import os
from pathlib import Path

DATABASE_URL = os.environ.get(
    "LIBRARIAN_DATABASE_URL", "postgresql+psycopg://librarian:librarian@127.0.0.1:5432/librarian"
)
# The SQL tool's read-only role; the default is the dev setup's.
READER_DATABASE_URL = os.environ.get(
    "LIBRARIAN_READER_DATABASE_URL",
    "postgresql+psycopg://librarian_reader:librarian_reader@127.0.0.1:5432/librarian",
)
# Holds inbox/, processed/, quarantine/, traces/, evals/ and context.md.
ROOT = Path(os.environ.get("LIBRARIAN_ROOT", Path.home() / ".local/share/librarian"))
DOCLING_URL = os.environ.get("LIBRARIAN_DOCLING_URL", "http://127.0.0.1:5001")
EMBEDDER_URL = os.environ.get("LIBRARIAN_EMBEDDER_URL", "http://127.0.0.1:8083")
AGENT_MODEL = os.environ.get("LIBRARIAN_AGENT_MODEL", "deepseek-v4-1-flash-1017")
TRACE_STORE = os.environ.get("LIBRARIAN_TRACE_STORE", "file")
FILE_URL = os.environ.get("LIBRARIAN_FILE_URL")
SERVE_HOST = os.environ.get("LIBRARIAN_SERVE_HOST", "127.0.0.1")
SERVE_PORT = int(os.environ.get("LIBRARIAN_SERVE_PORT", "8090"))
AUTH = os.environ.get("LIBRARIAN_AUTH")
BEARER_TOKEN = os.environ.get("LIBRARIAN_BEARER_TOKEN")
ACCESS_TEAM = os.environ.get("LIBRARIAN_ACCESS_TEAM")
ACCESS_AUD = os.environ.get("LIBRARIAN_ACCESS_AUD")
