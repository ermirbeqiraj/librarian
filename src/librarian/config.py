import os
from pathlib import Path

from sqlalchemy.engine.url import make_url

DATABASE_URL = os.environ.get(
    "LIBRARIAN_DATABASE_URL",
    "postgresql+psycopg://librarian:librarian@127.0.0.1:5432/librarian",
)
# The SQL tool's read-only role. The default password matches the compose dev database
# (like librarian:librarian above); set LIBRARIAN_READER_PASSWORD on the homeserver.
READER_PASSWORD = os.environ.get("LIBRARIAN_READER_PASSWORD", "librarian_reader")
READER_DATABASE_URL = os.environ.get("LIBRARIAN_READER_DATABASE_URL")
if READER_DATABASE_URL is None:
    # Same database as DATABASE_URL, but as librarian_reader.
    READER_DATABASE_URL = str(
        make_url(DATABASE_URL).set(username="librarian_reader", password=READER_PASSWORD)
    )
# One root holds inbox/, quarantine/, processed/ and evals/. Dev keeps it out of Dropbox,
# so wiping Postgres and this folder resets everything.
ROOT = Path(os.environ.get("LIBRARIAN_ROOT", Path.home() / ".local/share/librarian"))
INBOX_DIR = ROOT / "inbox"
QUARANTINE_DIR = ROOT / "quarantine"
PROCESSED_DIR = ROOT / "processed"
EVALS_DIR = ROOT / "evals"
POLL_SECONDS = int(os.environ.get("LIBRARIAN_POLL_SECONDS", "10"))
DOCLING_URL = os.environ.get("LIBRARIAN_DOCLING_URL", "http://127.0.0.1:5001")
EMBEDDER_URL = os.environ.get("LIBRARIAN_EMBEDDER_URL", "http://127.0.0.1:8083")
