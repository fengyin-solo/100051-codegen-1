"""培训演练接口：按岗位与设备类型排期，覆盖开班签到、结束演练、成绩录入与确认结业。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult, ScoreBatchResult
from app.services.train import TrainService

router = APIRouter(prefix="/api/train", tags=["培训演练"])

service = TrainService()

LIST_FIELDS = ["培训编号", "培训岗位", "设备类型", "计划开班日期", "培训讲师", "演练项目", "学员人数", "培训状态"]
STATUSES = ["待开班", "培训中", "待考核", "已结业"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按培训编号检索"),
    status: str | None = Query(default=None, description="待开班、培训中、待考核、已结业"),
    position: str | None = Query(default=None, description="按培训岗位检索"),
    device: str | None = Query(default=None, description="按设备类型检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按编号、岗位、设备类型与状态过滤培训列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, position=position, device=device, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def status_stats() -> dict[str, Any]:
    """各状态班次数量：给页头的统计卡片用。"""
    return {"module": "train", "counts": service.status_counts()}


@router.get("/graduates")
def graduate_roster() -> dict[str, Any]:
    """结业名单：只列已结业班次里考核合格的学员，未结业的记录不会出现。"""
    roster = service.graduates()
    return {"module": "train", "total": len(roster), "items": roster}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出培训演练清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "train", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条培训演练明细（含学员成绩与操作日志）；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"培训演练 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一个培训班次，按岗位与设备类型排期；缺字段时说明原因而不是静默丢弃。"""
    entry, message = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message="培训班次已登记排期", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行开班签到、结束演练、确认结业；状态只能逐档前进，违规动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    operator = str(payload.values.get("操作人") or "").strip()
    entry, message = service.run_action(entry_id, action, operator)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/scores", response_model=ScoreBatchResult)
def record_scores(entry_id: int, payload: EntryPayload) -> ScoreBatchResult:
    """批量录入考核成绩：逐条给出结果，已录入的学员重复提交不再生效。"""
    raw_items = payload.values.get("成绩列表") or []
    items = raw_items if isinstance(raw_items, list) else []
    operator = str(payload.values.get("操作人") or "").strip()
    entry, results, message = service.record_scores(entry_id, items, operator)
    ok = entry is not None and all(item["ok"] for item in results) and bool(results)
    return ScoreBatchResult(ok=ok, message=message, entry=entry, results=results)
