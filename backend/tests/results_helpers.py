from datetime import datetime, timedelta

from test_classes_api import admin_login
from test_student_attempts_api import advance_server_clock


async def publish_ended(client, monkeypatch, exam):
    headers = await admin_login(client)
    advance_server_clock(monkeypatch, datetime.fromisoformat(exam["end_at"]) + timedelta(seconds=1))
    url = f"/api/staff/exams/{exam['id']}"
    refreshed = await client.post(url + "/grading/refresh", headers=headers, json={})
    assert refreshed.status_code == 200, refreshed.text
    current = (await client.get(url)).json()
    response = await client.post(
        url + "/publish-results", headers=headers, json={"version": current["version"]}
    )
    assert response.status_code == 200, response.text
    return response.json()
