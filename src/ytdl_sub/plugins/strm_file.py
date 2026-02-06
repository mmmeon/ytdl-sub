import os
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional
from typing import Set

from yt_dlp.utils import datetime_from_str

from ytdl_sub.config.plugin.plugin import Plugin
from ytdl_sub.config.plugin.plugin_operation import PluginOperation
from ytdl_sub.config.validators.options import ToggleableOptionsDictValidator
from ytdl_sub.entries.entry import Entry
from ytdl_sub.entries.script.variable_definitions import VARIABLES
from ytdl_sub.entries.script.variable_definitions import VariableDefinitions
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
        Partially validate strm file options
        """
        if isinstance(value, dict):
            value["strm_proxy_url"] = value.get("strm_proxy_url", "http://placeholder/")
            value["video_id_variable"] = value.get("video_id_variable", "{id}")
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

    @property
    def strm_proxy_url(self) -> StringFormatterValidator:
        """
        :expected type: EntryFormatter
        :description:
          The base URL for the streaming proxy. This will be prepended to the video ID.
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
        # Track entries handled at metadata time so we skip them in modify_entry
        self._strm_entries: set = set()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _build_streaming_url(self, entry: Entry) -> str:
        strm_proxy_url = self.overrides.apply_formatter(
            formatter=self.plugin_options.strm_proxy_url, entry=entry
        )
        video_id = self.overrides.apply_formatter(
            formatter=self.plugin_options.video_id_variable, entry=entry
        )
        return f"{strm_proxy_url}{video_id}"

    def _write_and_save_strm(self, entry: Entry) -> None:
        """
        Write a .strm file to the working directory and save it to the output directory.
        Used in conditional mode where we handle the file entirely at metadata time.
        """
        streaming_url = self._build_streaming_url(entry)

        # Build the output file name from output_options.file_name with ext=strm
        entry.add({v.ext: "strm"})

        strm_file_name = entry.get_download_file_name()
        strm_file_path = Path(self.working_directory) / strm_file_name

        if not self.is_dry_run:
            os.makedirs(os.path.dirname(strm_file_path), exist_ok=True)
            with open(strm_file_path, "w", encoding="utf-8") as f:
                f.write(streaming_url)

        strm_metadata = FileMetadata.from_dict(
            value_dict={"streaming_url": streaming_url},
            title="STRM file",
        )

        self.save_file(
            file_name=strm_file_name, file_metadata=strm_metadata, entry=entry
        )

        if not self.is_dry_run:
            FileHandler.delete(strm_file_path)

    def _is_entry_before_threshold(self, entry: Entry) -> bool:
        """Check if the entry's upload_date is before strm_before threshold."""
        assert self.plugin_options.strm_before is not None
        threshold_str = self.overrides.apply_formatter(
            formatter=self.plugin_options.strm_before
        )
        threshold_date = datetime_from_str(threshold_str).date().strftime("%Y%m%d")
        entry_date = entry.get(v.upload_date, str)
        return entry_date < threshold_date

    # ── lifecycle hooks ──────────────────────────────────────────────────────

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
                "Creating .strm file for '%s' (upload date before threshold)", entry.title
            )
            self._write_and_save_strm(entry)
            self._strm_entries.add(entry.ytdl_uid())
            return None

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

        # Standalone mode: all entries become .strm files
        streaming_url = self._build_streaming_url(entry)

        entry.add({v.ext: "strm"})

        if not self.is_dry_run:
            strm_file_path = Path(entry.get_download_file_path())
            os.makedirs(os.path.dirname(strm_file_path), exist_ok=True)
            with open(strm_file_path, "w", encoding="utf-8") as strm_file:
                strm_file.write(streaming_url)

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
