from urllib import response
import pytest
from httpx import AsyncClient
from test.conftest import auth_header, create_user, create_admin_manually, login_user
from sqlalchemy.ext.asyncio import AsyncSession

# =========================================================================
# 1. Success Cases Testing
# =========================================================================

#------------------ create user ------------------------------------------
@pytest.mark.anyio
async def test_create_user_success(client: AsyncClient):
    payload = {
        "username": "customer_sam",
        "first_name": "Sam",
        "last_name": "Smith",
        "email": "sam@example.com",
        "password": "Password123"
    }
    user = await create_user(client,**payload)

    #login with user created
    token_res= await login_user(client, username="customer_sam", password="Password123")
    token = token_res["access_token"]
    response = await client.get("/api/auth/me", headers=auth_header(token))
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "customer_sam"
    assert data["email"] == "sam@example.com"
    assert data["full_name"] == "Sam Smith"
    assert data["role_name"] == "user"
    assert "password" not in data
    assert "password_hash" not in data


# =========================================================================
# Admin Creating Users with Different Roles
# =========================================================================

# ----------------- 1. Admin creates Customer User (role_id=1) -----------------
@pytest.mark.anyio
async def test_admin_create_customer_user_success(client: AsyncClient, db_transaction: AsyncSession):
    # 1. Setup admin
    admin = await create_admin_manually(db_transaction, username="admin_customer_creator", email="admin_cust@supportops.com")
    token_res = await login_user(client, username=admin.username, password="password123")
    headers = auth_header(token_res["access_token"])

    # 2. Admin creates customer
    payload = {
        "username": "support_user_01",
        "first_name": "User",
        "last_name": "One",
        "email": "user1@supportops.com",
        "password": "Password123",
        "role_id": 1
    }
    response = await client.post("/api/v1/users/admin", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "support_user_01"
    assert data["role_name"] == "user"
    assert "password" not in data
    assert "password_hash" not in data


# ----------------- 2. Admin creates Agent User (role_id=2) -----------------
@pytest.mark.anyio
async def test_admin_create_agent_user_success(client: AsyncClient, db_transaction: AsyncSession):
    # 1. Setup admin
    admin = await create_admin_manually(db_transaction, username="admin_agent_creator", email="admin_agent@supportops.com")
    token_res = await login_user(client, username=admin.username, password="password123")
    headers = auth_header(token_res["access_token"])

    # 2. Admin creates agent
    payload = {
        "username": "support_agent_01",
        "first_name": "Agent",
        "last_name": "One",
        "email": "agent1@supportops.com",
        "password": "Password123",
        "role_id": 2
    }
    response = await client.post("/api/v1/users/admin", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "support_agent_01"
    assert data["role_name"] == "agent"
    assert "password" not in data
    assert "password_hash" not in data


# ----------------- 3. Admin creates Manager User (role_id=3) -----------------
@pytest.mark.anyio
async def test_admin_create_manager_user_success(client: AsyncClient, db_transaction: AsyncSession):
    # 1. Setup admin
    admin = await create_admin_manually(db_transaction, username="admin_manager_creator", email="admin_mgr@supportops.com")
    token_res = await login_user(client, username=admin.username, password="password123")
    headers = auth_header(token_res["access_token"])

    # 2. Admin creates manager
    payload = {
        "username": "support_manager_01",
        "first_name": "Manager",
        "last_name": "One",
        "email": "manager1@supportops.com",
        "password": "Password123",
        "role_id": 3
    }
    response = await client.post("/api/v1/users/admin", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "support_manager_01"
    assert data["role_name"] == "manager"
    assert "password" not in data
    assert "password_hash" not in data


# ----------------- 4. Admin creates another Admin & new Admin performs Admin tasks -----------------
@pytest.mark.anyio
async def test_admin_create_admin_user_success(client: AsyncClient, db_transaction: AsyncSession):
    # 1. First admin setup
    admin1 = await create_admin_manually(db_transaction, username="admin_super_creator", email="admin_super@supportops.com")
    token_res1 = await login_user(client, username=admin1.username, password="password123")
    headers1 = auth_header(token_res1["access_token"])

    # 2. Admin 1 creates Admin 2 via API
    payload = {
        "username": "support_admin_02",
        "first_name": "Admin",
        "last_name": "Two",
        "email": "admin2@supportops.com",
        "password": "Password123",
        "role_id": 4
    }
    create_res = await client.post("/api/v1/users/admin", json=payload, headers=headers1)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["username"] == "support_admin_02"
    assert data["role_name"] == "admin"
    assert "password" not in data
    assert "password_hash" not in data

    # 3. New Admin (Admin 2) logs in via API
    token_res2 = await login_user(client, username="support_admin_02", password="Password123")
    assert "access_token" in token_res2
    headers2 = auth_header(token_res2["access_token"])

    # 4. Verify Admin 2 can access /api/auth/me and has admin role
    me_res = await client.get("/api/auth/me", headers=headers2)
    assert me_res.status_code == 200
    assert me_res.json()["role_name"] == "admin"

    # 5. Verify Admin 2 can perform admin activities: creating a new Manager user
    manager_payload = {
        "username": "manager_by_admin2",
        "first_name": "Branch",
        "last_name": "Manager",
        "email": "branch_mgr@supportops.com",
        "password": "Password123",
        "role_id": 3
    }
    mgr_create_res = await client.post("/api/v1/users/admin", json=manager_payload, headers=headers2)
    assert mgr_create_res.status_code == 201
    mgr_data = mgr_create_res.json()
    assert mgr_data["username"] == "manager_by_admin2"
    assert mgr_data["role_name"] == "manager"

# =========================================================================
# 2. Manager Creating Users & Restrictions
# =========================================================================

# ----------------- 1. Manager creates Customer User (role_id=1) -----------------
@pytest.mark.anyio
async def test_manager_create_customer_user_success(client: AsyncClient, db_transaction: AsyncSession):
    """Manager creates a regular customer user via /api/v1/users/manager; manager_id is auto-assigned."""
    # 1. Setup manager via admin
    manager = await create_admin_manually(db_transaction, username="admin_for_cust_mgr", email="admin_cust_mgr@supportops.com")
    manager_token = (await login_user(client, username=manager.username, password="password123"))["access_token"]

    # 2. Manager creates customer user
    cust_res = await client.post("/api/v1/users/manager", json={
        "username": "managed_customer_01",
        "first_name": "Managed",
        "last_name": "Customer",
        "email": "managed_cust@supportops.com",
        "password": "Password123",
        "role_id": 1
    }, headers=auth_header(manager_token))
    assert cust_res.status_code == 201
    data = cust_res.json()
    assert data["username"] == "managed_customer_01"
    assert data["role_name"] == "user"
    assert data["manager_id"] == manager.id
    assert "password" not in data
    assert "password_hash" not in data

    # 3. Verify created customer can log in
    cust_token_res = await login_user(client, username="managed_customer_01", password="Password123")
    assert "access_token" in cust_token_res

# ----------------- 2. Manager creates manager (role_id=3) -----------------
@pytest.mark.anyio
async def test_manager_create_manager_success(client: AsyncClient, db_transaction: AsyncSession):
    """Manager creates a manager user via /api/v1/users/manager; manager_id is auto-assigned."""
    # 1. Setup manager
    manager = await create_admin_manually(db_transaction, username="admin_for_mgr", email="admin_mgr_test@supportops.com")
    manager_token = (await login_user(client, username=manager.username, password="password123"))["access_token"]
    
    mgr_res = await client.post("/api/v1/users/manager", json={
        "username": "dept_manager",
        "first_name": "Dept",
        "last_name": "Manager",
        "email": "dept_mgr@supportops.com",
        "password": "Password123",
        "role_id": 3
    }, headers=auth_header(manager_token))
    assert mgr_res.status_code == 201
    data = mgr_res.json()
    assert data["username"] == "dept_manager"
    assert data["role_name"] == "manager"
    assert data["manager_id"] == manager.id
    assert "password" not in data
    assert "password_hash" not in data

    # 2. Manager logs in
    mgr_token = (await login_user(client, username="dept_manager", password="Password123"))["access_token"]

    # 3. Manager creates agent
    agent_res = await client.post("/api/v1/users/manager", json={
        "username": "subordinate_agent",
        "first_name": "Sub",
        "last_name": "Agent",
        "email": "sub_agent@supportops.com",
        "password": "Password123",
        "role_id": 2
    }, headers=auth_header(mgr_token))
    assert agent_res.status_code == 201
    data = agent_res.json()
    assert data["role_name"] == "agent"
    assert data["manager_id"] == mgr_res.json()["id"]

# ----------------- 3. Manager Admin creation should fail (role_id=4) -----------------
@pytest.mark.anyio
async def test_manager_cannot_create_admin_user(client: AsyncClient, db_transaction: AsyncSession):
    """Security rule: Managers must get 403 Forbidden when trying to create an Admin account."""
    manager = await create_admin_manually(db_transaction, username="admin_mgr_rule", email="admin_mgr_rule@supportops.com")
    manager_token = (await login_user(client, username=manager.username, password="password123"))["access_token"]
    
    await client.post("/api/v1/users/admin", json={
        "username": "rule_manager",
        "first_name": "Rule",
        "last_name": "Manager",
        "email": "rule_mgr@supportops.com",
        "password": "Password123",
        "role_id": 3
    }, headers=auth_header(manager_token))

    mgr_token = (await login_user(client, username="rule_manager", password="Password123"))["access_token"]

    # Manager attempts to create an admin (role_id=4)
    response = await client.post("/api/v1/users/manager", json={
        "username": "sneaky_admin",
        "first_name": "Sneaky",
        "last_name": "Admin",
        "email": "sneaky_admin@supportops.com",
        "password": "Password123",
        "role_id": 4
    }, headers=auth_header(mgr_token))
    assert response.status_code == 403
    assert "Managers are not allowed to create or assign Admin accounts" in response.json()["detail"]


# =========================================================================
# 3. Duplicate and Validation Failures
# =========================================================================

# ----------------- 1. Duplicate Email Failure -----------------
@pytest.mark.anyio
async def test_create_user_duplicate_email_fails(client: AsyncClient):
    """Creating a user with an already registered email must return 400."""
    await create_user(client, username="orig_user1", email="shared@example.com")

    # Try duplicate email
    dup_res = await client.post("/api/v1/users", json={
        "username": "diff_username",
        "first_name": "Diff",
        "last_name": "User",
        "email": "shared@example.com",
        "password": "Password123"
    })
    assert dup_res.status_code == 400
    assert "Email already exists" in dup_res.json()["detail"]

# ----------------- 2. Duplicate Username Failure -----------------
@pytest.mark.anyio
async def test_create_user_duplicate_username_fails(client: AsyncClient):
    """Creating a user with an already registered username must return 400."""
    await create_user(client, username="unique_uname", email="email1@example.com")

    # Try duplicate username
    dup_res = await client.post("/api/v1/users", json={
        "username": "unique_uname",
        "first_name": "Other",
        "last_name": "Person",
        "email": "email2@example.com",
        "password": "Password123"
    })
    assert dup_res.status_code == 400
    assert "User name already exists" in dup_res.json()["detail"]

# ----------------- 3. Invalid Role ID Failure for admin user -----------------
@pytest.mark.anyio
async def test_create_user_invalid_role_id_fails(client: AsyncClient, db_transaction: AsyncSession):
    """Providing a non-existent role_id must return 400."""
    admin = await create_admin_manually(db_transaction, username="admin_role_check", email="admin_check@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    response = await client.post("/api/v1/users/admin", json={
        "username": "invalid_role_user",
        "first_name": "Invalid",
        "last_name": "Role",
        "email": "invalid_role@supportops.com",
        "password": "Password123",
        "role_id": 9999  # Role does not exist
    }, headers=auth_header(admin_token))
    assert response.status_code == 400
    assert "Specified role_id does not exist" in response.json()["detail"]

# ----------------- 4. Invalid Role ID Failure for Manager -----------------
@pytest.mark.anyio
async def test_create_manager_invalid_role_id_fails(client: AsyncClient, db_transaction: AsyncSession):
    """Providing a non-existent role_id must return 400."""
    admin = await create_admin_manually(db_transaction, username="admin_role_check", email="admin_check@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    response = await client.post("/api/v1/users/manager", json={
        "username": "invalid_role_user",
        "first_name": "Invalid",
        "last_name": "Role",
        "email": "invalid_role@supportops.com",
        "password": "Password123",
        "role_id": 9999  # Role does not exist
    }, headers=auth_header(admin_token))
    assert response.status_code == 400
    assert "Specified role_id does not exist" in response.json()["detail"]

# ----------------- 5. Customer cannot access admin user creation -----------------
@pytest.mark.anyio
async def test_customer_cannot_access_admin_user_creation(client: AsyncClient):
    """Regular customers must be rejected with 403 Forbidden when calling /api/v1/users/admin."""
    await create_user(client, username="plain_cust", email="plain_cust@example.com")
    cust_token = (await login_user(client, username="plain_cust", password="password123"))["access_token"]

    response = await client.post("/api/v1/users/admin", json={
        "username": "forbidden_agent",
        "first_name": "Test",
        "last_name": "Test",
        "email": "forbidden_agent@example.com",
        "password": "Password123",
        "role_id": 2
    }, headers=auth_header(cust_token))
    assert response.status_code == 403


# =========================================================================
# 4. Read User Endpoints (GET)
# =========================================================================

# ----------------- 1. Admin can list all users -----------------
@pytest.mark.anyio
async def test_admin_get_all_users(client: AsyncClient, db_transaction: AsyncSession):
    """Admin can list all users in the system."""
    admin = await create_admin_manually(db_transaction, username="admin_list_users", email="admin_list@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    response = await client.get("/api/v1/users/admin/users", headers=auth_header(admin_token))
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

# ----------------- 2. Any authenticated user can retrieve user details by ID -----------------
@pytest.mark.anyio
async def test_get_user_by_id_success(client: AsyncClient):
    """Any authenticated user can retrieve user details by ID."""
    created = await create_user(client, username="user_lookup", email="lookup@example.com")
    token = (await login_user(client, username="user_lookup", password="password123"))["access_token"]

    response = await client.get(f"/api/v1/users/{created['id']}", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["username"] == "user_lookup"

# ----------------- 3. Manager can list all the users tagged to him ----------------------
@pytest.mark.anyio
async def test_manager_get_users(client: AsyncClient, db_transaction: AsyncSession):
    """Manager can list all users tagged to him."""
    #1. Create admin user
    admin = await create_admin_manually(db_transaction, username="admin_super_creator", email="admin_super_creator@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]
    admin_header = auth_header(admin_token)
    
    #2. Admin creates manager using auth_header
    response = await client.post("/api/v1/users/manager", json={
        "username": "test_manager",
        "first_name": "test",
        "last_name": "manager",
        "email": "test_manager@supportops.com",
        "password": "Password1993",
        "role_id": 3
    }, headers=admin_header)
    assert response.status_code == 201
    manager_id = response.json()["id"]

    #3. Manager logins
    manager_token = (await login_user(client, username="test_manager", password="Password1993"))["access_token"]
    manager_header = auth_header(manager_token)

    # 4. Manager creates 3 users (e.g. Agents with role_id=2 or Customers with role_id=1) under him
    user1_response = await client.post("/api/v1/users/manager", json={
        "username": "test_user1",
        "first_name": "test",
        "last_name": "user1",
        "email": "test_user1@supportops.com",
        "password": "Password1993",
        "role_id": 2  # Agent role
    }, headers=manager_header)
    assert user1_response.status_code == 201

    user2_response = await client.post("/api/v1/users/manager", json={
        "username": "test_user2",
        "first_name": "test",
        "last_name": "user2",
        "email": "test_user2@supportops.com",
        "password": "Password1993",
        "role_id": 2  # Agent role
    }, headers=manager_header)
    assert user2_response.status_code == 201

    user3_response = await client.post("/api/v1/users/manager", json={
        "username": "test_user3",
        "first_name": "test",
        "last_name": "user3",
        "email": "test_user3@supportops.com",
        "password": "Password1993",
        "role_id": 1  # Customer role
    }, headers=manager_header)
    assert user3_response.status_code == 201
    
    # 5. Manager lists users under him and checks if the 3 users are listed
    response = await client.get("/api/v1/users/manager/users", headers=manager_header)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    
# ----------------- 4. Requesting a non-existent user_id must return 404 -----------------
@pytest.mark.anyio
async def test_get_user_by_id_not_found(client: AsyncClient):
    """Requesting a non-existent user_id must return 404."""
    created = await create_user(client, username="caller_user", email="caller@example.com")
    token = (await login_user(client, username="caller_user", password="password123"))["access_token"]

    response = await client.get("/api/v1/users/99999", headers=auth_header(token))
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


# =========================================================================
# 5. Update User Profile & Role (PUT)
# =========================================================================
# ----------------- 1. User can update there profile -----------------
@pytest.mark.anyio
async def test_user_self_update_details(client: AsyncClient):
    """Users can update their own profile details."""
    created = await create_user(client, username="update_me", email="updateme@example.com")
    token = (await login_user(client, username="update_me", password="password123"))["access_token"]

    response = await client.put(f"/api/v1/users/{created['id']}", json={
        "first_name": "UpdatedFirst",
        "last_name": "UpdatedLast"
    }, headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["full_name"] == "UpdatedFirst UpdatedLast"

# ----------------- 2. User can update their password and login with new password -----------------
@pytest.mark.anyio
async def test_user_self_update_password(client: AsyncClient):
    """Users can update their own password via PUT /api/v1/users/{user_id}."""
    created = await create_user(client, username="update_password", email="update_password@example.com")
    token = (await login_user(client, username="update_password", password="password123"))["access_token"]

    # 1. Update password using PUT /api/v1/users/{user_id}
    response = await client.put(f"/api/v1/users/{created['id']}", json={
        "password": "newpassword123"
    }, headers=auth_header(token))
    assert response.status_code == 200

    # 2. Login with new password succeeds
    login_new = await login_user(client, username="update_password", password="newpassword123")
    assert "access_token" in login_new

    # 3. Login with old password fails (401 Unauthorized)
    old_res = await client.post("/api/auth/token", data={
        "username": "update_password",
        "password": "password123"
    })
    assert old_res.status_code == 401

# ----------------- 3. User cannot update another user -----------------
@pytest.mark.anyio
async def test_user_cannot_update_another_user(client: AsyncClient):
    """A customer cannot edit another user's profile (403 Forbidden)."""
    user_a = await create_user(client, username="user_victim", email="victim@example.com")
    await create_user(client, username="user_attacker", email="attacker@example.com")
    attacker_token = (await login_user(client, username="user_attacker", password="password123"))["access_token"]

    response = await client.put(f"/api/v1/users/{user_a['id']}", json={
        "first_name": "Hacked"
    }, headers=auth_header(attacker_token))
    assert response.status_code == 403
    assert "You are not authorized" in response.json()["detail"]

# ----------------- 4. Admin can update any user's role -----------------
@pytest.mark.anyio
async def test_admin_can_update_user_role(client: AsyncClient, db_transaction: AsyncSession):
    """Admin can promote/update any user's role."""
    admin = await create_admin_manually(db_transaction, username="admin_role_updater", email="admin_role_up@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    target = await create_user(client, username="promotee", email="promotee@example.com")

    # Promote to Agent (role_id=2)
    response = await client.put(f"/api/v1/users/{target['id']}/role", json={
        "role_id": 2
    }, headers=auth_header(admin_token))
    assert response.status_code == 200
    assert response.json()["role_name"] == "agent"

# ----------------- 5. Manager cannot promote someone to Admin -----------------
@pytest.mark.anyio
async def test_manager_cannot_promote_to_admin(client: AsyncClient, db_transaction: AsyncSession):
    """Security rule: Managers cannot promote someone to Admin (role_id=4)."""
    admin = await create_admin_manually(db_transaction, username="admin_setup_mgr2", email="admin_mgr2@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    await client.post("/api/v1/users/admin", json={
        "username": "manager_promoter",
        "first_name": "Mgr",
        "last_name": "Promoter",
        "email": "mgr_promoter@supportops.com",
        "password": "Password123",
        "role_id": 3
    }, headers=auth_header(admin_token))

    mgr_token = (await login_user(client, username="manager_promoter", password="Password123"))["access_token"]
    target = await create_user(client, username="user_target", email="target@example.com")

    # Manager attempts to promote target to Admin (role_id=4)
    response = await client.put(f"/api/v1/users/{target['id']}/role", json={
        "role_id": 4
    }, headers=auth_header(mgr_token))
    assert response.status_code == 403
    assert "Managers are not allowed to create or assign Admin accounts" in response.json()["detail"]


# =========================================================================
# 6. Soft Delete User (DELETE)
# =========================================================================
# ----------------- 1. Admin can delete a user -----------------
@pytest.mark.anyio
async def test_admin_delete_user_success(client: AsyncClient, db_transaction: AsyncSession):
    """Admin successfully soft deletes a user."""
    admin = await create_admin_manually(db_transaction, username="admin_deleter", email="admin_deleter@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    target = await create_user(client, username="to_be_deleted", email="delete_me@example.com")

    # Delete user
    delete_res = await client.delete(f"/api/v1/users/{target['id']}", headers=auth_header(admin_token))
    assert delete_res.status_code == 200
    assert delete_res.json()["message"] == "User deleted successfully"

    # Attempting to delete again returns 404 (already deleted)
    second_delete = await client.delete(f"/api/v1/users/{target['id']}", headers=auth_header(admin_token))
    assert second_delete.status_code == 404


# ----------------- 2. Manager can delete user -----------------
@pytest.mark.anyio
async def test_manager_delete_user_success(client: AsyncClient, db_transaction: AsyncSession):
    """Manager successfully soft deletes a user."""
    # 1. Create admin user
    admin = await create_admin_manually(db_transaction, username="admin_deleter", email="admin_deleter@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    #Admin creates the manager user
    await client.post("/api/v1/users/admin", json={
        "username": "manager_deleter",
        "first_name": "Destroyer",
        "last_name": "Mgr",
        "email": "mgr_destroyer@supportops.com",
        "password": "Password123",
        "role_id": 3
    }, headers=auth_header(admin_token))

    mgr_token = (await login_user(client, username="manager_deleter", password="Password123"))["access_token"]

    # 2. Create target user
    target = await create_user(client, username="to_be_deleted", email="delete_me@example.com")

    # 3.Manager deletes the user
    delete_res = await client.delete(f"/api/v1/users/{target['id']}", headers=auth_header(mgr_token))
    assert delete_res.status_code == 200
    assert delete_res.json()["message"] == "User deleted successfully"

    # Attempting to delete again returns 404 (already deleted)
    second_delete = await client.delete(f"/api/v1/users/{target['id']}", headers=auth_header(admin_token))
    assert second_delete.status_code == 404

# ----------------- 3. Manager cannot delete an Admin -----------------
@pytest.mark.anyio
async def test_manager_cannot_delete_admin(client: AsyncClient, db_transaction: AsyncSession):
    """Security rule: Managers cannot delete an Admin account."""
    admin = await create_admin_manually(db_transaction, username="admin_protected", email="protected_admin@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    await client.post("/api/v1/users/admin", json={
        "username": "manager_destroyer",
        "first_name": "Destroyer",
        "last_name": "Mgr",
        "email": "mgr_destroyer@supportops.com",
        "password": "Password123",
        "role_id": 3
    }, headers=auth_header(admin_token))

    mgr_token = (await login_user(client, username="manager_destroyer", password="Password123"))["access_token"]

    # Manager attempts to delete the admin
    response = await client.delete(f"/api/v1/users/{admin.id}", headers=auth_header(mgr_token))
    assert response.status_code == 403
    assert "Managers are not allowed to delete Admin or Manager accounts" in response.json()["detail"]