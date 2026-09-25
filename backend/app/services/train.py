"""培训演练业务规则：排期、签到、成绩录入与结业流转都收在这里。

状态序列固定为 待开班 → 培训中 → 待考核 → 已结业，只允许逐档前进，
任何动作都不能把记录带回上一档；每一步都在「日志」里留下操作人与时间。
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from app.store import store

MODULE = "train"
REQUIRED_FIELDS = ["培训岗位", "设备类型", "计划开班日期", "培训讲师"]
DEVICE_TYPES = ["信号机", "转辙机", "轨道电路", "联锁设备", "列车防护"]
STATUS_ORDER = ["待开班", "培训中", "待考核", "已结业"]
ACTION_RULES = {"开班签到": "培训中", "结束演练": "待考核", "确认结业": "已结业"}
PASS_SCORE_DEFAULT = 60.0

# 同一场演练可能多人同时提交成绩，用锁把每一批处理串行化，避免互相覆盖。
_lock = threading.Lock()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_trainees(raw: Any) -> list[str]:
    """学员名单兼容逗号、顿号分隔的字符串和数组，去重去空。"""
    if isinstance(raw, str):
        parts = raw.replace("，", "、").replace(",", "、").split("、")
    elif isinstance(raw, list):
        parts = [str(item) for item in raw]
    else:
        parts = []
    names: list[str] = []
    for part in parts:
        name = part.strip()
        if name and name not in names:
            names.append(name)
    return names


def _parse_pass_line(raw: Any) -> float | None:
    """合格线留空时按 60 分计；填了就必须是 0-100 的数字。"""
    if raw is None or str(raw).strip() == "":
        return PASS_SCORE_DEFAULT
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not 0 <= value <= 100:
        return None
    return value


class TrainService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        position: str | None = None,
        device: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("培训编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if position:
            rows = [row for row in rows if position in str(row.get("培训岗位", ""))]
        if device:
            rows = [row for row in rows if row.get("设备类型") == device]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def status_counts(self) -> dict[str, int]:
        counts = {name: 0 for name in STATUS_ORDER}
        for row in store.rows(MODULE):
            name = str(row.get("status", ""))
            if name in counts:
                counts[name] += 1
        return counts

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        device = str(values.get("设备类型") or "").strip()
        if device not in DEVICE_TYPES:
            return None, f"设备类型「{device}」不在可排期范围：{'、'.join(DEVICE_TYPES)}"
        names = _parse_trainees(values.get("学员名单"))
        if not names:
            return None, "学员名单为空，培训班次至少需要一名学员"
        operator = str(values.get("操作人") or "").strip()
        if not operator:
            return None, "请填写操作人，登记排期需要记录操作人与时间"
        pass_line = _parse_pass_line(values.get("合格线"))
        if pass_line is None:
            return None, "合格线需要是 0-100 的数字，留空则按 60 分计"
        rows = store.rows(MODULE)
        entry_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        code = str(values.get("培训编号") or "").strip() or f"TRAIN-{entry_id:04d}"
        if any(row.get("培训编号") == code for row in rows):
            return None, f"培训编号「{code}」已存在，请更换编号"
        participants = [
            {"姓名": name, "签到": False, "签到时间": None, "成绩": None, "考核结论": None, "成绩录入人": None, "成绩录入时间": None}
            for name in names
        ]
        entry: dict[str, Any] = {
            "id": entry_id,
            "status": STATUS_ORDER[0],
            "pending": True,
            "abnormal": False,
            "培训编号": code,
            "培训岗位": str(values["培训岗位"]).strip(),
            "设备类型": device,
            "计划开班日期": str(values["计划开班日期"]).strip(),
            "培训讲师": str(values["培训讲师"]).strip(),
            "演练项目": str(values.get("演练项目") or "").strip() or "设备检修实操演练",
            "合格线": pass_line,
            "学员人数": len(participants),
            "培训状态": STATUS_ORDER[0],
            "participants": participants,
            "日志": [],
        }
        self._append_log(entry, operator, "登记排期", f"按{entry['培训岗位']}·{device}排期，计划 {entry['计划开班日期']} 开班，学员 {len(participants)} 人")
        rows.append(entry)
        return entry, ""

    def run_action(self, entry_id: int, action: str, operator: str) -> tuple[dict[str, Any] | None, str]:
        with _lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"培训演练 {entry_id} 不存在或已归档"
            if not operator:
                return None, "请填写操作人，培训流转需要记录操作人与时间"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于培训演练可执行范围"
            current = str(entry.get("status", ""))
            target = ACTION_RULES[action]
            if current not in STATUS_ORDER:
                return None, f"当前状态「{current}」不在允许的状态序列里，请联系管理员核对数据"
            current_idx = STATUS_ORDER.index(current)
            target_idx = STATUS_ORDER.index(target)
            if target_idx <= current_idx:
                return None, f"当前状态为「{current}」，不能{action}，状态不能回到上一档"
            if target_idx > current_idx + 1:
                return None, f"当前状态为「{current}」，不能跳档{action}，请按顺序流转"
            if action == "确认结业":
                unassessed = [p["姓名"] for p in entry["participants"] if not p.get("考核结论")]
                if unassessed:
                    return None, f"还有 {len(unassessed)} 人未录入考核成绩：{'、'.join(unassessed)}，不能确认结业"
            if action == "开班签到":
                signed_at = _now()
                for participant in entry["participants"]:
                    participant["签到"] = True
                    participant["签到时间"] = signed_at
            entry["status"] = target
            entry["培训状态"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            if action == "确认结业":
                entry["结业时间"] = _now()
            self._append_log(entry, operator, action, self._action_note(action, entry))
            return entry, f"培训演练已{action}"

    def record_scores(
        self,
        entry_id: int,
        items: list[dict[str, Any]],
        operator: str,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str]:
        """批量录入成绩：逐条给出结果，已录入的学员重复提交不再生效。"""
        with _lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, [], f"培训演练 {entry_id} 不存在或已归档"
            if not operator:
                return None, [], "请填写操作人，成绩录入需要记录操作人与时间"
            current = str(entry.get("status", ""))
            if current != "待考核":
                return None, [], f"当前状态为「{current}」，不能录入考核成绩，请先结束演练"
            if not items:
                return None, [], "未收到任何成绩记录，请至少填写一名学员的成绩"
            results: list[dict[str, Any]] = []
            recorded = 0
            for item in items:
                item = item or {}
                name = str(item.get("学员") or "").strip()
                raw = item.get("成绩")
                participant = next((p for p in entry["participants"] if p["姓名"] == name), None) if name else None
                if participant is None:
                    results.append({"trainee": name or "（未署名）", "ok": False, "message": f"学员「{name or '未署名'}」不在本场演练名单里，成绩未受理"})
                    continue
                if participant.get("考核结论"):
                    results.append({"trainee": name, "ok": False, "message": f"{name} 的成绩已录入（{participant['成绩']}分，{participant['考核结论']}），重复提交不再生效"})
                    continue
                if raw is None or str(raw).strip() == "":
                    results.append({"trainee": name, "ok": False, "message": f"{name} 未填写考核成绩，不能按合格处理，请补录成绩后再提交"})
                    continue
                try:
                    score = float(raw)
                except (TypeError, ValueError):
                    results.append({"trainee": name, "ok": False, "message": f"{name} 的成绩「{raw}」不是有效数字，请填写 0-100 之间的分数"})
                    continue
                if not 0 <= score <= 100:
                    results.append({"trainee": name, "ok": False, "message": f"{name} 的成绩 {score} 超出 0-100 范围，成绩未受理"})
                    continue
                pass_line = float(entry.get("合格线") or PASS_SCORE_DEFAULT)
                conclusion = "合格" if score >= pass_line else "不合格"
                participant["成绩"] = score
                participant["考核结论"] = conclusion
                participant["成绩录入人"] = operator
                participant["成绩录入时间"] = _now()
                recorded += 1
                results.append({"trainee": name, "ok": True, "message": f"{name}：{score}分，{conclusion}"})
            if recorded:
                passed = sum(1 for p in entry["participants"] if p.get("考核结论") == "合格")
                failed = sum(1 for p in entry["participants"] if p.get("考核结论") == "不合格")
                self._append_log(entry, operator, "录入成绩", f"本次新录入 {recorded} 人；累计合格 {passed} 人、不合格 {failed} 人")
            applied = sum(1 for result in results if result["ok"])
            summary = f"本次提交 {len(results)} 条，生效 {applied} 条"
            if applied < len(results):
                summary += "，未生效的请按逐条说明处理后重试"
            return entry, results, summary

    def graduates(self) -> list[dict[str, Any]]:
        """结业名单：只收录已结业班次里考核合格的学员，未结业记录一律不出现。"""
        roster: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            if row.get("status") != STATUS_ORDER[-1]:
                continue
            roster.append({
                "id": row["id"],
                "培训编号": row["培训编号"],
                "培训岗位": row["培训岗位"],
                "设备类型": row["设备类型"],
                "培训讲师": row["培训讲师"],
                "演练项目": row["演练项目"],
                "结业时间": row.get("结业时间"),
                "结业学员": [p["姓名"] for p in row["participants"] if p.get("考核结论") == "合格"],
                "未通过学员": [p["姓名"] for p in row["participants"] if p.get("考核结论") == "不合格"],
            })
        return roster

    @staticmethod
    def _action_note(action: str, entry: dict[str, Any]) -> str:
        if action == "开班签到":
            return f"学员 {len(entry['participants'])} 人完成签到，进入演练环节"
        if action == "结束演练":
            return "演练环节结束，等待录入考核成绩"
        passed = sum(1 for p in entry["participants"] if p.get("考核结论") == "合格")
        failed = sum(1 for p in entry["participants"] if p.get("考核结论") == "不合格")
        return f"考核合格 {passed} 人结业，不合格 {failed} 人待补考"

    @staticmethod
    def _append_log(entry: dict[str, Any], operator: str, action: str, note: str) -> None:
        entry.setdefault("日志", []).append({"时间": _now(), "操作人": operator, "动作": action, "说明": note})
