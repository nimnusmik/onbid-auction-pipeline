"""물건 상태 관리 (종료 감지)."""

import sqlite3


def mark_closed(
    conn: sqlite3.Connection,
    collected_ids: set,
    succeeded_groups: list[tuple[str, str]],
) -> int:
    """이번 수집에 나타나지 않은 active 물건을 closed로 마킹.

    낙찰되거나 취소된 물건은 API 응답에서 빠지므로 collected_ids에 없으면 종료로 간주.
    물건 자체는 삭제하지 않고 status만 변경해 이력 보존.

    부분 실패 보호:
      succeeded_groups 에 포함된 (cltr_usg_mcls_nm, cltr_usg_scls_nm) 조합의
      물건만 mark_closed 대상으로 한다. 실패한 그룹의 물건은 collected_ids 에
      들어있지 않으므로 보호 조건이 없으면 잘못 closed 처리될 수 있다.
    """
    if not succeeded_groups:
        # 모든 그룹이 실패했다면 손대지 않는다.
        return 0

    group_placeholders = ",".join(["(?, ?)"] * len(succeeded_groups))
    group_args = [v for grp in succeeded_groups for v in grp]

    if collected_ids:
        id_placeholders = ",".join("?" * len(collected_ids))
        sql = f"""
            UPDATE BID_ITEMS SET status='closed'
            WHERE status='active'
              AND pvct_trgt_yn != 'Y'
              AND cltr_mng_no NOT IN ({id_placeholders})
              AND (cltr_usg_mcls_nm, cltr_usg_scls_nm) IN ({group_placeholders})
        """
        params = list(collected_ids) + group_args
    else:
        # 성공 그룹이 모두 빈 결과를 반환한 정상 케이스 (드물지만 가능).
        sql = f"""
            UPDATE BID_ITEMS SET status='closed'
            WHERE status='active'
              AND pvct_trgt_yn != 'Y'
              AND (cltr_usg_mcls_nm, cltr_usg_scls_nm) IN ({group_placeholders})
        """
        params = group_args

    cursor = conn.execute(sql, params)
    conn.commit()
    return cursor.rowcount
