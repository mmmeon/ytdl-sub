from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional
from typing import Set
from urllib.parse import urlparse

from yt_dlp.utils import datetime_from_str

from ytdl_sub.config.plugin.plugin import Plugin
from ytdl_sub.config.plugin.plugin_operation import PluginOperation
from ytdl_sub.config.validators.options import ToggleableOptionsDictValidator
from ytdl_sub.entries.entry import Entry
from ytdl_sub.entries.script.variable_definitions import VARIABLES
from ytdl_sub.entries.script.variable_definitions import VariableDefinitions
from ytdl_sub.utils.exceptions import ValidationException
from ytdl_sub.utils.file_handler import FileHandler
from ytdl_sub.utils.file_handler import FileMetadata
from ytdl_sub.utils.logger import Logger
from ytdl_sub.validators.string_datetime import StringDatetimeValidator
from ytdl_sub.validators.string_formatter_validators import StringFormatterValidator

v: VariableDefinitions = VARIABLES

logger = Logger.get("strm-file")


class StrmFileOptions(ToggleableOptionsDictValidator):
    """
    Creates a .strm file for each entry that contains a URL for streaming the video
    without storing the actual video file locally. This is useful for media servers
    that support streaming from external sources.

    When used without ``strm_before``, the plugin operates in **standalone mode**:
    all entries become ``.strm`` files and ``skip_download`` is set automatically.

    When ``strm_before`` is set, the plugin operates in **conditional mode**: only
    entries with an upload date before the given threshold become ``.strm`` files.
    Entries within the threshold are downloaded normally. This is designed to pair
    with the ``Only Recent`` family of presets.

    The entry's file extension is changed to ``.strm``, so the standard
    ``output_options.file_name`` controls the output file name.

    :Usage:

    .. code-block:: yaml

       # Standalone: all entries become .strm files
       strm_file:
         strm_proxy_url: "http://localhost:8096/proxy/"
         video_id_variable: "{id}"

       # Conditional: only entries before the date become .strm files
       strm_file:
         strm_proxy_url: "http://localhost:8096/proxy/"
         video_id_variable: "{id}"
         strm_before: "today-2months"
    """

    _required_keys = {"strm_proxy_url", "video_id_variable"}
    _optional_keys = {"enable", "strm_before"}

    @classmethod
    def partial_validate(cls, name: str, value: Any) -> None:
        """
        Partially validate strm file options.
        Sets default values for required keys to allow presets to be combined.
        """
        if isinstance(value, dict):
            if "strm_proxy_url" not in value:
                value["strm_proxy_url"] = "http://localhost/"
            if "video_id_variable" not in value:
                value["video_id_variable"] = "{id}"
        _ = cls(name, value)

    def __init__(self, name, value):
        super().__init__(name, value)

        self._strm_proxy_url = self._validate_key(
            key="strm_proxy_url", validator=StringFormatterValidator
        )
        self._video_id_variable = self._validate_key(
            key="video_id_variable", validator=StringFormatterValidator
        )
        self._strm_before = self._validate_key_if_present(
            key="strm_before", validator=StringDatetimeValidator
        )

        self._validate_proxy_url()

    def _validate_proxy_url(self) -> None:
        """
        Validate that strm_proxy_url has a valid http or https protocol.
        Skip validation if the URL contains format variables (e.g., {variable}),
        since those will be validated at runtime.
        """
        url_str = self._strm_proxy_url.format_string
        if not url_str or "{" in url_str:
            return

        try:
            parsed = urlparse(url_str)
            if parsed.scheme not in ("http", "https"):
                raise self._validation_exception(
                    f"strm_proxy_url must use http or https protocol, got '{parsed.scheme}'"
                )
        except ValueError as e:
            raise self._validation_exception(f"strm_proxy_url is not a valid URL: {e}")

    @property
    def strm_proxy_url(self) -> StringFormatterValidator:
        """
        :expected type: EntryFormatter
        :description:
          The base URL for the streaming proxy. This will be prepended to the video ID.
          Must use http or https protocol.
        """
        return self._strm_proxy_url

    @property
    def video_id_variable(self) -> StringFormatterValidator:
        """
        :expected type: EntryFormatter
        :description:
          The variable containing the video ID (e.g., "{id}", "{video_id}").
          This will be appended to the proxy URL.
        """
        return self._video_id_variable

    @property
    def strm_before(self) -> Optional[StringDatetimeValidator]:
        """
        :expected type: Optional[OverridesFormatter]
        :description:
          Optional. When set, only entries with an upload date **before** this
          datetime become ``.strm`` files. Entries on or after this date are
          downloaded normally. Uses yt-dlp datetime format
          (e.g., ``today-2months``, ``20240101``). Can use override variables.
        """
        return self._strm_before

    @property
    def is_conditional(self) -> bool:
        """True when strm_before is set, meaning only some entries become .strm files."""
        return self._strm_before is not None

    def modified_variables(self) -> Dict[PluginOperation, Set[str]]:
        """
        Modifies ``ext`` to ``strm``, so do not resolve until this has run.
        """
        return {PluginOperation.MODIFY_ENTRY: {v.ext.variable_name}}


class StrmFilePlugin(Plugin[StrmFileOptions]):
    plugin_options_type = StrmFileOptions

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._strm_entries: set = set()
        # Track total entries processed for memory management cleanup
        self._total_entries_processed: int = 0
        # Cleanup threshold: after this many entries, we'll clear old entries from the set
        self._cleanup_threshold: int = 1000

    def _validate_video_id(self, video_id: str, entry: Entry) -> None:
        """
        Validate that the resolved video ID is a non-empty string.
        """
        if not video_id or not isinstance(video_id, str):
            raise ValidationException(
                f"video_id_variable resolved to an empty or invalid value for entry "
                f"'{entry.title}'. Please ensure the variable resolves to a valid video ID."
            )

    def _check_filename_collision(
        self, entry: Entry, strm_file_path: Path
    ) -> Optional[Path]:
        """
        Check for potential filename collisions when changing extension to .strm.
        Returns the colliding file path if one exists, None otherwise.
        """
        original_ext = entry.ext
        if original_ext == "strm":
            return None

        base_path = strm_file_path.with_suffix("")
        potential_collision = base_path.with_suffix(f".{original_ext}")

        if potential_collision.exists():
            return potential_collision

        return None

    def _add_strm_entry(self, uid: str) -> None:
        """
        Add an entry UID to the strm entries set with memory management.
        Periodically cleans up the set to prevent memory issues in long-running applications.
        """
        self._strm_entries.add(uid)
        self._total_entries_processed += 1

        # Cleanup memory periodically to prevent unbounded growth
        if self._total_entries_processed > self._cleanup_threshold:
            # Keep only the most recent entries by limiting set size
            if len(self._strm_entries) > self._cleanup_threshold:
                # Keep a reasonable number of entries (half the threshold)
                entries_to_keep = self._cleanup_threshold // 2
                # Convert to list and keep the last entries_to_keep items
                entries_list = list(self._strm_entries)
                self._strm_entries = set(entries_list[-entries_to_keep:])
                logger.debug(
                    "Cleaned up strm_entries set, current size: %d",
                    len(self._strm_entries),
                )
            # Reset counter after cleanup
            self._total_entries_processed = 0

    def _build_streaming_url(self, entry: Entry) -> str:
        """
        Build the streaming URL by joining the proxy URL and video ID.
        Properly handles URL joining to avoid malformed URLs.
        """
        strm_proxy_url = self.overrides.apply_formatter(
            formatter=self.plugin_options.strm_proxy_url, entry=entry
        )
        video_id = self.overrides.apply_formatter(
            formatter=self.plugin_options.video_id_variable, entry=entry
        )

<<<<<<< HEAD
        self._validate_video_id(video_id, entry)
=======
        # Ensure proxy URL ends with a slash for proper joining
        if not strm_proxy_url.endswith("/"):
            strm_proxy_url += "/"
>>>>>>> strm-fixes

        return f"{strm_proxy_url}{video_id}"

    def _write_and_save_strm(self, entry: Entry) -> bool:
        """
        Write a .strm file to the working directory and save it to the output directory.
        Used in conditional mode where we handle the file entirely at metadata time.

        Returns True if the file was successfully created and saved, False otherwise.
        """
        streaming_url = self._build_streaming_url(entry)

        entry.add({v.ext: "strm"})

        strm_file_name = entry.get_download_file_name()
        strm_file_path = Path(self.working_directory) / strm_file_name

        collision = self._check_filename_collision(entry, strm_file_path)
        if collision:
            logger.warning(
                "Filename collision detected: .strm file '%s' would overwrite existing file '%s'. "
                "Consider using output_options.file_name to differentiate.",
                strm_file_path,
                collision,
            )

        if not self.is_dry_run:
<<<<<<< HEAD
            strm_file_path.parent.mkdir(parents=True, exist_ok=True)
            strm_file_path.write_text(streaming_url, encoding="utf-8")
=======
            try:
                os.makedirs(os.path.dirname(strm_file_path), exist_ok=True)
                with open(strm_file_path, "w", encoding="utf-8") as f:
                    f.write(streaming_url)
            except OSError as e:
                logger.warning(
                    "Failed to write .strm file for '%s': %s",
                    entry.title,
                    str(e),
                )
                return False
>>>>>>> strm-fixes

        strm_metadata = FileMetadata.from_dict(
            value_dict={"streaming_url": streaming_url},
            title="STRM file",
        )

        try:
            self.save_file(
                file_name=strm_file_name, file_metadata=strm_metadata, entry=entry
            )
        except Exception as e:
            logger.warning(
                "Failed to save .strm file for '%s': %s",
                entry.title,
                str(e),
            )
            return False

        # Only delete temp file after confirming save was successful
        if not self.is_dry_run:
            FileHandler.delete(strm_file_path)

        return True

    def _is_entry_before_threshold(self, entry: Entry) -> bool:
        """
        Check if the entry's upload_date is before strm_before threshold.

        Returns False if strm_before is not set (should not happen in conditional mode).
        Uses proper datetime comparison instead of string comparison.
        """
        if self.plugin_options.strm_before is None:
            return False

        threshold_str = self.overrides.apply_formatter(
            formatter=self.plugin_options.strm_before
        )
        threshold_date = datetime_from_str(threshold_str).date()
<<<<<<< HEAD
=======

        entry_date_str = entry.try_get(v.upload_date, str)
        if entry_date_str is None:
            logger.warning(
                "Entry '%s' has no upload_date, skipping .strm creation",
                entry.title,
            )
            return False

        try:
            entry_date = datetime_from_str(entry_date_str).date()
        except Exception:
            logger.warning(
                "Entry '%s' has malformed upload_date '%s', skipping .strm creation",
                entry.title,
                entry_date_str,
            )
            return False

        return entry_date < threshold_date
>>>>>>> strm-fixes

        entry_date_str = entry.try_get(v.upload_date, str)
        if entry_date_str is None:
            logger.warning(
                "Entry '%s' has no upload_date, skipping .strm creation",
                entry.title,
            )
            return False

        try:
            entry_date = datetime_from_str(entry_date_str).date()
        except (ValueError, TypeError):
            logger.warning(
                "Entry '%s' has malformed upload_date '%s', skipping .strm creation",
                entry.title,
                entry_date_str,
            )
            return False

        return entry_date < threshold_date

    def ytdl_options(self) -> Optional[Dict]:
        """
        In standalone mode, skip all downloads since every entry becomes a .strm file.
        In conditional mode, return None so entries are downloaded normally.
        """
        if self.plugin_options.is_conditional:
            return None
        return {"skip_download": True}

    def modify_entry_metadata(self, entry: Entry) -> Optional[Entry]:
        """
        In conditional mode, intercept entries whose upload_date is before the
        strm_before threshold. Create a .strm file for them and return None to
        skip the download.

        In standalone mode, this is a no-op (all entries flow to modify_entry).
        """
        if not self.plugin_options.is_conditional:
            return entry

        if self._is_entry_before_threshold(entry):
            logger.info(
                "Creating .strm file for '%s' (upload date before threshold)",
                entry.title,
            )

            # Add error recovery: only mark as strm entry if file was created successfully
            if self._write_and_save_strm(entry):
                self._add_strm_entry(entry.ytdl_uid())
                return None
            else:
                # Fallback: allow the entry to be downloaded normally
                logger.info(
                    "Falling back to download for '%s' due to .strm creation failure",
                    entry.title,
                )
                return entry

        return entry

    def modify_entry(self, entry: Entry) -> Optional[Entry]:
        """
        In standalone mode, write the streaming URL into a .strm file at the entry's
        download path and update the entry's extension to ``strm``.

        In conditional mode, this is a no-op — strm entries were already handled in
        modify_entry_metadata, and normal entries pass through unchanged.
        """
        if self.plugin_options.is_conditional:
            return entry

        streaming_url = self._build_streaming_url(entry)

        entry.add({v.ext: "strm"})

        if not self.is_dry_run:
<<<<<<< HEAD
            strm_file_path = Path(entry.get_download_file_path())

            collision = self._check_filename_collision(entry, strm_file_path)
            if collision:
                logger.warning(
                    "Filename collision: .strm '%s' would overwrite existing file '%s'. "
                    "Consider using output_options.file_name to differentiate.",
                    strm_file_path,
                    collision,
                )

            strm_file_path.parent.mkdir(parents=True, exist_ok=True)
            strm_file_path.write_text(streaming_url, encoding="utf-8")
=======
            try:
                strm_file_path = Path(entry.get_download_file_path())
                os.makedirs(os.path.dirname(strm_file_path), exist_ok=True)
                with open(strm_file_path, "w", encoding="utf-8") as strm_file:
                    strm_file.write(streaming_url)
            except OSError as e:
                logger.warning(
                    "Failed to write .strm file for '%s': %s",
                    entry.title,
                    str(e),
                )
                return entry
>>>>>>> strm-fixes

        return entry

    def post_process_entry(self, entry: Entry) -> Optional[FileMetadata]:
        """
        In standalone mode, return metadata about the .strm file for the transaction log.
        In conditional mode, this only runs for normally-downloaded entries (no-op).
        """
        if self.plugin_options.is_conditional:
            return None

        streaming_url = self._build_streaming_url(entry)
        return FileMetadata.from_dict(
            value_dict={"streaming_url": streaming_url},
            title="STRM file",
        )
