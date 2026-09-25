"""培训演练业务规则：排期、签到、演练、考核与结业均在此闭环。"""
from __future__ import annotations

import re
from datetime import datetime
from threading import Lock
from typing import Any

from app.store import store

TRAINING_MODULE = "training"
PARTICIPANT_MODULE = "training_participant"
LOG_MODULE = "training_log"

STATUS_DRAFT = "待开班"
STATUS_TRAINING = "培训中"
STATUS_ASSESSMENT = "待考核"
STATUS_FINISHED = "已结业"
STATUS_ORDER = [STATUS_DRAFT, STATUS_TRAINING, STATUS_ASSESSMENT, STATUS_FINISHED]

RESULT_PENDING = "未考核"
RESULT_PASSED = "合格"
RESULT_FAILED = "不合格"

PASS_SCORE = 60
REQUIRED_TRAINING_FIELDS = ["培训编号", "培训名称", "岗位", "设备类型", "培训日期", "授课师傅"]


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TrainingService:
    def __init__(self) -> None:
        self._locks: dict[int, Lock] = {}
        self._locks_guard = Lock()

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        post: str | None = None,
        device_type: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._list_item(row) for row in store.rows(TRAINING_MODULE)]
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("培训编号", ""))
                or keyword in str(row.get("培训名称", ""))
                or keyword in str(row.get("授课师傅", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if post:
            rows = [row for row in rows if post in str(row.get("岗位", ""))]
        if device_type:
            rows = [row for row in rows if device_type in str(row.get("设备类型", ""))]

        rows.sort(key=lambda row: int(row.get("id", 0)), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        training = store.find(TRAINING_MODULE, entry_id)
        if training is None:
            return None
        participants = self._participants(entry_id)
        logs = [dict(row) for row in store.rows(LOG_MODULE) if row.get("培训ID") == entry_id]
        detail = dict(training)
        detail["participants"] = participants
        detail["logs"] = logs
        detail["stats"] = self._stats(participants)
        return detail

    def create_training(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        cleaned: dict[str, str] = {}
        for field in REQUIRED_TRAINING_FIELDS:
            value = str(values.get(field) or "").strip()
            if not value:
                return None, f"缺少必填字段：{field}"
            cleaned[field] = value

        operator = str(values.get("操作人") or "").strip()
        if not operator:
            return None, "缺少必填字段：操作人"

        rows = store.rows(TRAINING_MODULE)
        if any(row.get("培训编号") == cleaned["培训编号"] for row in rows):
            return None, f"培训编号 {cleaned['培训编号']} 已存在，请更换编号"

        names = self._normalized_names(values.get("参训人员"))
        if not names:
            return None, "至少需要安排一名参训人员"

        training_id = self._next_id(TRAINING_MODULE)
        timestamp = now_text()
        training: dict[str, Any] = {
            "id": training_id,
            "status": STATUS_DRAFT,
            "pending": True,
            "abnormal": False,
            **cleaned,
            "操作人": operator,
            "创建人": operator,
            "创建时间": timestamp,
            "培训开始人": "",
            "培训开始时间": "",
            "结束演练人": "",
            "结束演练时间": "",
            "结业操作人": "",
            "结业时间": "",
        }
        rows.append(training)

        participant_rows = store.rows(PARTICIPANT_MODULE)
        for name in names:
            participant_id = self._next_id(PARTICIPANT_MODULE)
            participant_rows.append(
                {
                    "id": participant_id,
                    "培训ID": training_id,
                    "培训编号": cleaned["培训编号"],
                    "岗位": cleaned["岗位"],
                    "设备类型": cleaned["设备类型"],
                    "培训日期": cleaned["培训日期"],
                    "姓名": name,
                    "status": "未签到",
                    "签到状态": "未签到",
                    "考核成绩": "",
                    "考核结果": RESULT_PENDING,
                    "人员状态": "待开班",
                    "score_submitted": False,
                    "abnormal": False,
                    "签到人": "",
                    "签到时间": "",
                    "考核人": "",
                    "考核时间": "",
                    "结业时间": "",
                }
            )

        self._add_log(
            training_id,
            "排期培训",
            STATUS_DRAFT,
            operator,
            timestamp,
            f"按{cleaned['岗位']}、{cleaned['设备类型']}安排 {len(names)} 名人员参训",
        )
        return self.get_entry(training_id), "培训已排期，当前状态为待开班"

    def sign_in(self, training_id: int, participant_id: int, operator: str) -> tuple[dict[str, Any] | None, str]:
        operator = operator.strip()
        if not operator:
            return None, "缺少必填字段：操作人"
        with self._lock(training_id):
            training = store.find(TRAINING_MODULE, training_id)
            if training is None:
                return None, f"培训 {training_id} 不存在或已归档"
            participant = self._find_participant(training_id, participant_id)
            if participant is None:
                return None, f"参训人员 {participant_id} 不属于这场培训"
            timestamp = now_text()

            if training["status"] == STATUS_DRAFT:
                training["status"] = STATUS_TRAINING
                training["培训开始人"] = operator
                training["培训开始时间"] = timestamp
                self._add_log(training_id, "开始培训", STATUS_TRAINING, operator, timestamp, "首次签到后进入演练环节")
            elif training["status"] != STATUS_TRAINING:
                return None, f"当前状态为{training['status']}，签到通道已关闭，状态不能回退"

            if participant["签到状态"] == "已签到":
                return self.get_entry(training_id), f"{participant['姓名']} 已签到，请勿重复签到"

            participant["签到状态"] = "已签到"
            participant["status"] = STATUS_TRAINING
            participant["人员状态"] = STATUS_TRAINING
            participant["签到人"] = operator
            participant["签到时间"] = timestamp
            self._add_log(training_id, "人员签到", participant["status"], operator, timestamp, f"{participant['姓名']} 签到成功")
            return self.get_entry(training_id), f"{participant['姓名']} 已签到，进入培训演练"

    def finish_drill(self, training_id: int, operator: str) -> tuple[dict[str, Any] | None, str]:
        operator = operator.strip()
        if not operator:
            return None, "缺少必填字段：操作人"
        with self._lock(training_id):
            training = store.find(TRAINING_MODULE, training_id)
            if training is None:
                return None, f"培训 {training_id} 不存在或已归档"
            if training["status"] != STATUS_TRAINING:
                return None, f"只有培训中的演练可以结束，当前状态为{training['status']}，不能回退或重复结束"

            participants = self._participants(training_id)
            signed = [row for row in participants if row.get("签到状态") == "已签到"]
            if not signed:
                return None, "尚无人签到，不能结束演练；请先组织参训人员签到"

            timestamp = now_text()
            training["status"] = STATUS_ASSESSMENT
            training["结束演练人"] = operator
            training["结束演练时间"] = timestamp
            for participant in store.rows(PARTICIPANT_MODULE):
                if participant.get("培训ID") == training_id and participant.get("签到状态") == "已签到":
                    participant["status"] = STATUS_ASSESSMENT
                    participant["人员状态"] = STATUS_ASSESSMENT

            self._add_log(training_id, "结束演练", STATUS_ASSESSMENT, operator, timestamp, f"{len(signed)} 人进入考核成绩录入")
            return self.get_entry(training_id), "演练已结束，可逐条录入考核成绩"

    def submit_scores(
        self,
        training_id: int,
        operator: str,
        results: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
        operator = operator.strip()
        if not operator:
            return (
                {"ok": False, "message": "缺少必填字段：操作人", "entry": None},
                [],
                "缺少必填字段：操作人",
            )

        with self._lock(training_id):
            training = store.find(TRAINING_MODULE, training_id)
            if training is None:
                return (
                    {"ok": False, "message": f"培训 {training_id} 不存在或已归档", "entry": None},
                    [],
                    f"培训 {training_id} 不存在或已归档",
                )
            if training["status"] not in {STATUS_ASSESSMENT, STATUS_FINISHED}:
                message = f"只有待考核的培训可以录入成绩，当前状态为{training['status']}，状态不能回退"
                return (
                    {"ok": False, "message": message, "entry": self.get_entry(training_id)},
                    [],
                    message,
                )
            if not results:
                message = "未收到任何人员的考核成绩"
                return (
                    {"ok": False, "message": message, "entry": self.get_entry(training_id)},
                    [],
                    message,
                )

            outcome_rows: list[dict[str, Any]] = []
            success_count = 0
            timestamp = now_text()
            for item in results:
                participant_id = int(item.get("participantId") or 0)
                participant = self._find_participant(training_id, participant_id)
                if participant is None:
                    outcome_rows.append(
                        {
                            "ok": False,
                            "participantId": participant_id,
                            "participantName": "",
                            "message": f"参训人员 {participant_id} 不属于这场培训，成绩未生效",
                            "assessmentResult": "",
                            "entry": None,
                        }
                    )
                    continue

                if participant["score_submitted"]:
                    outcome_rows.append(
                        {
                            "ok": False,
                            "participantId": participant_id,
                            "participantName": participant["姓名"],
                            "message": (
                                f"{participant['姓名']} 的成绩已在 {participant['考核时间']} 录入为 "
                                f"{participant['考核成绩']} 分（{participant['考核结果']}），重复提交不生效"
                            ),
                            "assessmentResult": participant["考核结果"],
                            "entry": dict(participant),
                        }
                    )
                    continue

                raw_score = item.get("score")
                if raw_score is None or not str(raw_score).strip():
                    outcome_rows.append(
                        {
                            "ok": False,
                            "participantId": participant_id,
                            "participantName": participant["姓名"],
                            "message": f"{participant['姓名']} 的考核成绩未填写，不能按合格处理，仍停留在待考核",
                            "assessmentResult": RESULT_PENDING,
                            "entry": dict(participant),
                        }
                    )
                    continue

                try:
                    score_num = float(raw_score)
                except (TypeError, ValueError):
                    outcome_rows.append(
                        {
                            "ok": False,
                            "participantId": participant_id,
                            "participantName": participant["姓名"],
                            "message": f"{participant['姓名']} 的考核成绩必须是 0-100 的数字，未按合格处理",
                            "assessmentResult": RESULT_PENDING,
                            "entry": dict(participant),
                        }
                    )
                    continue

                if not 0 <= score_num <= 100:
                    outcome_rows.append(
                        {
                            "ok": False,
                            "participantId": participant_id,
                            "participantName": participant["姓名"],
                            "message": f"{participant['姓名']} 的考核成绩需在 0-100 分之间，本次未生效",
                            "assessmentResult": RESULT_PENDING,
                            "entry": dict(participant),
                        }
                    )
                    continue

                score_text = str(int(score_num)) if score_num.is_integer() else str(score_num)
                passed = score_num >= PASS_SCORE
                result = RESULT_PASSED if passed else RESULT_FAILED
                participant["考核成绩"] = score_text
                participant["考核结果"] = result
                participant["考核人"] = operator
                participant["考核时间"] = timestamp
                participant["score_submitted"] = True
                participant["abnormal"] = not passed
                if passed:
                    participant["status"] = STATUS_FINISHED
                    participant["人员状态"] = STATUS_FINISHED
                    participant["结业时间"] = timestamp
                else:
                    participant["status"] = "考核不合格"
                    participant["人员状态"] = "考核不合格"

                success_count += 1
                outcome_rows.append(
                    {
                        "ok": True,
                        "participantId": participant_id,
                        "participantName": participant["姓名"],
                        "message": f"{participant['姓名']} 成绩 {score_text} 分，考核{result}",
                        "assessmentResult": result,
                        "entry": dict(participant),
                    }
                )
                self._add_log(
                    training_id,
                    "录入考核成绩",
                    result,
                    operator,
                    timestamp,
                    f"{participant['姓名']}：{score_text} 分，{result}",
                )

            signed_rows = [
                row
                for row in store.rows(PARTICIPANT_MODULE)
                if row.get("培训ID") == training_id and row.get("签到状态") == "已签到"
            ]
            waiting_rows = [row for row in signed_rows if row.get("status") == STATUS_ASSESSMENT]
            if not waiting_rows and training["status"] == STATUS_ASSESSMENT:
                training["status"] = STATUS_FINISHED
                training["pending"] = False
                passed_count = sum(1 for row in signed_rows if row.get("考核结果") == RESULT_PASSED)
                failed_count = sum(1 for row in signed_rows if row.get("考核结果") == RESULT_FAILED)
                training["结业操作人"] = operator
                training["结业时间"] = now_text()
                self._add_log(
                    training_id,
                    "培训结业",
                    STATUS_FINISHED,
                    operator,
                    training["结业时间"],
                    f"合格 {passed_count} 人，不合格 {failed_count} 人；不合格人员不进入结业名单",
                )

            failure_count = sum(1 for row in outcome_rows if not row["ok"])
            if success_count and failure_count:
                summary = f"已生效 {success_count} 条，{failure_count} 条未生效；结果见逐条明细"
                ok = False
            elif success_count:
                summary = f"{success_count} 条考核成绩已生效"
                ok = True
            else:
                summary = f"{failure_count} 条提交均未生效；结果见逐条明细"
                ok = False
            return {"ok": ok, "message": summary, "entry": self.get_entry(training_id)}, outcome_rows, summary

    def graduates(
        self,
        *,
        keyword: str | None = None,
        post: str | None = None,
        device_type: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows: list[dict[str, Any]] = []
        for participant in store.rows(PARTICIPANT_MODULE):
            if participant.get("status") != STATUS_FINISHED or participant.get("考核结果") != RESULT_PASSED:
                continue
            training = store.find(TRAINING_MODULE, int(participant.get("培训ID", 0)))
            if training is None or training.get("status") != STATUS_FINISHED:
                continue
            row = dict(participant)
            row["培训名称"] = training.get("培训名称")
            row["授课师傅"] = training.get("授课师傅")
            rows.append(row)

        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("姓名", ""))
                or keyword in str(row.get("培训编号", ""))
                or keyword in str(row.get("培训名称", ""))
            ]
        if post:
            rows = [row for row in rows if post in str(row.get("岗位", ""))]
        if device_type:
            rows = [row for row in rows if device_type in str(row.get("设备类型", ""))]

        rows.sort(key=lambda row: (str(row.get("结业时间", "")), int(row.get("id", 0))), reverse=True)
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def _lock(self, training_id: int) -> Lock:
        with self._locks_guard:
            return self._locks.setdefault(training_id, Lock())

    def _next_id(self, module: str) -> int:
        return max((int(row.get("id", 0)) for row in store.rows(module)), default=0) + 1

    def _participants(self, training_id: int) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in store.rows(PARTICIPANT_MODULE)
            if row.get("培训ID") == training_id
        ]

    def _find_participant(self, training_id: int, participant_id: int) -> dict[str, Any] | None:
        for row in store.rows(PARTICIPANT_MODULE):
            if int(row.get("id", 0)) == participant_id and int(row.get("培训ID", 0)) == training_id:
                return row
        return None

    def _list_item(self, training: dict[str, Any]) -> dict[str, Any]:
        item = dict(training)
        item["状态"] = item.get("status")
        participants = self._participants(int(training.get("id", 0)))
        item.update(self._stats(participants))
        return item

    def _stats(self, participants: list[dict[str, Any]]) -> dict[str, int]:
        signed = [row for row in participants if row.get("签到状态") == "已签到"]
        return {
            "应到人数": len(participants),
            "已签到人数": len(signed),
            "待考核人数": sum(1 for row in signed if row.get("status") == STATUS_ASSESSMENT),
            "合格人数": sum(1 for row in participants if row.get("考核结果") == RESULT_PASSED),
            "不合格人数": sum(1 for row in participants if row.get("考核结果") == RESULT_FAILED),
        }

    def _normalized_names(self, value: Any) -> list[str]:
        if isinstance(value, str):
            candidates = re.split(r"[,，、;；\n\r]+", value)
        elif isinstance(value, list):
            candidates = value
        else:
            candidates = []
        names: list[str] = []
        for candidate in candidates:
            name = str(candidate or "").strip()
            if name and name not in names:
                names.append(name)
        return names

    def _add_log(
        self,
        training_id: int,
        action: str,
        target_status: str,
        operator: str,
        timestamp: str,
        remark: str,
    ) -> None:
        store.rows(LOG_MODULE).append(
            {
                "id": self._next_id(LOG_MODULE),
                "培训ID": training_id,
                "动作": action,
                "目标状态": target_status,
                "操作人": operator,
                "操作时间": timestamp,
                "说明": remark,
            }
        )


training_service = TrainingService()
