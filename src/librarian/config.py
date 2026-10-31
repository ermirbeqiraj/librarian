import os
from pathlib import Path

DATABASE_URL = os.environ.get(
    "LIBRARIAN_DATABASE_URL",
    "postgresql+psycopg://librarian:librarian@127.0.0.1:5432/librarian",
)
# One root holds inbox/, quarantine/ and processed/; the evals read evals/ and write to
# learnings/. Dev keeps it out of Dropbox, so wiping Postgres and this folder resets everything.
ROOT = Path(os.environ.get("LIBRARIAN_ROOT", Path.home() / ".local/share/librarian"))
INBOX_DIR = ROOT / "inbox"
QUARANTINE_DIR = ROOT / "quarantine"
PROCESSED_DIR = ROOT / "processed"
EVALS_DIR = ROOT / "evals"
LEARNINGS_DIR = ROOT / "learnings"
POLL_SECONDS = int(os.environ.get("LIBRARIAN_POLL_SECONDS", "10"))
DOCLING_URL = os.environ.get("LIBRARIAN_DOCLING_URL", "http://127.0.0.1:5001")
EMBEDDER_URL = os.environ.get("LIBRARIAN_EMBEDDER_URL", "http://127.0.0.1:8083")
