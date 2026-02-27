import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, date
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.ytdl_sub.plugins.strm_file import StrmFilePlugin, StrmFileOptions
from src.ytdl_sub.entries.entry import Entry
from src.ytdl_sub.utils.exceptions import ValidationException
from src.ytdl_sub.utils.file_handler import FileMetadata


class TestStrmFile(unittest.TestCase):
    def setUp(self):
        # Mock options
        self.mock_options = MagicMock(spec=StrmFileOptions)
        self.mock_options.strm_before = MagicMock()

        # Set defaults for common mocks
        self.mock_options.is_conditional = False
        self.mock_options.strm_proxy_url.format_string = "http://localhost:8096/proxy/"
        self.mock_options.video_id_variable.format_string = "{id}"

        # Mock plugin
        self.plugin = StrmFilePlugin(
            plugin_options=self.mock_options,
            working_directory="/tmp",
            output_directory="/tmp/output",
            overrides=MagicMock(),
            is_dry_run=True,
        )

        # Mock entry
        self.entry = MagicMock(spec=Entry)
        self.entry.title = "Test Video"
        self.entry.get = MagicMock(return_value="dQw4w9WgXcQ")

    @patch("ytdl_sub.plugins.strm_file.datetime_from_str")
    def test_is_entry_before_threshold_normal_case(self, mock_datetime):
        """Test normal case where dates are properly formatted"""
        # Setup
        threshold_date = date(2023, 1, 1)
        entry_date = date(2022, 1, 1)  # Earlier date

        # Configure mocks
        self.plugin.overrides.apply_formatter = MagicMock(return_value="20230101")
        self.entry.try_get = MagicMock(return_value="20220101")

        # Create a mock datetime object with date method
        mock_date = MagicMock()
        mock_date.date.return_value = threshold_date
        mock_date2 = MagicMock()
        mock_date2.date.return_value = entry_date

        # Set side effect for datetime_from_str
        mock_datetime.side_effect = lambda d: (
            mock_date if d == "20230101" else mock_date2
        )

        # Run test
        result = self.plugin._is_entry_before_threshold(self.entry)

        # Assert
        self.assertTrue(result)
        self.entry.try_get.assert_called_once()

    @patch("ytdl_sub.plugins.strm_file.datetime_from_str")
    def test_is_entry_before_threshold_missing_date(self, mock_datetime):
        """Test case where entry is missing upload_date"""
        # Setup
        self.entry.try_get.return_value = None

        # Run test
        with patch("ytdl_sub.plugins.strm_file.logger") as mock_logger:
            result = self.plugin._is_entry_before_threshold(self.entry)

        # Assert
        self.assertFalse(result)
        mock_logger.warning.assert_called_once()

    @patch("ytdl_sub.plugins.strm_file.datetime_from_str")
    def test_is_entry_before_threshold_malformed_date(self, mock_datetime):
        """Test case where entry has malformed upload_date"""
        # Setup
        self.entry.try_get.return_value = "invalid-date"
        mock_datetime.side_effect = ValueError("Invalid date format")

        # Run test
        with patch("ytdl_sub.plugins.strm_file.logger") as mock_logger:
            result = self.plugin._is_entry_before_threshold(self.entry)

        # Assert
        self.assertFalse(result)
        mock_logger.warning.assert_called_once()

    def test_is_entry_before_threshold_none_strm_before(self):
        """Test case where strm_before is None"""
        # Setup
        self.plugin.plugin_options = MagicMock()
        self.plugin.plugin_options.strm_before = None

        # Run test
        result = self.plugin._is_entry_before_threshold(self.entry)

        # Assert
        self.assertFalse(result)
        # No calls to try_get or datetime_from_str should be made
        # Reset entry.try_get to a new mock for this test
        self.entry.try_get = MagicMock()
        self.entry.try_get.assert_not_called()


# Tests for _build_streaming_url method
def test_build_streaming_url_basic(self):
    """Test basic URL construction with simple proxy and video ID"""
    # Setup
    self.plugin.overrides.apply_formatter = MagicMock(
        side_effect=["http://localhost:8096/proxy/", "dQw4w9WgXcQ"]
    )

    # Run test
    url = self.plugin._build_streaming_url(self.entry)

    # Assert
    self.assertEqual(url, "http://localhost:8096/proxy/dQw4w9WgXcQ")
    self.plugin.overrides.apply_formatter.assert_called()


def test_build_streaming_url_with_variables(self):
    """Test proxy URL with format variables"""
    # Setup
    self.plugin.overrides.apply_formatter = MagicMock(
        side_effect=["http://server:8080/{server_id}/", "video123"]
    )

    # Run test
    url = self.plugin._build_streaming_url(self.entry)

    # Assert
    self.assertEqual(url, "http://server:8080/{server_id}/video123")


def test_build_streaming_url_custom_video_id_var(self):
    """Test with non-standard video ID variable"""
    # Setup
    self.plugin.overrides.apply_formatter = MagicMock(
        side_effect=["http://proxy/", "{youtube_id}"]
    )

    # Run test
    url = self.plugin._build_streaming_url(self.entry)

    # Assert
    self.assertEqual(url, "http://proxy/{youtube_id}")


# Tests for _validate_video_id method
def test_validate_video_id_valid(self):
    """Test validation passes for valid video ID"""
    # Should not raise exception
    self.plugin._validate_video_id("dQw4w9WgXcQ", self.entry)


def test_validate_video_id_empty_string(self):
    """Test validation fails for empty string"""
    with self.assertRaises(ValidationException) as ctx:
        self.plugin._validate_video_id("", self.entry)
    self.assertIn("empty or invalid value", str(ctx.exception))


def test_validate_video_id_none(self):
    """Test validation fails for None"""
    with self.assertRaises(ValidationException) as ctx:
        self.plugin._validate_video_id(None, self.entry)
    self.assertIn("empty or invalid value", str(ctx.exception))


def test_validate_video_id_non_string(self):
    """Test validation fails for non-string types"""
    with self.assertRaises(ValidationException):
        self.plugin._validate_video_id(12345, self.entry)


# Tests for _check_filename_collision method
@patch("ytdl_sub.plugins.strm_file.Path")
def test_collision_detected(self, mock_path_class):
    """Test collision is detected when original file exists"""
    # Setup
    mock_entry = MagicMock()
    mock_entry.ext = "mp4"
    mock_strm_path = MagicMock()
    mock_strm_path.with_suffix.return_value.with_suffix.return_value.exists.return_value = True

    # Run test
    collision = self.plugin._check_filename_collision(mock_entry, mock_strm_path)

    # Assert
    self.assertIsNotNone(collision)


@patch("ytdl_sub.plugins.strm_file.Path")
def test_no_collision_when_no_file(self, mock_path_class):
    """Test no collision when original file doesn't exist"""
    # Setup
    mock_entry = MagicMock()
    mock_entry.ext = "mp4"
    mock_strm_path = MagicMock()
    mock_strm_path.with_suffix.return_value.with_suffix.return_value.exists.return_value = False

    # Run test
    collision = self.plugin._check_filename_collision(mock_entry, mock_strm_path)

    # Assert
    self.assertIsNone(collision)


@patch("ytdl_sub.plugins.strm_file.Path")
def test_no_collision_already_strm(self, mock_path_class):
    """Test no collision when entry is already .strm"""
    # Setup
    mock_entry = MagicMock()
    mock_entry.ext = "strm"

    # Run test
    collision = self.plugin._check_filename_collision(mock_entry, MagicMock())

    # Assert
    self.assertIsNone(collision)


# Tests for _write_and_save_strm method
@patch("ytdl_sub.plugins.strm_file.FileHandler")
@patch("ytdl_sub.plugins.strm_file.Path")
def test_write_and_save_strm_creates_file(self, mock_path_class, mock_file_handler):
    """Test STRM file is created and saved correctly"""
    # Setup
    self.plugin.is_dry_run = False
    self.plugin.overrides.apply_formatter = MagicMock(
        side_effect=["http://proxy/", "video123"]
    )

    mock_entry = MagicMock()
    mock_entry.get_download_file_name.return_value = "video.strm"
    mock_entry.ytdl_uid.return_value = "uid123"
    mock_entry.add = MagicMock()

    mock_path_instance = MagicMock()
    mock_path_class.return_value = mock_path_instance

    # Run test
    self.plugin._write_and_save_strm(mock_entry)

    # Assert
    mock_path_instance.parent.mkdir.assert_called_once()
    mock_path_instance.write_text.assert_called_once_with(
        "http://proxy/video123", encoding="utf-8"
    )
    mock_entry.add.assert_called_once()
    self.plugin.save_file.assert_called_once()


# Tests for modify_entry_metadata (conditional mode)
def test_modify_entry_metadata_before_threshold(self):
    """Test entry before threshold returns None (skips download)"""
    # Setup
    self.mock_options.is_conditional = True
    self.plugin._is_entry_before_threshold = MagicMock(return_value=True)
    self.plugin._write_and_save_strm = MagicMock()

    # Run test
    result = self.plugin.modify_entry_metadata(self.entry)

    # Assert
    self.assertIsNone(result)
    self.plugin._write_and_save_strm.assert_called_once_with(self.entry)


def test_modify_entry_metadata_after_threshold(self):
    """Test entry after threshold returns entry (normal download)"""
    # Setup
    self.mock_options.is_conditional = True
    self.plugin._is_entry_before_threshold = MagicMock(return_value=False)

    # Run test
    result = self.plugin.modify_entry_metadata(self.entry)

    # Assert
    self.assertEqual(result, self.entry)


def test_modify_entry_metadata_standalone_mode(self):
    """Test standalone mode returns entry unchanged"""
    # Setup
    self.mock_options.is_conditional = False

    # Run test
    result = self.plugin.modify_entry_metadata(self.entry)

    # Assert
    self.assertEqual(result, self.entry)


# Tests for modify_entry (standalone mode)
@patch("ytdl_sub.plugins.strm_file.Path")
def test_modify_entry_standalone_mode(self, mock_path_class):
    """Test standalone mode creates STRM file"""
    # Setup
    self.mock_options.is_conditional = False
    self.plugin.is_dry_run = False
    self.plugin.overrides.apply_formatter = MagicMock(
        side_effect=["http://proxy/", "video123"]
    )

    mock_entry = MagicMock()
    mock_entry.get_download_file_path.return_value = "/tmp/video.mp4"
    mock_entry.add = MagicMock()

    mock_path_instance = MagicMock()
    mock_path_class.return_value = mock_path_instance

    # Run test
    result = self.plugin.modify_entry(mock_entry)

    # Assert
    self.assertEqual(result, mock_entry)
    mock_entry.add.assert_called_once()
    mock_path_instance.parent.mkdir.assert_called_once()
    mock_path_instance.write_text.assert_called_once()


def test_modify_entry_conditional_mode(self):
    """Test conditional mode passes entry through"""
    # Setup
    self.mock_options.is_conditional = True

    # Run test
    result = self.plugin.modify_entry(self.entry)

    # Assert
    self.assertEqual(result, self.entry)


# Tests for post_process_entry
def test_post_process_entry_standalone_mode(self):
    """Test metadata returned in standalone mode"""
    # Setup
    self.mock_options.is_conditional = False
    self.plugin.overrides.apply_formatter = MagicMock(
        side_effect=["http://proxy/", "video123"]
    )

    # Run test
    result = self.plugin.post_process_entry(self.entry)

    # Assert
    self.assertIsNotNone(result)
    self.assertEqual(result.title, "STRM file")
    # Could verify streaming_url in metadata if needed


def test_post_process_entry_conditional_mode(self):
    """Test None returned in conditional mode"""
    # Setup
    self.mock_options.is_conditional = True

    # Run test
    result = self.plugin.post_process_entry(self.entry)

    # Assert
    self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
