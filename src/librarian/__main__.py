from sqlalchemy import text

from librarian.db import engine


def main() -> None:
    with engine.connect() as conn:
        pg = conn.execute(text("SHOW server_version")).scalar_one()
        vector = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one_or_none()
    print(f"postgres {pg}, pgvector {vector or 'not installed'}")


if __name__ == "__main__":
    main()
