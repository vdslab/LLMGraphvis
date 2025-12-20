import logging

from app.core.database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    logger.info("Creating database tables...")
    try:
        # Import models to ensure they are registered with Base
        # (Already imported at top level)
        # Check registered tables
        logger.info(f"Registered tables: {list(Base.metadata.tables.keys())}")

        Base.metadata.create_all(bind=engine)
        logger.info("Tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")


if __name__ == "__main__":
    init_db()
