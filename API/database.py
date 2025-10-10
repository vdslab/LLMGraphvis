from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment variable or use default
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@db:5432/graphvis")

# Create SQLAlchemy engine with specific connection parameters
if DATABASE_URL.startswith("sqlite"):
    # SQLite doesn't support connect_timeout parameter
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # 接続前にpingを実行し、接続が生きているか確認
        pool_recycle=3600,   # 1時間ごとに接続をリサイクル
    )
else:
    # PostgreSQL and other databases with connect_timeout support
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # 接続前にpingを実行し、接続が生きているか確認
        pool_recycle=3600,   # 1時間ごとに接続をリサイクル
        connect_args={
            "connect_timeout": 10,  # 接続タイムアウトを10秒に設定
        }
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create base class for models
Base = declarative_base()

# Function to get database session


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
