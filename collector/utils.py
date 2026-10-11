"""collector 공통 유틸리티."""

from datetime import datetime


def to_int(v) -> int | None:
    try:
        return int(float(v)) if v not in (None, "", "null") else None
    except Exception:
        return None


def to_float(v) -> float | None:
    try:
        return float(v) if v not in (None, "", "null") else None
    except Exception:
        return None


def to_str(v) -> str | None:
    return str(v).strip() if v not in (None, "", "null") else None


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def to_list(v) -> list:
    """API 응답에서 배열 필드를 안전하게 리스트로 변환.
    - None / 빈 문자열 → 빈 리스트
    - dict(단건)       → [dict]
    - list             → list 그대로
    """
    if not v:
        return []
    if isinstance(v, dict):
        return [v]
    if isinstance(v, list):
        return v
    return []
