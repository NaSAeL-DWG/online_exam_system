import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from .config import DemoConfig
from .dataset import ATTEMPTS, EXAMS, answer_values, questions
from .http import DemoAPI, DemoError


class DemoRunner:
    def __init__(self, config, transport):
        self.config = config
        self.api = DemoAPI(transport)
        self.prefix = f"[{config.namespace}]"
        if config.manifest_path.exists():
            self.state = json.loads(config.manifest_path.read_text(encoding="utf-8"))
            if self.state.get("namespace") != config.namespace:
                raise DemoError("manifest 与 namespace 不一致，请另用独立文件")
        else:
            self.state = {
                "namespace": config.namespace,
                "accounts": {},
                "classes": {},
                "questions": {},
                "exams": {},
                "attempts": {},
            }

    def save(self):
        """每项成功即原子记账，中断后继续；文件中只保存公开ID与进度。"""
        path = self.config.manifest_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)

    async def admin(self):
        return await self.api.login(self.config.admin_login, self.config.admin_password)

    def temporary_password(self, login_name):
        # 临时密码从私有演示口令派生，首次改密中断后仍可继续，且不会落盘。
        digest = hmac.new(
            self.config.password.encode(), login_name.encode(), hashlib.sha256
        ).hexdigest()
        return "Temporary!" + digest

    async def ensure_account(self, key, name, teacher):
        await self.admin()
        login_name = f"{self.config.namespace}-{key}"
        stored = self.state["accounts"].get(key)
        rows = await self.api.list_all("/api/admin/users", q=login_name)
        user = next((row for row in rows if row["login_name"] == login_name), None)
        if stored and (user is None or user["id"] != stored["id"]):
            raise DemoError(f"演示账号 {login_name} 已被人工改名或移除，请另用namespace")
        if user and not stored and user["real_name"] != f"{self.prefix} {name}":
            raise DemoError(f"账号命名冲突：{login_name}，请另用namespace")
        if user is None:
            payload = {
                "real_name": f"{self.prefix} {name}",
                "email": f"{login_name}@example.com",
                "phone_number": "13800001000",
            }
            if teacher:
                result = await self.api.request(
                    "POST",
                    "/api/admin/teachers",
                    payload
                    | {
                        "teacher_no": login_name,
                        "temporary_password": self.temporary_password(login_name),
                    },
                )
            else:
                result = await self.api.request(
                    "POST",
                    "/api/auth/register",
                    payload
                    | {
                        "student_no": login_name,
                        "password": self.config.password,
                    },
                )
            user = result["user"]
        self.state["accounts"][key] = {
            "id": user["id"],
            "login_name": login_name,
            "role": user["user_type"],
        }
        self.save()
        if teacher and user["must_change_password"]:
            await self.api.login(login_name, self.temporary_password(login_name))
            await self.api.request(
                "PUT",
                "/api/auth/password",
                {
                    "current_password": self.temporary_password(login_name),
                    "new_password": self.config.password,
                },
            )
            # 改密已撤销旧会话，不再以该会话调用退出。
            self.api.login_name = None
        elif not teacher and user["status"] == "WAITING_ACTIVATE":
            reviews = await self.api.list_all("/api/staff/reviews", q=login_name, status="PENDING")
            pending = next((row for row in reviews if row["user"]["id"] == user["id"]), None)
            if pending:
                await self.api.request(
                    "POST", f"/api/staff/reviews/{pending['id']}/decision", {"decision": "APPROVED"}
                )
        return user["id"]

    async def ensure_class(self, key, title, teachers, students):
        await self.admin()
        stored = self.state["classes"].get(key)
        if stored:
            info = (await self.api.request("GET", f"/api/classes/{stored['id']}"))["class_info"]
        else:
            name = f"{self.prefix} {title}"
            rows = await self.api.list_all("/api/classes", q=name)
            info = next((row for row in rows if row["name"] == name), None)
            if info is None:
                result = await self.api.request(
                    "POST",
                    "/api/classes",
                    {
                        "name": name,
                        "description": "演示教学班：学生可同时加入多个班级。",
                        "teacher_ids": [self.state["accounts"][item]["id"] for item in teachers],
                    },
                )
                info = result["class_info"]
            self.state["classes"][key] = {"id": info["id"], "members_done": []}
            stored = self.state["classes"][key]
            self.save()
        for student in students:
            if student in stored["members_done"]:
                continue
            user_id = self.state["accounts"][student]["id"]
            await self.api.request(
                "PUT", f"/api/classes/{info['id']}/members/{user_id}", {"role": "STUDENT"}
            )
            stored["members_done"].append(student)
            self.save()

    async def identities(self):
        if self.state.get("identities_complete"):
            await self.admin()
            rows = await self.api.list_all("/api/admin/users", q=self.config.namespace)
            for account in self.state["accounts"].values():
                if not any(row["id"] == account["id"] for row in rows):
                    raise DemoError(
                        "manifest 中的账号在当前API不存在或已改名，请检查地址或另用namespace"
                    )
            for stored in self.state["classes"].values():
                await self.api.request("GET", f"/api/classes/{stored['id']}")
            return
        for key, name in [("t1", "陈知行"), ("t2", "许明月"), ("t3", "周思齐")]:
            await self.ensure_account(key, name, True)
        for key, name in [
            ("s1", "林雨桐"),
            ("s2", "王子涵"),
            ("s3", "赵一诺"),
            ("s4", "刘梓轩"),
            ("s5", "孙若曦"),
            ("s6", "郑宇辰"),
        ]:
            await self.ensure_account(key, name, False)
        await self.ensure_class(
            "foundation", "软件工程基础班", ["t1", "t2"], ["s1", "s2", "s3", "s5"]
        )
        await self.ensure_class("advanced", "数据库实践班", ["t2", "t3"], ["s1", "s3", "s4", "s6"])
        self.state["identities_complete"] = True
        self.save()

    async def login_account(self, key):
        account = self.state["accounts"][key]
        await self.api.login(account["login_name"], self.config.password)

    async def content(self):
        await self.login_account("t1")
        for key, score, payload in questions(self.config.namespace):
            stored = self.state["questions"].get(key)
            if stored:
                await self.api.request("GET", f"/api/staff/questions/{stored['id']}")
                continue
            rows = await self.api.list_all("/api/staff/questions", q=payload["content"])
            question = next((row for row in rows if row["content"] == payload["content"]), None)
            if question is None:
                question = await self.api.request("POST", "/api/staff/questions", payload)
            self.state["questions"][key] = {"id": question["id"], "score": score}
            self.save()
        if "paper" not in self.state:
            title = f"{self.prefix} 软件工程综合卷（100分）"
            rows = await self.api.list_all("/api/staff/papers", q=title)
            paper = next((row for row in rows if row["title"] == title), None)
            if paper is None:
                paper = await self.api.request(
                    "POST",
                    "/api/staff/papers",
                    {
                        "title": title,
                        "description": "事务、HTTP、稳定ID与历史快照；四类题合计100分。",
                        "questions": [
                            {"question_id": row["id"], "score": row["score"]}
                            for row in self.state["questions"].values()
                        ],
                    },
                )
            self.state["paper"] = paper["id"]
            self.save()

    async def prepare_exams(self):
        await self.login_account("t1")
        if "history_end_at" not in self.state:
            self.state["history_end_at"] = (
                datetime.now(timezone.utc) + timedelta(seconds=self.config.window_seconds)
            ).isoformat()
            self.save()
        for key, title, audience, review, timing in EXAMS:
            stored = self.state["exams"].get(key)
            if stored:
                exam = await self.api.request("GET", f"/api/staff/exams/{stored['id']}")
            else:
                full_title = f"{self.prefix} {title}"
                rows = await self.api.list_all("/api/staff/exams", q=full_title)
                exam = next((row for row in rows if row["title"] == full_title), None)
                if exam is None:
                    exam = await self.api.request(
                        "POST",
                        "/api/staff/exams",
                        {
                            "source_paper_id": self.state["paper"],
                            "title": full_title,
                            "description": f"{self.prefix} 演示数据。通过真实作答、阅卷和公布流程创建。",
                            "audience_type": audience,
                        },
                    )
                stored = {"id": exam["id"]}
                self.state["exams"][key] = stored
                self.save()
            url = f"/api/staff/exams/{exam['id']}"
            if not stored.get("configured"):
                # 响应丢失时已有完整配置则复用，不再次写入或覆盖人工编辑。
                if exam["end_at"] is None:
                    now = datetime.now(timezone.utc)
                    start = now - timedelta(seconds=5)
                    end = datetime.fromisoformat(self.state["history_end_at"])
                    if timing in {"future", "draft"}:
                        start = now + timedelta(days=7)
                        end = start + timedelta(hours=2)
                    elif timing == "open":
                        end = now + timedelta(days=7)
                    exam = await self.api.request(
                        "PUT",
                        url,
                        {
                            "version": exam["version"],
                            "title": exam["title"],
                            "description": exam["description"],
                            "audience_type": audience,
                            "start_at": start.isoformat(),
                            "end_at": end.isoformat(),
                            "duration_seconds": 600
                            if timing == "open"
                            else self.config.window_seconds,
                            "max_attempts": 3,
                            "allow_review": review,
                            "shuffle_questions": key == "practice",
                            "shuffle_options": key == "practice",
                            "multiple_choice_mode": "PARTIAL",
                            "pass_percentage": "60.00",
                            "grader_ids": [
                                self.state["accounts"][item]["id"] for item in ["t1", "t2", "t3"]
                            ],
                            "questions": [
                                {"source_question_id": row["id"], "score": row["score"]}
                                for row in self.state["questions"].values()
                            ],
                        },
                    )
                stored["configured"] = True
                self.save()
            if audience == "RESTRICTED" and not stored.get("participants_done"):
                students = (
                    ["s6"]
                    if key == "cancelled"
                    else (
                        ["s1", "s2"]
                        if key in {"hidden", "pending", "correcting"}
                        else ["s1", "s2", "s3", "s4", "s5"]
                    )
                )
                payload = {"student_ids": [self.state["accounts"][item]["id"] for item in students]}
                if key == "limited":
                    payload["class_ids"] = [self.state["classes"]["foundation"]["id"]]
                await self.api.request("POST", url + "/participants", payload)
                stored["participants_done"] = True
                self.save()
            if timing != "draft" and not stored.get("released"):
                if exam["status"] == "DRAFT":
                    exam = await self.api.request(
                        "POST", url + "/publish", {"version": exam["version"]}
                    )
                stored["released"] = True
                self.save()

    async def ensure_attempt(self, exam_key, student, number, style):
        key = f"{exam_key}/{student}/{number}"
        stored = self.state["attempts"].get(key)
        if stored and stored.get("submitted"):
            return
        exam_id = self.state["exams"][exam_key]["id"]
        await self.login_account("t1")
        exam = await self.api.request("GET", f"/api/staff/exams/{exam_id}")
        attempts = await self.api.list_all(f"/api/staff/exams/{exam_id}/attempts")
        student_id = self.state["accounts"][student]["id"]
        submitted = next(
            (
                row
                for row in attempts
                if row["student"]["id"] == student_id and row["attempt_no"] == number
            ),
            None,
        )
        if submitted:
            self.state["attempts"][key] = {"id": submitted["id"], "submitted": True}
            self.save()
            return
        if datetime.now(timezone.utc) >= datetime.fromisoformat(exam["end_at"]):
            raise DemoError(
                f"{exam_key} 已结束但第{number}次演示作答尚未完成；保留已有数据，请另用namespace"
            )
        await self.login_account(student)
        attempt = await self.api.request("POST", f"/api/student/exams/{exam_id}/attempts", {})
        if attempt["attempt_no"] != number:
            raise DemoError(f"{exam_key} 的作答次数被人工改变；请另用namespace")
        self.state["attempts"][key] = {"id": attempt["id"]}
        self.save()
        attempt = await self.api.request(
            "POST",
            f"/api/student/attempts/{attempt['id']}/activate",
            {
                "expected_generation": attempt["token_generation"],
            },
        )
        permission = {
            "page_token": attempt["page_token"],
            "token_generation": attempt["token_generation"],
        }
        values = answer_values(exam, style)
        for question in attempt["questions"]:
            answer = question["answer"]
            desired = values[question["id"]]
            if answer["answer_data"] is not None:
                # 网络响应丢失时复用已保存答案；人工作答冲突则停止，绝不覆盖。
                if answer["answer_data"] != desired:
                    raise DemoError(f"{exam_key} 中已有不同的人工答案；请另用namespace")
                continue
            if desired is not None:
                await self.api.request(
                    "PUT",
                    f"/api/student/attempts/{attempt['id']}/answers/{answer['id']}",
                    permission | {"version": answer["version"], "answer_data": desired},
                )
        await self.api.request(
            "POST",
            f"/api/student/attempts/{attempt['id']}/submit",
            permission | {"confirm_unanswered": True},
        )
        self.state["attempts"][key]["submitted"] = True
        self.save()

    async def void_records(self):
        await self.login_account("t1")
        if not self.state.get("revoked"):
            exam_id = self.state["exams"]["limited"]["id"]
            rows = await self.api.list_all(f"/api/staff/exams/{exam_id}/participants")
            user_id = self.state["accounts"]["s5"]["id"]
            participant = next(row for row in rows if row["user"]["id"] == user_id)
            if participant["status"] != "CANCELLED":
                await self.api.request(
                    "POST",
                    f"/api/staff/exams/{exam_id}/participants/{participant['id']}/cancel",
                    {
                        "version": participant["version"],
                        "reason": "演示：学生转班，撤销资格并保留废弃作答审计。",
                    },
                )
            self.state["revoked"] = True
            self.save()
        if not self.state.get("cancelled"):
            exam_id = self.state["exams"]["cancelled"]["id"]
            exam = await self.api.request("GET", f"/api/staff/exams/{exam_id}")
            if exam["status"] != "CANCELLED":
                await self.api.request(
                    "POST",
                    f"/api/staff/exams/{exam_id}/cancel",
                    {
                        "version": exam["version"],
                        "reason": "演示：教学安排变更，整场取消并废弃答卷。",
                    },
                )
            self.state["cancelled"] = True
            self.save()

    async def finish_history(self):
        end = datetime.fromisoformat(self.state["history_end_at"])
        while (end - datetime.now(timezone.utc)).total_seconds() >= 0:
            await asyncio.sleep(min(10, (end - datetime.now(timezone.utc)).total_seconds() + 0.1))
        await self.login_account("t1")
        for key in ["limited", "public", "hidden", "pending", "correcting"]:
            await self.api.request(
                "POST", f"/api/staff/exams/{self.state['exams'][key]['id']}/grading/refresh", {}
            )
        for exam_key, student, number, _, score in ATTEMPTS:
            if score is None or student == "s5":
                continue
            attempt_id = self.state["attempts"][f"{exam_key}/{student}/{number}"]["id"]
            await self.login_account("t1")
            attempt = await self.api.request("GET", f"/api/staff/attempts/{attempt_id}")
            if attempt["grading_status"] == "GRADED":
                continue
            if attempt["task"] is None or attempt["task"]["assigned_teacher"] is None:
                raise DemoError("演示答卷尚无可用阅卷教师，请先通过管理员改派或另用namespace")
            assigned = attempt["task"]["assigned_teacher"]["id"]
            teacher = next(
                key for key, account in self.state["accounts"].items() if account["id"] == assigned
            )
            await self.login_account(teacher)
            attempt = await self.api.request("GET", f"/api/staff/attempts/{attempt_id}")
            essay = next(row for row in attempt["questions"] if row["type"] == "SHORT_ANSWER")
            if essay["answer"]["grading_status"] != "GRADED":
                await self.api.request(
                    "POST",
                    f"/api/staff/answers/{essay['answer']['id']}/grade",
                    {
                        "version": essay["answer"]["version"],
                        "grading_revision": essay["grading_revision"],
                        "score": score,
                        "comment": "已说明快照隔离目的。请结合保存字段与实际例子进一步完善。",
                    },
                )
        await self.login_account("t1")
        for key in ["limited", "public", "hidden", "correcting"]:
            stored = self.state["exams"][key]
            if stored.get("published"):
                continue
            url = f"/api/staff/exams/{stored['id']}"
            exam = await self.api.request("GET", url)
            if exam["status"] != "RESULTS_PUBLISHED":
                await self.api.request(
                    "POST", url + "/publish-results", {"version": exam["version"]}
                )
            stored["published"] = True
            self.save()
        correcting = self.state["exams"]["correcting"]
        if not correcting.get("withdrawn"):
            url = f"/api/staff/exams/{correcting['id']}"
            exam = await self.api.request("GET", url)
            if exam["status"] == "RESULTS_PUBLISHED":
                await self.api.request(
                    "POST",
                    url + "/withdraw-results",
                    {
                        "version": exam["version"],
                        "reason": "演示：复核简答评分依据，暂时隐藏成绩与回看。",
                    },
                )
            correcting["withdrawn"] = True
            self.save()
        await self.learning_notes()
        self.state["complete"] = True
        self.save()

    async def learning_notes(self):
        notes = [
            (
                "limited/s1/2",
                "MULTIPLE_CHOICE",
                True,
                "少选仅得部分分：补齐GET与HEAD，避免误把PATCH视作只读。",
            ),
            (
                "limited/s1/1",
                "SHORT_ANSWER",
                False,
                "快照应保存当时题干、选项、分值与评分依据，再补一个题库修改案例。",
            ),
        ]
        completed = self.state.setdefault("annotations_done", [])
        for attempt_key, kind, mastered, note in notes:
            marker = f"{attempt_key}/{kind}"
            if marker in completed:
                continue
            await self.login_account("t1")
            attempt_id = self.state["attempts"][attempt_key]["id"]
            attempt = await self.api.request("GET", f"/api/staff/attempts/{attempt_id}")
            answer_id = next(
                row["answer"]["id"] for row in attempt["questions"] if row["type"] == kind
            )
            await self.login_account("s1")
            mistake = await self.api.request("GET", f"/api/student/mistakes/{answer_id}")
            # 已有学习标记可能由学生人工填写，恢复时保留它，不重复覆盖。
            if mistake["note"] is None and not mistake["mastered"]:
                await self.api.request(
                    "PUT",
                    f"/api/student/mistakes/{answer_id}/annotation",
                    {
                        "note": note,
                        "mastered": mastered,
                    },
                )
            completed.append(marker)
            self.save()

    async def complete(self):
        if self.state.get("complete"):
            # 完成后的重跑只读验证资源仍存在，不恢复用户撤回或修改的状态。
            for stored in self.state["exams"].values():
                await self.api.request("GET", f"/api/staff/exams/{stored['id']}")
            return
        await self.content()
        await self.prepare_exams()
        for exam_key, student, number, style, _ in ATTEMPTS:
            await self.ensure_attempt(exam_key, student, number, style)
        await self.void_records()
        await self.finish_history()

    def report(self):
        return {
            "namespace": self.config.namespace,
            "accounts": self.state["accounts"],
            "classes": {key: row["id"] for key, row in self.state["classes"].items()},
            "exams": {key: row["id"] for key, row in self.state["exams"].items()},
            "complete": self.state.get("complete", False),
        }


async def run_demo(config: DemoConfig, transport):
    """演示入口只编排公开HTTP请求，不访问ORM或改变业务时钟。"""
    runner = DemoRunner(config, transport)
    try:
        await runner.identities()
        if config.stage == "complete":
            await runner.complete()
        return runner.report()
    finally:
        await runner.api.logout()
