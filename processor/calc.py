"""감정가 비율 계산 로직."""


def calc_ratio(item: dict) -> float | None:
    """감정가 대비 최저입찰가 비율(%) 계산.
    API가 apslPrcCtrsLowstBidRto를 직접 제공하면 그 값을 사용하고,
    없으면 apslEvlAmt / lowstBidPrcIndctCont로 직접 계산.
    """
    ratio = item.get("apslPrcCtrsLowstBidRto")
    if ratio is not None:
        try:
            return round(float(ratio), 2)
        except Exception:
            pass
    try:
        apsl = float(item.get("apslEvlAmt") or 0)
        lowst = float(item.get("lowstBidPrcIndctCont") or 0)
        if apsl > 0 and lowst > 0:
            return round(lowst / apsl * 100, 2)
    except Exception:
        pass
    return None
