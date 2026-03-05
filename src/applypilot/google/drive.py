"""Google Drive/Docs operations: download, upload, template fill, PDF export."""

import io
import logging
from pathlib import Path
from typing import Any

_GOOGLE_DEPS_ERROR: ModuleNotFoundError | None = None

try:
    from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("googleapiclient"):
        _GOOGLE_DEPS_ERROR = exc
        MediaIoBaseDownload = None  # type: ignore[assignment]
        MediaFileUpload = None  # type: ignore[assignment]
    else:
        raise

from applypilot.google.auth import get_service

log = logging.getLogger(__name__)


def _require_google_deps() -> None:
    if _GOOGLE_DEPS_ERROR is not None:
        raise RuntimeError(
            "Google integration dependencies are missing. Install: "
            "pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        ) from _GOOGLE_DEPS_ERROR


def download_file(file_id: str, dest_path: Path):
    """Download a file from Google Drive."""
    _require_google_deps()
    service = get_service("drive", "v3")
    meta = service.files().get(fileId=file_id, fields="mimeType,name").execute()
    mime_type = meta.get("mimeType", "")

    if mime_type == "application/vnd.google-apps.document":
        # Export Google Docs as plain text for resume tailoring input.
        request = service.files().export_media(fileId=file_id, mimeType="text/plain")
    else:
        request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        progress = int(status.progress() * 100)
        log.info("Download progress: %d%%", progress)
    
    with open(dest_path, "wb") as f:
        f.write(fh.getvalue())
    return dest_path

def upload_file(local_path: Path, folder_id: str | None = None, as_google_doc: bool = False):
    """Upload a file to Google Drive."""
    _require_google_deps()
    service = get_service("drive", "v3")
    
    name = local_path.stem if as_google_doc else local_path.name
    file_metadata: dict[str, Any] = {"name": name}
    
    if folder_id:
        file_metadata["parents"] = [folder_id]
        
    if as_google_doc:
        file_metadata["mimeType"] = "application/vnd.google-apps.document"
        
    mime_type = "application/pdf" if local_path.suffix == ".pdf" else "text/plain"
    media = MediaFileUpload(str(local_path), mimetype=mime_type)
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()
    log.info("Uploaded file with ID: %s", file.get("id"))
    return file.get("id")

def find_file_by_name(name: str):
    """Find a file on Drive by its name."""
    service = get_service("drive", "v3")
    query = f"name = '{name}' and trashed = false"
    results = service.files().list(
        q=query, spaces="drive", fields="files(id, name)"
    ).execute()
    items = results.get("files", [])
    if not items:
        return None
    return items[0]


def copy_file(file_id: str, new_name: str, folder_id: str | None = None) -> str:
    """Copy a Drive file and return the new file ID."""
    service = get_service("drive", "v3")
    body: dict[str, Any] = {"name": new_name}
    if folder_id:
        body["parents"] = [folder_id]
    copied = service.files().copy(fileId=file_id, body=body, fields="id").execute()
    return str(copied["id"])


def replace_text_in_google_doc(document_id: str, replacements: dict[str, str]) -> None:
    """Replace placeholders in a Google Doc while preserving existing formatting."""
    docs = get_service("docs", "v1")
    requests = []
    for src, dst in replacements.items():
        requests.append(
            {
                "replaceAllText": {
                    "containsText": {"text": src, "matchCase": True},
                    "replaceText": dst,
                }
            }
        )

    if not requests:
        return

    docs.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()


def export_google_doc_as_pdf(document_id: str, dest_path: Path) -> Path:
    """Export a Google Doc to PDF and write it to dest_path."""
    _require_google_deps()
    service = get_service("drive", "v3")
    request = service.files().export_media(fileId=document_id, mimeType="application/pdf")
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(fh.getvalue())
    return dest_path
