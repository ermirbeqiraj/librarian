import logging

from alembic import context
from sqlalchemy import create_engine, pool

import librarian.models  # noqa: F401
from librarian.config import DATABASE_URL
from librarian.db import Base

logging.basicConfig(format="%(levelname)-5.5s [%(name)s] %(message)s")
logging.getLogger("alembic").setLevel(logging.INFO)

if context.is_offline_mode():
    context.configure(url=DATABASE_URL, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(DATABASE_URL, poolclass=pool.NullPool).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
