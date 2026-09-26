from io import BytesIO

import pytest
from PIL import Image

from test_classes_api import admin_login
from test_classes_api import user_login
from content_helpers import create_student


@pytest.mark.asyncio
async def test_image_upload_is_immutable_validated_and_private(client):
    headers = await admin_login(client)
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, format="PNG")
    data = buffer.getvalue()
    uploaded = await client.post(
        "/api/staff/assets", headers=headers, files={"file": ("../../same.png", data, "image/png")}
    )
    assert uploaded.status_code == 201, uploaded.text
    asset = uploaded.json()
    read = await client.get(asset["url"])
    assert read.status_code == 200
    assert read.content == data
    assert read.headers["cache-control"] == "private, no-store"
    second = await client.post(
        "/api/staff/assets", headers=headers, files={"file": ("../../same.png", data, "image/png")}
    )
    assert second.json()["id"] != asset["id"]
    invalid = await client.post(
        "/api/staff/assets",
        headers=headers,
        files={"file": ("x.png", b"<script>alert(1)</script>", "image/png")},
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"]["code"] == "INVALID_IMAGE"
    _, student_no = await create_student(client)
    client.cookies.clear()
    await user_login(client, student_no, "ValidPassword!123")
    assert (await client.get(asset["url"])).status_code == 403
    client.cookies.clear()
    assert (await client.get(asset["url"])).status_code == 401
