import uvicorn

from librarian.config import SERVE_HOST, SERVE_PORT
from librarian.serve.server import app


def main() -> None:
    uvicorn.run(app(), host=SERVE_HOST, port=SERVE_PORT)


if __name__ == "__main__":
    main()
