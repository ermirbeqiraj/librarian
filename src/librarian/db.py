import atexit

import simplejson
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from librarian.config import DATABASE_URL


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
        }
    )


engine = create_engine(
    DATABASE_URL,
    echo=True,
    json_serializer=lambda o: simplejson.dumps(
        o, use_decimal=True, default=lambda d: d.isoformat()
    ),
    json_deserializer=lambda s: simplejson.loads(s, use_decimal=True),
)
atexit.register(engine.dispose)
Session = sessionmaker(engine)
