#!/data/data/com.termux/files/usr/bin/python
import os
import pickle
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

# Load environment variables from ~/.env
env_path = Path.home() / ".env"
load_dotenv(dotenv_path=env_path)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class GoogleDriveSyncer:
    def __init__(self, client_id=None, client_secret=None, token_file: str = "token.pickle") -> None:
        # Get credentials from environment if not provided
        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            raise ValueError("Missing credentials. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in ~/.env file")

        self.token_file = token_file
        self.service = self.authenticate()

    def authenticate(self) -> Resource:
        """Authenticate using Client ID and Secret from environment"""
        creds = None

        # Load previous token if exists
        if os.path.exists(self.token_file):
            with open(self.token_file, "rb") as token:
                creds = pickle.load(token)

        # If credentials are invalid or don't exist, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Create flow using Client ID and Secret from .env
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": self.client_id,
                            "client_secret": self.client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "redirect_uris": ["http://localhost"],
                        }
                    },
                    SCOPES,
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            with open(self.token_file, "wb") as token:
                pickle.dump(creds, token)

        return build("drive", "v3", credentials=creds)

    def get_all_files(self, folder_id: str = "root"):
        """Get all files and folders from Google Drive"""
        all_items = []
        page_token = None

        while True:
            try:
                results = (
                    self.service
                    .files()
                    .list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        pageSize=1000,
                        fields="nextPageToken, files(id, name, mimeType, size, modifiedTime)",
                        pageToken=page_token,
                    )
                    .execute()
                )

                items = results.get("files", [])
                all_items.extend(items)

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

            except HttpError as error:
                print(f"An error occurred: {error}")
                break

        return all_items

    def download_file(self, file_id, file_name, local_path) -> bool:
        """Download a single file from Google Drive"""
        try:
            request = self.service.files().get_media(fileId=file_id)

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            with open(local_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    print(f"Downloading {file_name}: {int(status.progress() * 100)}%")

            print(f"✓ Downloaded: {file_name}")
            return True

        except HttpError as error:
            print(f"✗ Failed to download {file_name}: {error}")
            return False

    def sync_folder(self, drive_folder_id: str, local_folder_path, folder_name: str = "root") -> None:
        """Recursively sync Google Drive folder to local drive"""
        print(f"\n📁 Syncing folder: {folder_name}")

        # Ensure local folder exists
        os.makedirs(local_folder_path, exist_ok=True)

        # Get all items in the Drive folder
        items = self.get_all_files(drive_folder_id)

        for item in items:
            item_name = item["name"]
            item_id = item["id"]
            item_mime = item.get("mimeType", "")
            local_item_path = os.path.join(local_folder_path, item_name)

            if item_mime == "application/vnd.google-apps.folder":
                # It's a folder - recurse into it
                self.sync_folder(item_id, local_item_path, item_name)
            else:
                # It's a file - download if newer or doesn't exist
                remote_modified = item.get("modifiedTime")
                should_download = True

                if os.path.exists(local_item_path):
                    local_mtime = os.path.getmtime(local_item_path)
                    # Compare timestamps (convert to seconds since epoch)
                    from datetime import datetime

                    remote_time = datetime.fromisoformat(remote_modified.replace("Z", "+00:00")).timestamp()

                    if local_mtime >= remote_time:
                        should_download = False
                        print(f"⏭ Skipping (up to date): {item_name}")

                if should_download:
                    self.download_file(item_id, item_name, local_item_path)
                    # Set local file modification time to match Drive
                    if remote_modified:
                        from datetime import datetime

                        mod_time = datetime.fromisoformat(remote_modified.replace("Z", "+00:00")).timestamp()
                        os.utime(local_item_path, (mod_time, mod_time))

    def sync_all(self, local_base_path: str) -> None:
        """Sync entire Google Drive to local path"""
        print("Starting full Google Drive sync...")
        self.sync_folder("root", local_base_path, "My Drive")
        print("\n✅ Sync completed!")

    def sync_by_folder_name(self, folder_name, local_base_path) -> None:
        """Sync a specific folder by its name from root"""
        print(f"Searching for folder: {folder_name}")
        items = self.get_all_files("root")

        target_folder = None
        for item in items:
            if item["name"] == folder_name and item["mimeType"] == "application/vnd.google-apps.folder":
                target_folder = item
                break

        if target_folder:
            self.sync_folder(target_folder["id"], local_base_path, folder_name)
        else:
            print(f'Folder "{folder_name}" not found in root directory')


def main() -> None:
    # Configuration
    LOCAL_SYNC_PATH = "./google_drive_backup"  # Change this to your desired local path

    try:
        # Credentials are automatically loaded from ~/.env
        syncer = GoogleDriveSyncer()

        # Option 1: Sync entire Drive
        syncer.sync_all(LOCAL_SYNC_PATH)

        # Option 2: Sync specific folder by name
        # syncer.sync_by_folder_name('My Important Folder', LOCAL_SYNC_PATH)

        # Option 3: Sync specific folder by ID
        # syncer.sync_folder('FOLDER_ID_HERE', LOCAL_SYNC_PATH)

    except ValueError as e:
        print(f"Configuration error: {e}")
        print("\nPlease create ~/.env file with:")
        print("GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com")
        print("GOOGLE_CLIENT_SECRET=your_client_secret")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
