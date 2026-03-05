"""Google Workspace Auth: OAuth2 flow and token management."""

import logging
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from applypilot.config import APP_DIR, CONFIG_DIR

log = logging.getLogger(__name__)

# Default scopes for resume workflows (Drive + Docs only).
# Set APPLYPILOT_GOOGLE_FULL_SCOPES=1 to also request Gmail/Calendar scopes.
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/documents",
]
if os.environ.get("APPLYPILOT_GOOGLE_FULL_SCOPES") == "1":
    SCOPES.extend(
        [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar.events",
        ]
    )

TOKEN_PATH = APP_DIR / "google_token.json"
_CREDENTIAL_CANDIDATES = (
    lambda: Path(os.environ["GOOGLE_CREDENTIALS_FILE"]).expanduser(),
    lambda: APP_DIR / "google_credentials.json",
    lambda: Path.cwd() / "credentials.json",
    lambda: Path.cwd() / "google_credentials.json",
    lambda: CONFIG_DIR / "google_credentials.json",
)


def _resolve_credentials_path() -> Path | None:
    """Return first existing credentials file from known locations."""
    for build_path in _CREDENTIAL_CANDIDATES:
        try:
            path = build_path()
        except KeyError:
            continue
        if path.exists():
            return path
    return None

def get_credentials():
    """Get valid user credentials from storage or run auth flow."""
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                log.error("Failed to refresh token: %s", e)
                creds = None
        
        if not creds:
            credentials_path = _resolve_credentials_path()
            if not credentials_path:
                raise FileNotFoundError(
                    "Google credentials not found. Looked in:\n"
                    f"  - {APP_DIR / 'google_credentials.json'}\n"
                    f"  - {Path.cwd() / 'credentials.json'}\n"
                    f"  - {Path.cwd() / 'google_credentials.json'}\n"
                    f"  - {CONFIG_DIR / 'google_credentials.json'}\n"
                    "Set GOOGLE_CREDENTIALS_FILE to override."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
            
    return creds

def get_service(name: str, version: str):
    """Get a Google API service instance."""
    creds = get_credentials()
    return build(name, version, credentials=creds)
