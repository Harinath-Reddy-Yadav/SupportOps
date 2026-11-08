from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from supportops.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.get_secret_value().startswith("sqlite") else {}

engine = create_async_engine(
    settings.database_url.get_secret_value(),
    connect_args=connect_args,
)

SessionLocal = async_sessionmaker(
                                    bind=engine,
                                    expire_on_commit=False, 
                                    class_=AsyncSession,
                                    autoflush=False
                                )

class Base(DeclarativeBase):
    pass

async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()