"""알림 관련 enum 정의."""

from enum import Enum


# 알림 종류: 감정가 비율 조건 / 마감 임박 / 수의계약 전환
class AlertType(str, Enum):
    RATIO    = "ratio"     # 감정가 대비 비율 조건 충족
    DEADLINE = "deadline"  # 마감 3일 이내
    PVCT     = "pvct"      # 수의계약 전환


# 알림 발송 결과 상태
class AlertStatus(str, Enum):
    SUCCESS = "success"    # 이메일 발송 성공
    FAIL    = "fail"       # 발송 실패 (네트워크 오류 등)
    SKIP    = "skip"       # 이미 보낸 물건이라 건너뜀
