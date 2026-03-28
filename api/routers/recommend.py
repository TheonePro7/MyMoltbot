"""每日北单推荐 API。"""

from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/recommend", tags=["每日推荐"])


@router.get("/daily")
def get_daily(expect: str | None = Query(None, description="北单期号"),
              confidence: float = Query(0.6, description="最低置信度")):
    """获取每日北单推荐。"""
    try:
        from ai.daily_recommend import get_daily_recommendations
        return get_daily_recommendations(expect=expect, min_confidence=confidence)
    except Exception as e:
        return {"error": f"拉取失败: {str(e)}", "matches": [], "predictions": [], "parlays": {}}
