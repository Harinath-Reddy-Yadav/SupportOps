from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from supportops.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.get_secret_value().startswith("sqlite") else {}

engine = create_engine(
    settings.database_url.get_secret_value(),
    connect_args=connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
