"""Google Drive integration for collecting tax documents."""

import io
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from tax_agent.config import get_config


# Read-only scope for security
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Supported file types for tax documents
SUPPORTED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/tiff": ".tiff",
    "application/vnd.google-apps.document": ".pdf",  # Export as PDF
}


@dataclass
class DriveFile:
    """Represents a file in Google Drive."""

    id: str
    name: str
    mime_type: str
    modified_time: str | None = None
    size: int | None = None

    @property
    def is_google_doc(self) -> bool:
        """Check if this is a native Google Doc (needs export)."""
        return self.mime_type == "application/vnd.google-apps.document"

    @property
    def extension(self) -> str:
        """Get the file extension."""
        return SUPPORTED_MIME_TYPES.get(self.mime_type, "")


@dataclass
class DriveFolder:
    """Represents a folder in Google Drive."""

    id: str
    name: str
    parent_id: str | None = None


class GoogleDriveCollector:
    """Collects tax documents from Google Drive."""

    def __init__(self):
        """Initialize the collector."""
        self.config = get_config()
        self._service = None
        self._credentials = None

    def is_authenticated(self) -> bool:
        """Check if we have valid credentials."""
        creds = self._load_credentials()
        return creds is not None and creds.valid

    def _load_credentials(self) -> Credentials | None:
        """Load credentials from keyring."""
        if self._credentials and self._credentials.valid:
            return self._credentials

        creds_dict = self.config.get_google_credentials()
        if not creds_dict:
            return None

        try:
            self._credentials = Credentials(
                token=creds_dict.get("token"),
                refresh_token=creds_dict.get("refresh_token"),
                token_uri=creds_dict.get("token_uri"),
                client_id=creds_dict.get("client_id"),
                client_secret=creds_dict.get("client_secret"),
                scopes=SCOPES,
            )

            # Refresh if expired
            if self._credentials.expired and self._credentials.refresh_token:
                self._credentials.refresh(Request())
                self._save_credentials(self._credentials)

            return self._credentials
        except Exception:
            return None

    def _save_credentials(self, creds: Credentials) -> None:
        """Save credentials to keyring."""
        creds_dict = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
        }
        self.config.set_google_credentials(creds_dict)
        self._credentials = creds

    def authenticate_with_client_file(self, client_secrets_file: str | Path) -> bool:
        """
        Authenticate using a client secrets JSON file.

        This runs the OAuth2 flow, opening a browser for user authorization.

        Args:
            client_secrets_file: Path to the client_secrets.json file from Google Cloud

        Returns:
            True if authentication was successful
        """
        client_secrets_file = Path(client_secrets_file)
        if not client_secrets_file.exists():
            raise FileNotFoundError(f"Client secrets file not found: {client_secrets_file}")

        # Load and store client config for future use
        with open(client_secrets_file) as f:
            client_config = json.load(f)
        self.config.set_google_client_config(client_config)

        # Run OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_file), SCOPES)
        creds = flow.run_local_server(port=0)

        self._save_credentials(creds)
        return True

    def authenticate_interactive(self) -> bool:
        """
        Run interactive OAuth flow using stored client config.

        Returns:
            True if authentication was successful
        """
        client_config = self.config.get_google_client_config()
        if not client_config:
            raise ValueError(
                "No client configuration found. "
                "Run 'tax-agent drive-auth --setup <credentials.json>' first."
            )

        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=0)

        self._save_credentials(creds)
        return True

    def _get_service(self):
        """Get or create the Drive API service."""
        if self._service is not None:
            return self._service

        creds = self._load_credentials()
        if not creds:
            raise ValueError(
                "Not authenticated with Google Drive. "
                "Run 'tax-agent drive-auth' first."
            )

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def list_folders(self, parent_id: str = "root") -> list[DriveFolder]:
        """
        List folders in Google Drive.

        Args:
            parent_id: Parent folder ID ('root' for root folder)

        Returns:
            List of DriveFolder objects
        """
        service = self._get_service()

        query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"

        folders = []
        page_token = None

        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, parents)",
                    pageToken=page_token,
                    orderBy="name",
                )
                .execute()
            )

            for item in response.get("files", []):
                parents = item.get("parents", [])
                folders.append(
                    DriveFolder(
                        id=item["id"],
                        name=item["name"],
                        parent_id=parents[0] if parents else None,
                    )
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return folders

    def list_files(
        self, folder_id: str, recursive: bool = False
    ) -> list[DriveFile]:
        """
        List supported files in a folder.

        Args:
            folder_id: Google Drive folder ID
            recursive: If True, include files from subfolders

        Returns:
            List of DriveFile objects
        """
        service = self._get_service()

        # Build MIME type filter
        mime_conditions = " or ".join(
            f"mimeType='{mt}'" for mt in SUPPORTED_MIME_TYPES
        )
        query = f"'{folder_id}' in parents and ({mime_conditions}) and trashed=false"

        files = []
        page_token = None

        while True:
            response = (
                service.files()
                .list(
                    q=query,
                    spaces="drive",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                    pageToken=page_token,
                    orderBy="name",
                )
                .execute()
            )

            for item in response.get("files", []):
                files.append(
                    DriveFile(
                        id=item["id"],
                        name=item["name"],
                        mime_type=item["mimeType"],
                        modified_time=item.get("modifiedTime"),
                        size=item.get("size"),
                    )
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        # Recursively get files from subfolders
        if recursive:
            subfolders = self.list_folders(folder_id)
            for subfolder in subfolders:
                files.extend(self.list_files(subfolder.id, recursive=True))

        return files

    def download_file(self, file: DriveFile) -> tuple[bytes, str]:
        """
        Download a file from Google Drive.

        Args:
            file: DriveFile object to download

        Returns:
            Tuple of (file content as bytes, suggested filename)
        """
        service = self._get_service()

        if file.is_google_doc:
            # Export Google Docs as PDF
            request = service.files().export_media(
                fileId=file.id, mimeType="application/pdf"
            )
            filename = f"{file.name}.pdf"
        else:
            request = service.files().get_media(fileId=file.id)
            filename = file.name

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)

        done = False
        while not done:
            _, done = downloader.next_chunk()

        return buffer.getvalue(), filename

    def download_to_temp_file(self, file: DriveFile) -> Path:
        """
        Download a file to a temporary location.

        Args:
            file: DriveFile object to download

        Returns:
            Path to the temporary file
        """
        content, filename = self.download_file(file)

        # Determine extension
        ext = file.extension
        if file.is_google_doc:
            ext = ".pdf"

        # Create temp file with proper extension
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, suffix=ext, prefix="taxdoc_"
        )
        temp_file.write(content)
        temp_file.close()

        return Path(temp_file.name)

    def get_folder_info(self, folder_id: str) -> DriveFolder | None:
        """
        Get information about a folder.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            DriveFolder object or None if not found
        """
        service = self._get_service()

        try:
            item = (
                service.files()
                .get(fileId=folder_id, fields="id, name, parents")
                .execute()
            )
            parents = item.get("parents", [])
            return DriveFolder(
                id=item["id"],
                name=item["name"],
                parent_id=parents[0] if parents else None,
            )
        except Exception:
            return None


def get_google_drive_collector() -> GoogleDriveCollector:
    """Get a GoogleDriveCollector instance."""
    return GoogleDriveCollector()
