import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

load_dotenv()

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "graphvis")

SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Row locks are short by construction (never held across an await; ADR 0038), so
# a wait this long means something broke that rule. Failing beats freezing.
LOCK_TIMEOUT = "5s"


def for_update(db, query):
    """`query.with_for_update()`, bounded by LOCK_TIMEOUT on Postgres.

    Use for every row lock. The lock lasts until the session commits or rolls
    back; do that before the next await, or a waiter on the event loop freezes
    the whole process (ADR 0038).
    """
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
    return query.with_for_update()


def is_lock_timeout(exc: Exception) -> bool:
    return isinstance(exc, OperationalError) and (
        getattr(exc.orig, "pgcode", None) == "55P03"  # lock_not_available
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
