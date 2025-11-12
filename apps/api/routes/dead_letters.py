# """死信查询接口。"""
#
# from __future__ import annotations
#
# from datetime import datetime
# from typing import Optional
#
# from fastapi import APIRouter, Depends, Query
#
# from apps.repositories.dead_letter_repository import DeadLetterRepository
#
#
# router = APIRouter(prefix="/dead-letters", tags=["DeadLetters"])
#
#
# def get_repository() -> DeadLetterRepository:
#     return DeadLetterRepository()
#
#
# @router.get("")
# async def list_dead_letters(
#     mac: Optional[str] = Query(None, description="按 MAC 过滤"),
#     limit: int = Query(50, ge=1, le=200),
#     offset: int = Query(0, ge=0),
#     from_ts: Optional[datetime] = Query(None, alias="from_ts"),
#     repo: DeadLetterRepository = Depends(get_repository),
# ) -> dict[str, object]:
#     items = await repo.list_dead_letters(mac=mac, limit=limit, offset=offset, from_ts=from_ts)
#     return {"items": items, "total": len(items)}
