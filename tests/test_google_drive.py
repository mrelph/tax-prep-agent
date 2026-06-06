"""Tests for Google Drive integration."""

import json
from unittest.mock import MagicMock, patch

import pytest

try:
    from tax_agent.collectors.google_drive import (
        DriveFile,
        DriveFolder,
        GoogleDriveCollector,
        SUPPORTED_MIME_TYPES,
    )
except ImportError:
    pytest.skip(
        "Google Drive dependencies not installed",
        allow_module_level=True,
    )


@pytest.fixture
def mock_config():
    """Mock configuration to avoid keyring issues."""
    with patch("tax_agent.collectors.google_drive.get_config") as mock:
        config = MagicMock()
        config.get_google_credentials.return_value = None
        config.get_google_client_config.return_value = None
        mock.return_value = config
        yield config


@pytest.fixture
def mock_credentials():
    """Mock valid Google credentials."""
    return {
        "token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id.apps.googleusercontent.com",
        "client_secret": "test_client_secret",
    }


class TestDriveFile:
    """Tests for DriveFile dataclass."""

    def test_create_drive_file(self):
        """Test creating a DriveFile."""
        file = DriveFile(
            id="abc123",
            name="W2_2024.pdf",
            mime_type="application/pdf",
        )
        assert file.id == "abc123"
        assert file.name == "W2_2024.pdf"
        assert file.mime_type == "application/pdf"
        assert not file.is_google_doc
        assert file.extension == ".pdf"

    def test_google_doc_detection(self):
        """Test detecting Google Docs."""
        file = DriveFile(
            id="doc123",
            name="Tax Notes",
            mime_type="application/vnd.google-apps.document",
        )
        assert file.is_google_doc
        assert file.extension == ".pdf"  # Google Docs export as PDF

    def test_image_file(self):
        """Test image file extension."""
        file = DriveFile(
            id="img123",
            name="1099_scan.png",
            mime_type="image/png",
        )
        assert file.extension == ".png"
        assert not file.is_google_doc


class TestDriveFolder:
    """Tests for DriveFolder dataclass."""

    def test_create_drive_folder(self):
        """Test creating a DriveFolder."""
        folder = DriveFolder(
            id="folder123",
            name="Tax Documents 2024",
            parent_id="root",
        )
        assert folder.id == "folder123"
        assert folder.name == "Tax Documents 2024"
        assert folder.parent_id == "root"


class TestGoogleDriveCollector:
    """Tests for GoogleDriveCollector class."""

    def test_not_authenticated_without_credentials(self, mock_config):
        """Test that collector is not authenticated without credentials."""
        collector = GoogleDriveCollector()
        assert not collector.is_authenticated()

    def test_authenticated_with_valid_credentials(self, mock_config, mock_credentials):
        """Test authentication check with valid credentials."""
        mock_config.get_google_credentials.return_value = mock_credentials

        with patch("tax_agent.collectors.google_drive.Credentials") as mock_creds_class:
            mock_creds = MagicMock()
            mock_creds.valid = True
            mock_creds.expired = False
            mock_creds_class.return_value = mock_creds

            collector = GoogleDriveCollector()
            # Force credentials to be loaded
            collector._credentials = mock_creds
            assert collector.is_authenticated()

    def test_credential_storage(self, mock_config, mock_credentials):
        """Test that credentials are stored correctly."""
        collector = GoogleDriveCollector()

        # Create mock credentials object
        mock_creds = MagicMock()
        mock_creds.token = mock_credentials["token"]
        mock_creds.refresh_token = mock_credentials["refresh_token"]
        mock_creds.token_uri = mock_credentials["token_uri"]
        mock_creds.client_id = mock_credentials["client_id"]
        mock_creds.client_secret = mock_credentials["client_secret"]

        collector._save_credentials(mock_creds)

        # Verify set_google_credentials was called
        mock_config.set_google_credentials.assert_called_once()
        call_args = mock_config.set_google_credentials.call_args[0][0]
        assert call_args["token"] == mock_credentials["token"]
        assert call_args["refresh_token"] == mock_credentials["refresh_token"]

    def test_list_folders_returns_correct_format(self, mock_config, mock_credentials):
        """Test that list_folders returns DriveFolder objects."""
        mock_config.get_google_credentials.return_value = mock_credentials

        # Mock the Drive API response
        mock_response = {
            "files": [
                {"id": "folder1", "name": "Tax 2024", "parents": ["root"]},
                {"id": "folder2", "name": "Receipts", "parents": ["root"]},
            ]
        }

        with patch("tax_agent.collectors.google_drive.Credentials"):
            with patch("tax_agent.collectors.google_drive.build") as mock_build:
                mock_service = MagicMock()
                mock_files = MagicMock()
                mock_list = MagicMock()
                mock_list.execute.return_value = mock_response
                mock_files.list.return_value = mock_list
                mock_service.files.return_value = mock_files
                mock_build.return_value = mock_service

                collector = GoogleDriveCollector()
                collector._credentials = MagicMock(valid=True)
                collector._service = mock_service

                folders = collector.list_folders("root")

                assert len(folders) == 2
                assert all(isinstance(f, DriveFolder) for f in folders)
                assert folders[0].name == "Tax 2024"
                assert folders[1].name == "Receipts"

    def test_list_files_returns_supported_types(self, mock_config, mock_credentials):
        """Test that list_files returns only supported file types."""
        mock_config.get_google_credentials.return_value = mock_credentials

        mock_response = {
            "files": [
                {"id": "file1", "name": "W2.pdf", "mimeType": "application/pdf"},
                {"id": "file2", "name": "1099.png", "mimeType": "image/png"},
                {"id": "file3", "name": "Notes", "mimeType": "application/vnd.google-apps.document"},
            ]
        }

        with patch("tax_agent.collectors.google_drive.Credentials"):
            with patch("tax_agent.collectors.google_drive.build") as mock_build:
                mock_service = MagicMock()
                mock_files = MagicMock()
                mock_list = MagicMock()
                mock_list.execute.return_value = mock_response
                mock_files.list.return_value = mock_list
                mock_service.files.return_value = mock_files
                mock_build.return_value = mock_service

                collector = GoogleDriveCollector()
                collector._credentials = MagicMock(valid=True)
                collector._service = mock_service

                files = collector.list_files("folder123")

                assert len(files) == 3
                assert all(isinstance(f, DriveFile) for f in files)
                assert files[0].name == "W2.pdf"
                assert files[1].mime_type == "image/png"
                assert files[2].is_google_doc


class TestSupportedMimeTypes:
    """Tests for supported MIME types."""

    def test_pdf_supported(self):
        """Test that PDF is supported."""
        assert "application/pdf" in SUPPORTED_MIME_TYPES

    def test_images_supported(self):
        """Test that common image formats are supported."""
        assert "image/png" in SUPPORTED_MIME_TYPES
        assert "image/jpeg" in SUPPORTED_MIME_TYPES
        assert "image/tiff" in SUPPORTED_MIME_TYPES

    def test_google_docs_supported(self):
        """Test that Google Docs are supported."""
        assert "application/vnd.google-apps.document" in SUPPORTED_MIME_TYPES


class TestConfigIntegration:
    """Tests for config integration with Google credentials."""

    def test_google_credentials_methods_exist(self):
        """Test that Google credential methods exist in Config."""
        from tax_agent.config import Config

        config = Config.__new__(Config)
        assert hasattr(config, "get_google_credentials")
        assert hasattr(config, "set_google_credentials")
        assert hasattr(config, "clear_google_credentials")
        assert hasattr(config, "has_google_drive_configured")
        assert hasattr(config, "get_google_client_config")
        assert hasattr(config, "set_google_client_config")
