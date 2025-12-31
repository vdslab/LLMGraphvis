from functools import wraps
from app.core import database

def execute_with_db(func):
    """
    Decorator to inject a database session into the function.
    The session is automatically closed after execution.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        db = database.SessionLocal()
        try:
            return func(db, *args, **kwargs)
        except Exception as e:
            # We can log here if needed, or just re-raise
            raise e
        finally:
            db.close()
    return wrapper
