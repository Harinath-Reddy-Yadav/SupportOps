import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from test.conftest import auth_header, create_admin_manually, create_user, login_user

# =========================================================================
# 1. Ticket Creation Tests
# =========================================================================

@pytest.mark.anyio
async def test_create_ticket_success(client: AsyncClient):
    """Authenticated customer creates a new ticket with auto-generated ticket number and status NEW."""
    user = await create_user(client, username="tkt_cust_01", email="tkt_cust01@example.com")
    token = (await login_user(client, username="tkt_cust_01", password="password123"))["access_token"]
    headers = auth_header(token)

    payload = {
        "title": "Cannot log in to VPN",
        "description": "Getting timeout error 504 when attempting VPN connection.",
        "category_id": 1,
        "priority_id": 1
    }
    response = await client.post("/api/v1/tickets", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["ticket_number"].startswith("TKT")
    assert data["id"] is not None
    assert data["ticket_status"]["id"] == 1  # NEW
    assert data["requester"]["id"] == user["id"]


@pytest.mark.anyio
async def test_create_ticket_invalid_category_fails(client: AsyncClient):
    """Creating a ticket with non-existent category_id must return 400."""
    await create_user(client, username="tkt_bad_cat", email="bad_cat@example.com")
    token = (await login_user(client, username="tkt_bad_cat", password="password123"))["access_token"]

    payload = {
        "title": "Invalid Cat Ticket",
        "description": "Non-existent category",
        "category_id": 9999,
        "priority_id": 1
    }
    response = await client.post("/api/v1/tickets", json=payload, headers=auth_header(token))
    assert response.status_code == 400
    assert "Invalid reference values" in str(response.json())


@pytest.mark.anyio
async def test_create_ticket_invalid_priority_fails(client: AsyncClient):
    """Creating a ticket with non-existent priority_id must return 400."""
    await create_user(client, username="tkt_bad_pri", email="bad_pri@example.com")
    token = (await login_user(client, username="tkt_bad_pri", password="password123"))["access_token"]

    payload = {
        "title": "Invalid Priority Ticket",
        "description": "Non-existent priority",
        "category_id": 1,
        "priority_id": 9999
    }
    response = await client.post("/api/v1/tickets", json=payload, headers=auth_header(token))
    assert response.status_code == 400
    assert "Invalid reference values" in str(response.json())


# =========================================================================
# 2. Ticket Retrieval Tests (GET)
# =========================================================================

@pytest.mark.anyio
async def test_get_all_tickets_as_customer_isolation(client: AsyncClient):
    """Regular customers only see tickets that they requested, not other users' tickets."""
    user1 = await create_user(client, username="tkt_viewer1", email="viewer1@example.com")
    token1 = (await login_user(client, username="tkt_viewer1", password="password123"))["access_token"]

    user2 = await create_user(client, username="tkt_viewer2", email="viewer2@example.com")
    token2 = (await login_user(client, username="tkt_viewer2", password="password123"))["access_token"]

    # User 1 creates a ticket
    await client.post("/api/v1/tickets", json={
        "title": "User 1 Secret Ticket",
        "description": "Private ticket",
        "category_id": 1,
        "priority_id": 1
    }, headers=auth_header(token1))

    # User 2 lists tickets - should NOT see User 1's ticket
    res2 = await client.get("/api/v1/tickets", headers=auth_header(token2))
    assert res2.status_code == 200
    titles = [t["title"] for t in res2.json()]
    assert "User 1 Secret Ticket" not in titles


@pytest.mark.anyio
async def test_admin_get_all_tickets(client: AsyncClient, db_transaction: AsyncSession):
    """Admin sees all tickets created by all users."""
    admin = await create_admin_manually(db_transaction, username="admin_all_tkts", email="admin_all_tkts@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]

    # Customer creates ticket
    await create_user(client, username="cust_with_tkt", email="cust_tkt@example.com")
    cust_token = (await login_user(client, username="cust_with_tkt", password="password123"))["access_token"]
    await client.post("/api/v1/tickets", json={
        "title": "Global Issue",
        "description": "System down",
        "category_id": 1,
        "priority_id": 1
    }, headers=auth_header(cust_token))

    # Admin lists tickets
    admin_res = await client.get("/api/v1/tickets", headers=auth_header(admin_token))
    assert admin_res.status_code == 200
    titles = [t["title"] for t in admin_res.json()]
    assert "Global Issue" in titles


@pytest.mark.anyio
async def test_manager_get_subordinates_tickets_in_assigned(client: AsyncClient, db_transaction: AsyncSession):
    """Manager can see tickets assigned to themselves OR any direct subordinates via /api/v1/tickets/assigned."""
    admin = await create_admin_manually(db_transaction, username="admin_mgr_tkt_setup", email="admin_mgr_tkt@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]
    admin_headers = auth_header(admin_token)

    # 1. Admin creates Manager (role_id=3)
    mgr_res = await client.post("/api/v1/users/admin", json={
        "username": "lead_manager_01",
        "first_name": "Lead",
        "last_name": "Manager",
        "email": "lead_mgr@supportops.com",
        "password": "Password123",
        "role_id": 3
    }, headers=admin_headers)
    mgr_id = mgr_res.json()["id"]
    mgr_token = (await login_user(client, username="lead_manager_01", password="Password123"))["access_token"]
    mgr_headers = auth_header(mgr_token)

    # 2. Manager creates Agent reporting to them via /api/v1/users/manager
    agent_res = await client.post("/api/v1/users/manager", json={
        "username": "subordinate_agent_01",
        "first_name": "Subordinate",
        "last_name": "Agent",
        "email": "sub_agent@supportops.com",
        "password": "Password123",
        "role_id": 2
    }, headers=mgr_headers)
    agent_id = agent_res.json()["id"]

    # 3. Customer creates two tickets
    await create_user(client, username="customer_mgr_flow", email="cust_mgr_flow@example.com")
    cust_token = (await login_user(client, username="customer_mgr_flow", password="password123"))["access_token"]
    tkt1 = (await client.post("/api/v1/tickets", json={
        "title": "Subordinate Task",
        "description": "Assigned to subordinate",
        "category_id": 1,
        "priority_id": 1
    }, headers=auth_header(cust_token))).json()

    tkt2 = (await client.post("/api/v1/tickets", json={
        "title": "Manager Task",
        "description": "Assigned directly to manager",
        "category_id": 1,
        "priority_id": 1
    }, headers=auth_header(cust_token))).json()

    # 4. Assign tkt1 to subordinate agent, and tkt2 to manager
    await client.post(f"/api/v1/tickets/{tkt1['id']}/assign", json={"assignee_id": agent_id}, headers=admin_headers)
    await client.post(f"/api/v1/tickets/{tkt2['id']}/assign", json={"assignee_id": mgr_id}, headers=admin_headers)

    # 5. Manager calls GET /api/v1/tickets/assigned and should see BOTH tickets
    assigned_res = await client.get("/api/v1/tickets/assigned", headers=mgr_headers)
    assert assigned_res.status_code == 200
    assigned_ticket_ids = [t["id"] for t in assigned_res.json()]
    assert tkt1["id"] in assigned_ticket_ids
    assert tkt2["id"] in assigned_ticket_ids


@pytest.mark.anyio
async def test_manager_can_update_subordinate_requester_ticket_status(client: AsyncClient, db_transaction: AsyncSession):
    """Manager can update status of a ticket requested by their subordinate via POST /{id}/status."""
    admin = await create_admin_manually(db_transaction, username="admin_mgr_stat_setup", email="admin_mgr_stat@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]
    admin_headers = auth_header(admin_token)

    # 1. Admin creates Manager
    mgr_res = await client.post("/api/v1/users/admin", json={
        "username": "dept_manager_02",
        "first_name": "Dept",
        "last_name": "Manager",
        "email": "dept_mgr02@supportops.com",
        "password": "Password123",
        "role_id": 3
    }, headers=admin_headers)
    mgr_token = (await login_user(client, username="dept_manager_02", password="Password123"))["access_token"]
    mgr_headers = auth_header(mgr_token)

    # 2. Manager creates user reporting to them
    user_res = await client.post("/api/v1/users/manager", json={
        "username": "reporting_user_01",
        "first_name": "Reporting",
        "last_name": "User",
        "email": "rep_user@supportops.com",
        "password": "Password123",
        "role_id": 1
    }, headers=mgr_headers)
    rep_user_token = (await login_user(client, username="reporting_user_01", password="Password123"))["access_token"]

    # 3. Reporting user creates a ticket
    tkt_res = await client.post("/api/v1/tickets", json={
        "title": "Subordinate Requester Ticket",
        "description": "Requested by subordinate",
        "category_id": 1,
        "priority_id": 1
    }, headers=auth_header(rep_user_token))
    ticket_id = tkt_res.json()["id"]

    # 4. Manager updates ticket status (Status 3 = IN_PROGRESS)
    status_res = await client.post(f"/api/v1/tickets/{ticket_id}/status", json={
        "status_id": 3,
        "comments": "Manager updating subordinate ticket to In Progress"
    }, headers=mgr_headers)
    assert status_res.status_code == 200
    assert status_res.json()["ticket_status"]["id"] == 3


@pytest.mark.anyio
async def test_manager_can_resolve_subordinate_assigned_ticket(client: AsyncClient, db_transaction: AsyncSession):
    """Manager can resolve/close a ticket assigned to their subordinate via POST /{id}/resolve."""
    admin = await create_admin_manually(db_transaction, username="admin_mgr_res_setup", email="admin_mgr_res@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]
    admin_headers = auth_header(admin_token)

    # 1. Admin creates Manager
    mgr_res = await client.post("/api/v1/users/admin", json={
        "username": "ops_manager_03",
        "first_name": "Ops",
        "last_name": "Manager",
        "email": "ops_mgr03@supportops.com",
        "password": "Password123",
        "role_id": 3
    }, headers=admin_headers)
    mgr_token = (await login_user(client, username="ops_manager_03", password="Password123"))["access_token"]
    mgr_headers = auth_header(mgr_token)

    # 2. Manager creates Agent reporting to them
    agent_res = await client.post("/api/v1/users/manager", json={
        "username": "team_agent_03",
        "first_name": "Team",
        "last_name": "Agent",
        "email": "team_agent03@supportops.com",
        "password": "Password123",
        "role_id": 2
    }, headers=mgr_headers)
    agent_id = agent_res.json()["id"]

    # 3. Create ticket and assign to subordinate agent
    tkt_res = await client.post("/api/v1/tickets", json={
        "title": "Subordinate Assigned Issue",
        "description": "Assigned to team_agent_03",
        "category_id": 1,
        "priority_id": 1
    }, headers=admin_headers)
    ticket_id = tkt_res.json()["id"]
    await client.post(f"/api/v1/tickets/{ticket_id}/assign", json={"assignee_id": agent_id}, headers=admin_headers)

    # 4. Manager resolves the ticket (Status 5 = RESOLVED)
    resolve_res = await client.post(f"/api/v1/tickets/{ticket_id}/resolve", json={
        "status_id": 5,
        "comments": "Manager stepping in to resolve subordinate's ticket"
    }, headers=mgr_headers)
    assert resolve_res.status_code == 200
    assert resolve_res.json()["ticket_status"]["id"] == 5


@pytest.mark.anyio
async def test_get_ticket_by_id_success(client: AsyncClient):
    """Retrieve ticket details by its database ID."""
    await create_user(client, username="tkt_by_id_user", email="by_id@example.com")
    token = (await login_user(client, username="tkt_by_id_user", password="password123"))["access_token"]
    headers = auth_header(token)

    create_res = await client.post("/api/v1/tickets", json={
        "title": "Find Me Ticket",
        "description": "Find me by ID",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_id = create_res.json()["id"]

    res = await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == ticket_id
    assert data["title"] == "Find Me Ticket"


@pytest.mark.anyio
async def test_get_ticket_by_id_not_found(client: AsyncClient):
    """Fetching non-existent ticket ID returns 404."""
    await create_user(client, username="tkt_not_found_user", email="not_found@example.com")
    token = (await login_user(client, username="tkt_not_found_user", password="password123"))["access_token"]

    res = await client.get("/api/v1/tickets/99999", headers=auth_header(token))
    assert res.status_code == 404
    assert res.json()["detail"] == "Ticket not found"


@pytest.mark.anyio
async def test_get_ticket_by_ticket_number(client: AsyncClient):
    """Retrieve ticket details by its unique ticket_number (e.g. TKT...)."""
    await create_user(client, username="tkt_num_user", email="num_user@example.com")
    token = (await login_user(client, username="tkt_num_user", password="password123"))["access_token"]
    headers = auth_header(token)

    create_res = await client.post("/api/v1/tickets", json={
        "title": "Lookup By Number",
        "description": "Details",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_num = create_res.json()["ticket_number"]

    res = await client.get(f"/api/v1/tickets/ticket/{ticket_num}", headers=headers)
    assert res.status_code == 200
    assert res.json()["ticket_number"] == ticket_num


# =========================================================================
# 3. Ticket Update Tests (PATCH)
# =========================================================================

@pytest.mark.anyio
async def test_update_ticket_by_requester_success(client: AsyncClient):
    """The creator of the ticket can update title, description, category, or priority."""
    await create_user(client, username="tkt_updater", email="updater@example.com")
    token = (await login_user(client, username="tkt_updater", password="password123"))["access_token"]
    headers = auth_header(token)

    create_res = await client.post("/api/v1/tickets", json={
        "title": "Old Title",
        "description": "Old description",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_id = create_res.json()["id"]

    patch_res = await client.patch(f"/api/v1/tickets/{ticket_id}", json={
        "title": "New Updated Title",
        "description": "New updated description",
        "priority_id": 2
    }, headers=headers)
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["title"] == "New Updated Title"
    assert data["description"] == "New updated description"
    assert data["ticket_priority"]["id"] == 2


@pytest.mark.anyio
async def test_user_cannot_update_another_users_ticket(client: AsyncClient):
    """Non-creator and non-admin cannot update someone else's ticket (403 Forbidden)."""
    # User 1 creates ticket
    await create_user(client, username="tkt_victim", email="victim_tkt@example.com")
    token1 = (await login_user(client, username="tkt_victim", password="password123"))["access_token"]
    create_res = await client.post("/api/v1/tickets", json={
        "title": "Victim Ticket",
        "description": "Original",
        "category_id": 1,
        "priority_id": 1
    }, headers=auth_header(token1))
    ticket_id = create_res.json()["id"]

    # User 2 attempts to patch User 1's ticket
    await create_user(client, username="tkt_intruder", email="intruder_tkt@example.com")
    token2 = (await login_user(client, username="tkt_intruder", password="password123"))["access_token"]
    patch_res = await client.patch(f"/api/v1/tickets/{ticket_id}", json={
        "title": "Hacked Title"
    }, headers=auth_header(token2))
    assert patch_res.status_code == 403
    assert "You are not authorized" in patch_res.json()["detail"]


# =========================================================================
# 4. Ticket Assignment Tests (POST /{id}/assign)
# =========================================================================

@pytest.mark.anyio
async def test_admin_assign_ticket_to_agent_success(client: AsyncClient, db_transaction: AsyncSession):
    """Admin assigns an unassigned ticket to an agent, transitioning status to ASSIGNED."""
    admin = await create_admin_manually(db_transaction, username="admin_assign_mgr", email="admin_assign_mgr@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]
    admin_headers = auth_header(admin_token)

    # 1. Admin creates agent
    agent_res = await client.post("/api/v1/users/admin", json={
        "username": "assignee_agent",
        "first_name": "Support",
        "last_name": "Agent",
        "email": "agent_assign@supportops.com",
        "password": "Password123",
        "role_id": 2
    }, headers=admin_headers)
    agent_id = agent_res.json()["id"]

    # 2. Create ticket
    ticket_res = await client.post("/api/v1/tickets", json={
        "title": "Need Support",
        "description": "Help needed",
        "category_id": 1,
        "priority_id": 1
    }, headers=admin_headers)
    ticket_id = ticket_res.json()["id"]

    # 3. Assign ticket to agent
    assign_res = await client.post(f"/api/v1/tickets/{ticket_id}/assign", json={
        "assignee_id": agent_id
    }, headers=admin_headers)
    assert assign_res.status_code == 200
    data = assign_res.json()
    assert data["assignee"]["id"] == agent_id
    assert data["ticket_status"]["name"].lower() == "assigned"


@pytest.mark.anyio
async def test_customer_cannot_assign_ticket_to_others(client: AsyncClient, db_transaction: AsyncSession):
    """Customer cannot assign tickets to other users (403 Forbidden)."""
    admin = await create_admin_manually(db_transaction, username="admin_for_ag", email="admin_for_ag@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]
    agent_res = await client.post("/api/v1/users/admin", json={
        "username": "some_agent_01",
        "first_name": "Agent",
        "last_name": "One",
        "email": "agent_one@supportops.com",
        "password": "Password123",
        "role_id": 2
    }, headers=auth_header(admin_token))
    agent_id = agent_res.json()["id"]

    # Customer creates ticket
    await create_user(client, username="cust_assign_att", email="cust_att@example.com")
    cust_token = (await login_user(client, username="cust_assign_att", password="password123"))["access_token"]
    cust_headers = auth_header(cust_token)
    tkt_res = await client.post("/api/v1/tickets", json={
        "title": "Customer Issue",
        "description": "Details",
        "category_id": 1,
        "priority_id": 1
    }, headers=cust_headers)
    ticket_id = tkt_res.json()["id"]

    # Customer attempts to assign to agent
    assign_res = await client.post(f"/api/v1/tickets/{ticket_id}/assign", json={
        "assignee_id": agent_id
    }, headers=cust_headers)
    assert assign_res.status_code == 403


# =========================================================================
# 5. Ticket Status Flow (Status Update, Resolve, Close)
# =========================================================================

@pytest.mark.anyio
async def test_ticket_resolve_and_close_flow(client: AsyncClient, db_transaction: AsyncSession):
    """Assigned agent can resolve and close their ticket with required comments."""
    admin = await create_admin_manually(db_transaction, username="admin_status_flow", email="admin_flow@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]
    admin_headers = auth_header(admin_token)

    # 1. Admin creates agent
    agent_res = await client.post("/api/v1/users/admin", json={
        "username": "resolving_agent",
        "first_name": "Resolving",
        "last_name": "Agent",
        "email": "resolving_agent@supportops.com",
        "password": "Password123",
        "role_id": 2
    }, headers=admin_headers)
    agent_id = agent_res.json()["id"]
    agent_token = (await login_user(client, username="resolving_agent", password="Password123"))["access_token"]
    agent_headers = auth_header(agent_token)

    # 2. Customer creates ticket
    await create_user(client, username="tkt_requester_fl", email="tkt_fl@example.com")
    cust_token = (await login_user(client, username="tkt_requester_fl", password="password123"))["access_token"]
    tkt_res = await client.post("/api/v1/tickets", json={
        "title": "Broken Server",
        "description": "Server reboot needed",
        "category_id": 1,
        "priority_id": 1
    }, headers=auth_header(cust_token))
    ticket_id = tkt_res.json()["id"]

    # 3. Admin assigns ticket to resolving_agent
    await client.post(f"/api/v1/tickets/{ticket_id}/assign", json={"assignee_id": agent_id}, headers=admin_headers)

    # 4. Agent resolves the ticket (Status 5 = RESOLVED) - requires comment
    resolve_res = await client.post(f"/api/v1/tickets/{ticket_id}/resolve", json={
        "status_id": 5,
        "comments": "Fixed the server power supply issue."
    }, headers=agent_headers)
    assert resolve_res.status_code == 200
    assert resolve_res.json()["ticket_status"]["id"] == 5

    # 5. Agent closes the ticket (Status 6 = CLOSED) - requires comment
    close_res = await client.post(f"/api/v1/tickets/{ticket_id}/close", json={
        "status_id": 6,
        "comments": "Confirmed fix with customer. Closing ticket."
    }, headers=agent_headers)
    assert close_res.status_code == 200
    assert close_res.json()["ticket_status"]["id"] == 6


@pytest.mark.anyio
async def test_resolve_without_comment_fails(client: AsyncClient, db_transaction: AsyncSession):
    """Resolving a ticket (status 5) without a comment must return 400."""
    admin = await create_admin_manually(db_transaction, username="admin_tkt_res_fail", email="admin_res_fail@supportops.com")
    admin_token = (await login_user(client, username=admin.username, password="password123"))["access_token"]
    admin_headers = auth_header(admin_token)

    tkt_res = await client.post("/api/v1/tickets", json={
        "title": "Comment test",
        "description": "Description",
        "category_id": 1,
        "priority_id": 1
    }, headers=admin_headers)
    ticket_id = tkt_res.json()["id"]

    # Assign to admin themselves
    await client.post(f"/api/v1/tickets/{ticket_id}/assign", json={"assignee_id": admin.id}, headers=admin_headers)

    # Attempt to resolve with empty comment
    res = await client.post(f"/api/v1/tickets/{ticket_id}/resolve", json={
        "status_id": 5,
        "comments": ""
    }, headers=admin_headers)
    assert res.status_code == 400
    assert "Comment is required" in res.json()["detail"]


# =========================================================================
# 6. Ticket Comments (POST /{id}/comments)
# =========================================================================

@pytest.mark.anyio
async def test_add_comment_to_ticket_endpoint(client: AsyncClient):
    """Add a comment via the tickets router POST /api/v1/tickets/{id}/comments."""
    await create_user(client, username="tkt_cmt_author", email="cmt_author@example.com")
    token = (await login_user(client, username="tkt_cmt_author", password="password123"))["access_token"]
    headers = auth_header(token)

    tkt_res = await client.post("/api/v1/tickets", json={
        "title": "Network Drops",
        "description": "WiFi disconnects randomly",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_id = tkt_res.json()["id"]

    cmt_res = await client.post(f"/api/v1/tickets/{ticket_id}/comments", json={
        "comment": "Also observed on 5GHz band."
    }, headers=headers)
    assert cmt_res.status_code == 200
    data = cmt_res.json()
    assert data["ticket_id"] == ticket_id
    assert data["comment"] == "Also observed on 5GHz band."
    assert data["commented_user"]["username"] == "tkt_cmt_author"


# =========================================================================
# 7. Ticket Deletion (DELETE)
# =========================================================================

@pytest.mark.anyio
async def test_delete_ticket_success(client: AsyncClient):
    """User deletes their ticket and associated comments are cleaned up."""
    await create_user(client, username="tkt_deleter", email="tkt_del@example.com")
    token = (await login_user(client, username="tkt_deleter", password="password123"))["access_token"]
    headers = auth_header(token)

    tkt_res = await client.post("/api/v1/tickets", json={
        "title": "Mistaken Ticket",
        "description": "Will be deleted",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_id = tkt_res.json()["id"]

    # Delete ticket
    del_res = await client.delete(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"]

    # Verify 404
    get_res = await client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert get_res.status_code == 404
