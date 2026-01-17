import os
from pathlib import Path
from typing import Optional

from ytdl_sub.config.plugin.plugin import Plugin
from ytdl_sub.config.validators.options import ToggleableOptionsDictValidator
from ytdl_sub.entries.entry import Entry
from ytdl_sub.utils.file_handler import FileHandler
from ytdl_sub.utils.file_handler import FileMetadata
from ytdl_sub.validators.file_path_validators import StringFormatterFileNameValidator
from ytdl_sub.validators.string_formatter_validators import StringFormatterValidator


class StrmFileOptions(ToggleableOptionsDictValidator):
    """
    Creates a .strm file for each entry that contains a URL for streaming the video
    without storing the actual video file locally. This is useful for media servers
    that support streaming from external sources.

    :Usage:

    .. code-block:: yaml

       strm_file:
         strm_file_name: "{title_sanitized}.strm"
         strm_proxy_url: "http://localhost:8096/proxy/"
         video_id_variable: "{id}"
    """

    _required_keys = {"strm_file_name", "strm_proxy_url", "video_id_variable"}
    _optional_keys = {"enable"}

    def __init__(self, name, value):
        super().__init__(name, value)

        self._strm_file_name = self._validate_key(
            key="strm_file_name", validator=StringFormatterFileNameValidator
        )
        self._strm_proxy_url = self._validate_key(
            key="strm_proxy_url", validator=StringFormatterValidator
        )
        self._video_id_variable = self._validate_key(
            key="video_id_variable", validator=StringFormatterValidator
        )

    @property
    def strm_file_name(self) -> StringFormatterFileNameValidator:
        """
        :expected type: EntryFormatter
        :description:
          The STRM file name. Typically matches the video file name pattern but with .strm extension.
        """
        return self._strm_file_name

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


class StrmFilePlugin(Plugin[StrmFileOptions]):
    plugin_options_type = StrmFileOptions

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track dummy video files created (output file paths) to delete later
        self._dummy_files_to_delete = []

    def modify_entry(self, entry: Entry) -> Entry:
        """
        Creates a dummy video file so ytdl-sub doesn't fail when skip_download is enabled.
        This is necessary because ytdl-sub expects the video file to exist.

        Parameters
        ----------
        entry:
            Entry to create a dummy file for

        Returns
        -------
        The entry unchanged
        """
        # Create a minimal empty video file as a placeholder
        # This file will be moved by ytdl-sub's file handler
        dummy_video_path = Path(entry.get_download_file_path())

        if not dummy_video_path.exists():
            os.makedirs(os.path.dirname(dummy_video_path), exist_ok=True)
            # Create an empty file - just needs to exist for ytdl-sub's file handling
            dummy_video_path.touch()

        return entry

    def post_process_entry(self, entry: Entry) -> None:
        """
        Creates a .strm file for the entry with the streaming URL.
        Also tracks the output video file path for later deletion.

        Parameters
        ----------
        entry:
            Entry to create a .strm file for
        """
        # Get the formatted values
        strm_file_name = self.overrides.apply_formatter(
            formatter=self.plugin_options.strm_file_name, entry=entry
        )
        strm_proxy_url = self.overrides.apply_formatter(
            formatter=self.plugin_options.strm_proxy_url, entry=entry
        )
        video_id = self.overrides.apply_formatter(
            formatter=self.plugin_options.video_id_variable, entry=entry
        )

        # Create the streaming URL
        streaming_url = f"{strm_proxy_url}{video_id}"

        # Write the .strm file
        strm_file_path = Path(self.working_directory) / strm_file_name
        os.makedirs(os.path.dirname(strm_file_path), exist_ok=True)
        with open(strm_file_path, "w", encoding="utf-8") as strm_file:
            strm_file.write(streaming_url)

        # Save the strm file and log its metadata
        strm_metadata = FileMetadata.from_dict(
            value_dict={"streaming_url": streaming_url},
            title="STRM file",
        )

        self.save_file(file_name=strm_file_name, file_metadata=strm_metadata, entry=entry)

        FileHandler.delete(strm_file_path)

        # Track the output video file path for deletion after all processing is complete
        # The file_name in the strm path has same pattern as episode_file_path, just add ext
        # Build the output video file name from the strm file name by changing extension
        output_video_file_name = strm_file_name.rsplit('.', 1)[0] + '.' + entry.ext
        output_file_path = Path(self._enhanced_download_archive.output_directory) / output_video_file_name
        self._dummy_files_to_delete.append(output_file_path)

    def post_process_subscription(self):
        """
        Delete all dummy video files after the subscription is complete.
        This removes the empty placeholder files while keeping .strm, .nfo, thumbnails, etc.
        """
        for dummy_file in self._dummy_files_to_delete:
            if dummy_file.exists() and dummy_file.stat().st_size == 0:
                FileHandler.delete(dummy_file)

        # Clear the list for the next subscription
        self._dummy_files_to_delete = []
