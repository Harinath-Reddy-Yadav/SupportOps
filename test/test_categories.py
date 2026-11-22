import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from test.conftest import auth_header, create_admin_manually, create_user, login_user

# =========================================================================
# 1. Categories - List & Read
# =========================================================================

@pytest.mark.anyio
async def test_get_all_categories_success(client: AsyncClient):
    """Any authenticated user can list categories (seeded with General & Technical)."""
    user = await create_user(client, username="cat_viewer", email="cat_view@example.com")
    token = (await login_user(client, username="cat_viewer", password="password123"))["access_token"]

    response = await client.get("/api/v1/categories", headers=auth_header(token))
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    category_names = [c["name"].lower() for c in data]
    assert "general" in category_names
    assert "technical" in category_names


@pytest.mark.anyio
async def test_get_category_by_id_success(client: AsyncClient):
    """Fetch category details by its ID."""
    user = await create_user(client, username="cat_by_id_user", email="cat_by_id@example.com")
    token = (await login_user(client, username="cat_by_id_user", password="password123"))["access_token"]

    response = await client.get("/api/v1/categories/1", headers=auth_header(token))
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"].lower() == "general"


@pytest.mark.anyio
async def test_get_category_by_id_not_found(client: AsyncClient):
    """Getting non-existent category returns 404."""
    user = await create_user(client, username="cat_404_user", email="cat_404@example.com")
    token = (await login_user(client, username="cat_404_user", password="password123"))["access_token"]

    response = await client.get("/api/v1/categories/9999", headers=auth_header(token))
    assert response.status_code == 404
    assert response.json()["detail"] == "Category not found"


# =========================================================================
# 2. Categories - Admin Create & Restrictions
# =========================================================================

# ----------------- 2. Categories - Admin Create & Restrictions -----------------

@pytest.mark.anyio
async def test_create_category_admin_success(client: AsyncClient, db_transaction: AsyncSession):
    """Admin can create a new category."""
    admin = await create_admin_manually(db_transaction, username="admin_cat_creator", email="admin_cat_create@supportops.com")
    token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    # Using a unique category name so it never collides across test runs
    payload = {"name": "Billing Ops Unique", "description": "Payment and billing tickets"}
    response = await client.post("/api/v1/categories", json=payload, headers=auth_header(token))
    assert response.status_code == 201, f"Failed with {response.status_code}: {response.text}"
    data = response.json()
    assert data["name"] == "billing ops unique"
    assert data["description"] == payload["description"]
    assert "id" in data


@pytest.mark.anyio
async def test_create_category_duplicate_name_fails(client: AsyncClient, db_transaction: AsyncSession):
    """Creating a category with a duplicate name returns 409 Conflict."""
    admin = await create_admin_manually(db_transaction, username="admin_cat_dup", email="admin_cat_dup@supportops.com")
    token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    # 1. First create a unique category
    create_first = await client.post("/api/v1/categories", json={"name": "unique_dup_check", "description": "Billing"}, headers=auth_header(token))
    assert create_first.status_code == 201

    # 2. Try creating the exact same name again
    response = await client.post("/api/v1/categories", json={"name": "unique_dup_check", "description": "Duplicate billing"}, headers=auth_header(token))
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.anyio
async def test_create_category_forbidden_for_regular_user(client: AsyncClient):
    """Regular customers are forbidden from creating categories (403 Forbidden)."""
    user = await create_user(client, username="normal_user_cat", email="user_cat@example.com")
    token = (await login_user(client, username="normal_user_cat", password="password123"))["access_token"]

    payload = {"name": "Hacked Category", "description": "Should fail"}
    response = await client.post("/api/v1/categories", json=payload, headers=auth_header(token))
    assert response.status_code == 403


# =========================================================================
# 3. Categories - Update & Delete
# =========================================================================

@pytest.mark.anyio
async def test_update_category_admin_success(client: AsyncClient, db_transaction: AsyncSession):
    """Admin can update an existing category."""
    admin = await create_admin_manually(db_transaction, username="admin_cat_upd", email="admin_cat_upd@supportops.com")
    token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    # 1. Create category
    create_res = await client.post("/api/v1/categories", json={
        "name": "Hardware",
        "description": "Hardware problems"
    }, headers=auth_header(token))
    assert create_res.status_code == 201
    cat_id = create_res.json()["id"]

    # 2. Update category
    upd_res = await client.put(f"/api/v1/categories/{cat_id}", json={
        "name": "Hardware Issues",
        "description": "Desktop and laptop hardware issues"
    }, headers=auth_header(token))
    assert upd_res.status_code == 200
    assert upd_res.json()["name"] == "hardware issues"


@pytest.mark.anyio
async def test_delete_category_admin_success(client: AsyncClient, db_transaction: AsyncSession):
    """Admin can delete a category that has no active tickets."""
    admin = await create_admin_manually(db_transaction, username="admin_cat_del", email="admin_cat_del@supportops.com")
    token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    # 1. Create a category
    create_res = await client.post("/api/v1/categories", json={
        "name": "Temporary",
        "description": "To be deleted"
    }, headers=auth_header(token))
    cat_id = create_res.json()["id"]

    # 2. Delete it
    del_res = await client.delete(f"/api/v1/categories/{cat_id}", headers=auth_header(token))
    assert del_res.status_code == 200

    # 3. Verify it is gone
    get_res = await client.get(f"/api/v1/categories/{cat_id}", headers=auth_header(token))
    assert get_res.status_code == 404
