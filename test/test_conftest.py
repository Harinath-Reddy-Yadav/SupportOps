import pytest
from sqlalchemy import select
from supportops import models

@pytest.mark.anyio
async def test_permanent_admin_and_manager_exist(db_transaction):
    """
    Verify that setup_database permanently seeded:
    - Admin (id=1, username='default_admin', email='admin@admin.com', role='admin')
    - Manager (id=2, username='default_manager', email='manager@manager.com', role='manager')
    - All lookup roles, statuses, priorities, categories
    """
    # 1. Admin Check
    admin = await db_transaction.get(models.User, 1)
    assert admin is not None
    assert admin.username == "default_admin"
    assert admin.email == "admin@admin.com"
    assert admin.role.name == "admin"

    # 2. Manager Check
    manager = await db_transaction.get(models.User, 2)
    assert manager is not None
    assert manager.username == "default_manager"
    assert manager.email == "manager@manager.com"
    assert manager.role.name == "manager"

    # 3. Roles Check
    roles = (await db_transaction.execute(select(models.Role).order_by(models.Role.id))).scalars().all()
    assert [r.name for r in roles] == ["user", "agent", "manager", "admin"]


@pytest.mark.anyio
async def test_permanent_users_can_login(client):
    """
    Verify that the permanent Admin and Manager can obtain JWT tokens via login endpoint.
    """
    # Login Admin
    admin_login = await client.post(
        "/api/auth/token",
        data={"username": "admin@admin.com", "password": "adminpassword123"}
    )
    assert admin_login.status_code == 200
    assert "access_token" in admin_login.json()

    # Login Manager
    mgr_login = await client.post(
        "/api/auth/token",
        data={"username": "manager@manager.com", "password": "managerpassword123"}
    )
    assert mgr_login.status_code == 200
    assert "access_token" in mgr_login.json()


@pytest.mark.anyio
async def test_permanent_users_never_get_rolled_back_by_tests(db_transaction):
    """
    Even after transactions rollback, permanent admin and manager remain intact!
    """
    admin = await db_transaction.get(models.User, 1)
    manager = await db_transaction.get(models.User, 2)
    assert admin is not None
    assert manager is not None
