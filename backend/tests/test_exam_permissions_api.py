import pytest

from content_helpers import create_teacher, teacher_login


@pytest.mark.asyncio
async def test_teacher_can_select_graders_without_gaining_admin_user_listing(client):
    first, first_no = await create_teacher(client)
    second, _ = await create_teacher(client)
    await teacher_login(client, first_no)
    candidates = await client.get(
        "/api/staff/teachers", params={"q": second["login_name"], "status": "ACTIVATED"}
    )
    assert candidates.status_code == 200, candidates.text
    assert candidates.json()["items"][0]["id"] == second["id"]
    assert (await client.get("/api/admin/users")).status_code == 403
