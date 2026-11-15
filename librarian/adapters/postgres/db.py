import atexit

import simplejson
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


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


def sessions(url: str) -> sessionmaker[Session]:
    """Sessions on one engine, JSON numbers as Decimal so amounts stay exact."""
    engine = create_engine(
        url,
        json_serializer=lambda o: simplejson.dumps(
            o, use_decimal=True, default=lambda d: d.isoformat()
        ),
        json_deserializer=lambda s: simplejson.loads(s, use_decimal=True),
    )
    atexit.register(engine.dispose)
    return sessionmaker(engine)
