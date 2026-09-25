"""培训演练接口：培训排期、签到、结束演练、批量考核与结业名单。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.schemas import ActionResult, PageResult
from app.services.training import training_service

router = APIRouter(prefix="/api/training", tags=["培训演练"])


class TrainingCreatePayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)


class OperatorPayload(BaseModel):
    operator: str = Field(default="", description="当前操作人")
    participantId: int | None = Field(default=None, description="签到的参训人员 ID")


class ScoreItemPayload(BaseModel):
    participantId: int
    score: str | None = Field(default=None, description="0-100 分；空值不会当成合格")


class ScoreSubmitPayload(BaseModel):
    operator: str = Field(default="", description="考核成绩录入人")
    results: list[ScoreItemPayload] = Field(default_factory=list)


@router.get("/graduates", response_model=PageResult[dict])
def list_graduates(
    keyword: str | None = None,
    post: str | None = None,
    deviceType: str | None = None,
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """只返回已完成且成绩合格的人员；待考核和不合格记录不会进入结业名单。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = training_service.graduates(
        keyword=keyword,
        post=post,
        device_type=deviceType,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = None,
    status: str | None = None,
    post: str | None = None,
    deviceType: str | None = None,
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按培训编号/名称、岗位、设备类型和状态查询排期。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = training_service.list_entries(
        keyword=keyword,
        status=status,
        post=post,
        device_type=deviceType,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取培训详情、参训人员与每一步的操作人、时间。"""
    entry = training_service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"培训 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_training(payload: TrainingCreatePayload) -> ActionResult:
    """按岗位和设备类型排期，并一次性建立参训人员记录。"""
    entry, message = training_service.create_training(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/sign-in", response_model=ActionResult)
def sign_in(entry_id: int, payload: OperatorPayload) -> ActionResult:
    """人员签到；第一次签到会让培训从待开班进入培训中。"""
    if payload.participantId is None:
        return ActionResult(ok=False, message="缺少必填字段：参训人员")
    entry, message = training_service.sign_in(entry_id, payload.participantId, payload.operator)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/finish-drill", response_model=ActionResult)
def finish_drill(entry_id: int, payload: OperatorPayload) -> ActionResult:
    """签到后的人员进入待考核；未签到人员不参与考核。"""
    entry, message = training_service.finish_drill(entry_id, payload.operator)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/scores", response_model=dict)
def submit_scores(entry_id: int, payload: ScoreSubmitPayload) -> dict[str, Any]:
    """同一场演练可一次提交多人成绩，逐条返回成功或失败结果。"""
    summary, results, _ = training_service.submit_scores(
        entry_id,
        payload.operator,
        [item.model_dump() for item in payload.results],
    )
    return {**summary, "results": results}
