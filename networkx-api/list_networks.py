from app.core.database import SessionLocal
from common import models

db = SessionLocal()
networks = db.query(models.Network).all()
for n in networks:
    print(f"ID: {n.id}, Name: {n.name}")
db.close()
