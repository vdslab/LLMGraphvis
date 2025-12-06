
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load env from backend
load_dotenv("backend/.env")

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app import models
from app.core.database import SQLALCHEMY_DATABASE_URL

def verify():
    print(f"Connecting to {SQLALCHEMY_DATABASE_URL}")
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Simulate create_chat logic
        print("Creating Network with graphml_content...")
        network = models.Network(
            id=777,
            name="Test Backend Network",
            graphml_content="<graphml>TEST</graphml>"
        )
        db.add(network)
        db.commit()
        print("Network created successfully.")
        
        # Verify it exists
        n = db.query(models.Network).filter(models.Network.id == 777).first()
        if n and n.graphml_content == "<graphml>TEST</graphml>":
            print("Verification Successful: Network saved with content.")
        else:
            print("Verification Failed: Network not found or content mismatch.")
            
    except Exception as e:
        print(f"Verification Failed with Error: {e}")
    finally:
        # Cleanup
        try:
            db.execute(models.Network.__table__.delete().where(models.Network.id == 777))
            db.commit()
            print("Cleanup done.")
        except Exception as e:
            print(f"Cleanup failed: {e}")
        db.close()

if __name__ == "__main__":
    verify()
