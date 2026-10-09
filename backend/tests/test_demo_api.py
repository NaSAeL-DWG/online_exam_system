from uuid import uuid4

import pytest

from app.config import get_settings
from test_classes_api import admin_login


@pytest.mark.asyncio
async def test_demo_prepares_shared_classes_and_reruns_without_overwriting_user_changes(
    client, tmp_path
):
    """演示准备通过公开接口可见，重跑保留已有数据与人工修改。"""
    from app.demo import DemoConfig, run_demo

    settings = get_settings()
    namespace = "demo-" + uuid4().hex[:10]
    headers = await admin_login(client)
    unrelated = await client.post(
        "/api/classes",
        headers=headers,
        json={
            "name": "已有教学班-" + uuid4().hex[:8],
            "description": "已有资料必须保留",
        },
    )
    assert unrelated.status_code == 201
    unrelated_id = unrelated.json()["class_info"]["id"]
    config = DemoConfig(
        namespace=namespace,
        admin_login=settings.admin_login_name,
        admin_password=settings.admin_password,
        password="DemoIntegration!123",
        manifest_path=tmp_path / "demo.json",
        stage="identities",
    )
    report = await run_demo(config, client)
    headers = await admin_login(client)
    classes = (await client.get("/api/classes", params={"q": namespace})).json()
    assert classes["total"] == 2
    assert len(report["accounts"]) == 9
    first = (await client.get(f"/api/classes/{report['classes']['foundation']}")).json()[
        "class_info"
    ]
    second = (await client.get(f"/api/classes/{report['classes']['advanced']}")).json()[
        "class_info"
    ]
    assert len(first["teachers"]) == 2
    assert len(second["teachers"]) == 2
    assert set(row["id"] for row in first["students"]) & set(
        row["id"] for row in second["students"]
    )

    changed = await client.patch(
        f"/api/classes/{first['id']}", headers=headers, json={"description": "教师手动编辑应保留"}
    )
    assert changed.status_code == 200
    await run_demo(config, client)
    await admin_login(client)
    reread = (await client.get(f"/api/classes/{first['id']}")).json()["class_info"]
    assert reread["description"] == "教师手动编辑应保留"
    assert (await client.get("/api/classes", params={"q": namespace})).json()["total"] == 2
    preserved = (await client.get(f"/api/classes/{unrelated_id}")).json()["class_info"]
    assert preserved["description"] == "已有资料必须保留"
    manifest = config.manifest_path.read_text(encoding="utf-8")
    assert config.password not in manifest
    assert config.admin_password not in manifest


class LostStartResponse:
    """网络边界模拟开始已成功、客户端未收到响应，不伪造业务状态。"""

    def __init__(self, client):
        self.client = client
        self.lost = False

    async def request(self, method, path, **kwargs):
        response = await self.client.request(method, path, **kwargs)
        if not self.lost and method == "POST" and path.endswith("/attempts"):
            self.lost = True
            raise ConnectionError("模拟开始响应丢失")
        return response


@pytest.mark.asyncio
async def test_demo_recovers_lost_start_and_exposes_real_results_review_pending_and_void_history(
    client, tmp_path
):
    """完整演示经公开接口产生历史，重跑不会增次或覆盖人工学习标记。"""
    from app.demo import DemoConfig, run_demo
    from test_classes_api import user_login

    settings = get_settings()
    config = DemoConfig(
        namespace="demo-" + uuid4().hex[:10],
        admin_login=settings.admin_login_name,
        admin_password=settings.admin_password,
        password="DemoIntegration!123",
        manifest_path=tmp_path / "complete.json",
        window_seconds=60,
    )
    with pytest.raises(ConnectionError, match="响应丢失"):
        await run_demo(config, LostStartResponse(client))
    report = await run_demo(config, client)
    exams = report["exams"]
    await user_login(client, report["accounts"]["s1"]["login_name"], config.password)
    result = (await client.get(f"/api/student/results/{exams['limited']}")).json()
    assert result["final_score"] == "45.0"
    assert [row["final_score"] for row in result["attempts"]] == ["90.0", "45.0"]
    review = await client.get(f"/api/student/attempts/{result['attempts'][0]['id']}/review")
    assert review.status_code == 200
    assert {row["type"] for row in review.json()["questions"]} == {
        "SINGLE_CHOICE",
        "MULTIPLE_CHOICE",
        "TRUE_FALSE",
        "SHORT_ANSWER",
    }
    hidden = (await client.get(f"/api/student/results/{exams['hidden']}")).json()
    assert hidden["final_score"] == "90.0"
    assert (
        await client.get(f"/api/student/attempts/{hidden['attempts'][0]['id']}/review")
    ).status_code == 403
    pending = (await client.get(f"/api/student/results/{exams['pending']}")).json()
    assert pending["final_score"] is None
    assert pending["final_attempt_no"] == 2
    assert pending["result_state"] == "NOT_PUBLISHED"
    correcting = (await client.get(f"/api/student/results/{exams['correcting']}")).json()
    assert correcting["result_state"] == "CORRECTING"

    mistakes = (await client.get("/api/student/mistakes", params={"q": config.namespace})).json()
    assert mistakes["total"] >= 4
    assert any(
        row["score"] == "12.5" and row["type"] == "MULTIPLE_CHOICE" for row in mistakes["items"]
    )
    assert any(row["mastered"] and row["note"] for row in mistakes["items"])
    answer_id = mistakes["items"][0]["answer_id"]
    headers = {"X-CSRF-Token": (await client.get("/api/auth/csrf")).json()["csrf_token"]}
    assert (
        await client.put(
            f"/api/student/mistakes/{answer_id}/annotation",
            headers=headers,
            json={"note": "人工修改不能被重跑覆盖", "mastered": True},
        )
    ).status_code == 200

    await admin_login(client)
    participants = (await client.get(f"/api/staff/exams/{exams['limited']}/participants")).json()
    revoked = next(
        row for row in participants["items"] if row["user"]["id"] == report["accounts"]["s5"]["id"]
    )
    assert revoked["status"] == "CANCELLED"
    assert revoked["voided_attempts"] == 1
    cancelled = (await client.get(f"/api/staff/exams/{exams['cancelled']}")).json()
    assert cancelled["status"] == "CANCELLED"
    assert (await client.get(f"/api/staff/exams/{exams['cancelled']}/attempts")).json()[
        "total"
    ] == 0
    final = (await client.get(f"/api/staff/exams/{exams['pending']}/final-results")).json()
    last = next(
        row for row in final["items"] if row["student"]["id"] == report["accounts"]["s1"]["id"]
    )
    assert last["final_score"] is None
    assert last["attempt_no"] == 2
    assert (await client.get(f"/api/staff/exams/{exams['public']}")).json()[
        "audience_type"
    ] == "PUBLIC"

    await run_demo(config, client)
    await user_login(client, report["accounts"]["s1"]["login_name"], config.password)
    saved = (await client.get(f"/api/student/mistakes/{answer_id}")).json()
    assert saved["note"] == "人工修改不能被重跑覆盖"
    assert saved["mastered"] is True
    assert (await client.get(f"/api/student/results/{exams['limited']}")).json()[
        "attempts_count"
    ] == 2
