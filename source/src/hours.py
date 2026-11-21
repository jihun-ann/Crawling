# 영업시간 파싱 / 영업 여부 판단 (순수 함수). 수집은 blog_content_loader.fetch_hours, 판단은 api/course.py
#
# 저장 형식 (place.business_hours, JSON):
#   {"월": {"open": "11:00", "close": "21:00", "breaks": [["15:00", "17:00"]], "last_order": "20:00"},
#    "화": null,            ← 휴무
#    ...}                   ← 키가 없는 요일 = 정보 없음
WEEKDAYS = "월화수목금토일"     # date.weekday() 순서


def _min(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def parse_naver_hours(new_business_hours):
    """네이버 플레이스 newBusinessHours → 저장 형식 dict. 정보가 없으면 None."""
    if not new_business_hours:
        return None
    result = {}
    for info in new_business_hours[0].get("businessHours") or []:
        day = (info.get("day") or "").strip()
        bh = info.get("businessHours")
        value = None
        if bh and bh.get("start") and bh.get("end"):
            last = next((lo.get("time") for lo in info.get("lastOrderTimes") or [] if lo.get("time")), None)
            value = {"open": bh["start"], "close": bh["end"],
                     "breaks": [[b["start"], b["end"]] for b in info.get("breakHours") or [] if b.get("start") and b.get("end")],
                     "last_order": last}
        days = WEEKDAYS if day == "매일" else WEEKDAYS[:5] if day == "평일" else "토일" if day == "주말" else day
        for d in days:
            if d in WEEKDAYS:
                result[d] = value
    return result or None


def open_days(hours):
    """영업하는 요일 문자열 (예: '월수목금토일'). 정보 없으면 None."""
    return "".join(d for d in WEEKDAYS if hours.get(d)) if hours else None


def is_open(hours, weekday, arrive_min, stay_min=60):
    """weekday('월'~'일')에 arrive_min(자정 기준 분)에 도착해 들어갈 수 있는지. True/False, 정보 없으면 None.

    기준: 영업 중이고, 브레이크타임이 아니고, 라스트오더 전이며, 마감까지 min(머무는 시간, 30분) 이상 남음.
    """
    if not hours or weekday not in hours:
        return None
    day = hours[weekday]
    if day is None:
        return False                                   # 휴무일
    open_, close = _min(day["open"]), _min(day["close"])
    if close <= open_:
        close += 24 * 60                               # 새벽 마감 (예: 18:00~02:00)
    if not (open_ <= arrive_min <= close - min(stay_min, 30)):
        return False
    if any(_min(s) <= arrive_min < _min(e) for s, e in day.get("breaks") or []):
        return False
    if day.get("last_order") and arrive_min > _min(day["last_order"]) + (24 * 60 if _min(day["last_order"]) < open_ else 0):
        return False
    return True


def describe(hours, weekday):
    """화면 표시용 문구. 예: '11:00~21:00 (브레이크 15:00~17:00)', '휴무', 정보 없으면 None."""
    if not hours or weekday not in hours:
        return None
    day = hours[weekday]
    if day is None:
        return "휴무"
    text = f"{day['open']}~{day['close']}"
    if day.get("breaks"):
        text += " (브레이크 " + ", ".join(f"{s}~{e}" for s, e in day["breaks"]) + ")"
    return text


if __name__ == "__main__":
    raw = [{"businessHours": [
        {"day": "일", "businessHours": {"start": "11:00", "end": "21:00"}, "breakHours": [{"start": "15:00", "end": "17:00"}],
         "lastOrderTimes": [{"type": "라스트오더", "time": "20:00"}]},
        {"day": "월", "businessHours": None, "description": "정기휴무 (매주 월요일)"},
    ]}]
    h = parse_naver_hours(raw)
    assert h["월"] is None and h["일"]["breaks"] == [["15:00", "17:00"]] and "화" not in h
    assert is_open(h, "일", _min("12:00")) is True
    assert is_open(h, "일", _min("15:30")) is False          # 브레이크
    assert is_open(h, "일", _min("20:30")) is False          # 라스트오더 지남
    assert is_open(h, "일", _min("10:00")) is False          # 오픈 전
    assert is_open(h, "월", _min("12:00")) is False          # 휴무
    assert is_open(h, "화", _min("12:00")) is None           # 정보 없음
    night = parse_naver_hours([{"businessHours": [{"day": "매일", "businessHours": {"start": "18:00", "end": "02:00"}}]}])
    assert is_open(night, "금", _min("23:00")) is True and open_days(night) == WEEKDAYS
    assert describe(h, "일") == "11:00~21:00 (브레이크 15:00~17:00)" and describe(h, "월") == "휴무"
    print("ok")
