import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from test.conftest import auth_header, create_admin_manually, create_user, login_user

# =========================================================================
# 1. Add Comments to Tickets
# =========================================================================

@pytest.mark.anyio
async def test_add_comment_to_ticket_success(client: AsyncClient):
    """Author can add a comment to their ticket."""
    user = await create_user(client, username="commenter_alice", email="alice_cmt@example.com")
    token = (await login_user(client, username="commenter_alice", password="password123"))["access_token"]
    headers = auth_header(token)

    # 1. Alice creates a ticket
    t_res = await client.post("/api/v1/tickets", json={
        "title": "Need help with monitor",
        "description": "External monitor does not turn on",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    assert t_res.status_code == 201
    ticket_id = t_res.json()["id"]

    # 2. Alice adds a comment
    c_res = await client.post(f"/api/v1/tickets/{ticket_id}/comments", json={
        "comment": "I tried checking the HDMI cable, still not working."
    }, headers=headers)
    assert c_res.status_code == 200
    comment_data = c_res.json()
    assert comment_data["ticket_id"] == ticket_id
    assert comment_data["comment"] == "I tried checking the HDMI cable, still not working."
    assert comment_data["commented_user"]["username"] == "commenter_alice"
    assert "date_time" in comment_data


# =========================================================================
# 2. Read Comments
# =========================================================================

@pytest.mark.anyio
async def test_get_ticket_comments(client: AsyncClient):
    """Retrieve all comments associated with a specific ticket."""
    user = await create_user(client, username="reader_bob", email="bob_cmt@example.com")
    token = (await login_user(client, username="reader_bob", password="password123"))["access_token"]
    headers = auth_header(token)

    # 1. Create ticket and 2 comments
    t_res = await client.post("/api/v1/tickets", json={
        "title": "Keyboard issue",
        "description": "Keys stuck",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_id = t_res.json()["id"]

    await client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"comment": "First update"}, headers=headers)
    await client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"comment": "Second update"}, headers=headers)

    # 2. Get comments for this ticket
    response = await client.get(f"/api/v1/comments/ticket/{ticket_id}", headers=headers)
    assert response.status_code == 200
    comments = response.json()
    assert len(comments) == 2
    assert comments[0]["comment"] == "First update"
    assert comments[1]["comment"] == "Second update"


@pytest.mark.anyio
async def test_get_comment_by_id(client: AsyncClient):
    """Retrieve single comment by ID."""
    user = await create_user(client, username="finder_charlie", email="charlie_cmt@example.com")
    token = (await login_user(client, username="finder_charlie", password="password123"))["access_token"]
    headers = auth_header(token)

    t_res = await client.post("/api/v1/tickets", json={
        "title": "Software crash",
        "description": "App crashes on launch",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_id = t_res.json()["id"]

    c_res = await client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"comment": "Crash logs attached"}, headers=headers)
    comment_id = c_res.json()["id"]

    # Fetch by ID
    get_res = await client.get(f"/api/v1/comments/{comment_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == comment_id
    assert get_res.json()["comment"] == "Crash logs attached"


# =========================================================================
# 3. Update & Delete Comments
# =========================================================================

@pytest.mark.anyio
async def test_update_comment_author_success(client: AsyncClient):
    """Author can update their own comment."""
    user = await create_user(client, username="editor_david", email="david_cmt@example.com")
    token = (await login_user(client, username="editor_david", password="password123"))["access_token"]
    headers = auth_header(token)

    t_res = await client.post("/api/v1/tickets", json={
        "title": "Mouse lag",
        "description": "Mouse stuttering",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_id = t_res.json()["id"]

    c_res = await client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"comment": "Initial comment text"}, headers=headers)
    comment_id = c_res.json()["id"]

    # Update comment
    upd_res = await client.put(f"/api/v1/comments/{comment_id}", json={"comment": "Corrected comment text"}, headers=headers)
    assert upd_res.status_code == 200
    assert upd_res.json()["comment"] == "Corrected comment text"


@pytest.mark.anyio
async def test_delete_comment_author_success(client: AsyncClient):
    """Author can delete their own comment."""
    user = await create_user(client, username="deleter_emma", email="emma_cmt@example.com")
    token = (await login_user(client, username="deleter_emma", password="password123"))["access_token"]
    headers = auth_header(token)

    t_res = await client.post("/api/v1/tickets", json={
        "title": "Audio issue",
        "description": "No sound output",
        "category_id": 1,
        "priority_id": 1
    }, headers=headers)
    ticket_id = t_res.json()["id"]

    c_res = await client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"comment": "Accidental comment"}, headers=headers)
    comment_id = c_res.json()["id"]

    # Delete comment
    del_res = await client.delete(f"/api/v1/comments/{comment_id}", headers=headers)
    assert del_res.status_code == 200

    # Verify 404
    get_res = await client.get(f"/api/v1/comments/{comment_id}", headers=headers)
    assert get_res.status_code == 404
