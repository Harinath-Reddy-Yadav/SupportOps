import os
import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from supportops.config import settings
from supportops.database import Base, get_db
import supportops.models as models
from supportops.auth import hash_password, create_access_token
from supportops.main import app

os.environ["SECRET_KEY"] = "test-secret-key-123"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

pytest_plugins = ["anyio"]

# ----------------- Set anyio backend --------------------
@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


# ----------------- Test Engine Creation -----------------
@pytest.fixture(scope="session")
def test_engine():
    engine = create_async_engine(
        settings.test_database_url.get_secret_value(),
        echo=False,
        poolclass=NullPool
    )

    return engine


# ----------------- Permanent Setup (Roles, Lookups, Admin & Manager) -----------------
@pytest.fixture(scope="session")
async def setup_database(test_engine):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(bind=test_engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session() as session:
        # 1. Seed Roles
        roles = [
            models.Role(name="user", description="Customer/User Role"),
            models.Role(name="agent", description="Agent Role"),
            models.Role(name="manager", description="Manager Role"),
            models.Role(name="admin", description="Admin Role"),
        ]

        # 2. Seed Statuses (Matches TicketStatusEnum)
        statuses = [
            models.Status(name="New", description="New ticket"),
            models.Status(name="Assigned", description="Ticket assigned"),
            models.Status(name="In Progress", description="In progress"),
            models.Status(name="On Hold", description="On hold"),
            models.Status(name="Resolved", description="Resolved"),
            models.Status(name="Closed", description="Closed"),
            models.Status(name="Reopened", description="Reopened"),
        ]

        # 3. Seed Priorities
        priorities = [
            models.Priority(name="Low", description="Low priority"),
            models.Priority(name="Medium", description="Medium priority"),
            models.Priority(name="High", description="High priority"),
            models.Priority(name="Critical", description="Critical priority"),
        ]

        # 4. Seed Categories
        categories = [
            models.Category(name="General", description="General inquiries"),
            models.Category(name="Technical", description="Technical issues"),
        ]

        # 5. Permanent Seeded Admin (ID=1) & Manager (ID=2)
        admin = models.User(
            username="default_admin",
            first_name="System",
            last_name="Admin",
            email="admin@admin.com",
            password_hash=hash_password("adminpassword123"),
            role_id=4,  # Admin role
            is_active=True
        )

        manager = models.User(
            username="default_manager",
            first_name="Default",
            last_name="Manager",
            email="manager@manager.com",
            password_hash=hash_password("managerpassword123"),
            role_id=3,  # Manager role
            is_active=True
        )

        session.add_all(roles + statuses + priorities + categories + [admin, manager])
        await session.commit()

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


# ----------------- Savepoint Transaction Per Test -----------------
@pytest.fixture(scope="function")
async def db_transaction(setup_database, test_engine):
    async with test_engine.begin() as conn:
        #Manullay creating the connection    
        conn = await test_engine.connect()

        #Begin transcation
        transaction = await conn.begin()

        test_async_session = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint"
        )
        async with test_async_session() as session:
            try:
                yield session
            except Exception as e:
                await transaction.rollback()
                raise e
            finally:
                await session.close()
                await transaction.rollback()
                await conn.close()


# ----------------- Test Client with DB Dependency Override -----------------
@pytest.fixture(scope="function")
async def client(db_transaction: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Override get_db to inject the test database transaction."""
    async def get_test_db():
        yield db_transaction

    app.dependency_overrides[get_db] = get_test_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ----------------- Auth Header & Tokens for Permanent Users -----------------
def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_token() -> str:
    """Returns access token for permanent admin (ID=1)."""
    return create_access_token({"sub": "1"})


@pytest.fixture(scope="session")
def manager_token() -> str:
    """Returns access token for permanent manager (ID=2)."""
    return create_access_token({"sub": "2"})


# ----------------- Helper Fixtures for Dynamic Test Data -----------------
def auth_header(token: str) -> dict:
    """Helper to generate Authorization header."""
    return {"Authorization": f"Bearer {token}"}


async def create_user(
    client: AsyncClient,
    username: str = "sample_user",
    first_name: str = "Sample",
    last_name: str = "User",
    email: str = "sample@example.com",
    password: str = "password123"
) -> dict:
    """Creates a customer user via the public API."""
    res = await client.post(
        "/api/v1/users",
        json={
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password
        }
    )
    assert res.status_code == 201, f"Failed to create user: {res.text}"
    assert res.json().get("username") == username, f"Username mismatch: {res.json().get('username')} != {username}"
    assert res.json().get("role_id") == None, f"Role ID mismatch: {res.json().get('role_id')} != None"
    assert res.json().get("email") == email, f"Email mismatch: {res.json().get('email')} != {email}"
    assert res.json().get("full_name") == f"{first_name} {last_name}", f"Full name mismatch: {res.json().get('full_name')} != {first_name} {last_name}"
    return res.json()


async def login_user(
    client: AsyncClient,
    username: str = None,
    email: str = None,
    password: str = "password123"
) -> dict:
    """Logs in a user via the API and returns token dict."""
    login_id = username or email
    res = await client.post(
        "/api/auth/token",
        data={"username": login_id, "password": password}
    )
    assert res.status_code == 200, f"Failed to login: {res.text}"
    return res.json()


async def create_admin_manually(
    db: AsyncSession,
    username: str = "admin_user",
    first_name: str = "Admin",
    last_name: str = "User",
    email: str = "admin_user@example.com",
    password: str = "password123",
    role_id: int = 4,
    is_active: bool = True
) -> models.User:
    """Directly inserts an admin user into the test database transaction."""
    admin = models.User(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=hash_password(password),
        role_id=role_id,
        is_active=is_active
    )
    db.add(admin)
    await db.flush()
    await db.refresh(admin)
    return admin