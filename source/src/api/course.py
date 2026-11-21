# 코스 생성 로직 (DB/외부 API 없는 순수 함수). main.py의 /courses/recommend가 사용
import math
from datetime import datetime, timedelta

from source.src.hours import describe, is_open

# 코스 순서와 장소별 머무는 시간(분)
COURSE_ORDER = ["관광지", "카페", "소품샵", "맛집"]
STAY_MINUTES = {"관광지": 90, "카페": 60, "소품샵": 40, "맛집": 70, "테마파크": 300}
UNKNOWN_HOURS_PENALTY = 0.3   # 영업시간 정보 없는 곳은 확인된 곳보다 약간 뒤로

# 교통수단별 평균 속도(km/h)와 탐색 반경(km)
SPEED_KMH = {"자동차": 35, "대중교통": 20, "KTX/기차": 35, "도보": 4}
SEARCH_RADIUS_KM = {"자동차": 30, "대중교통": 15, "KTX/기차": 15, "도보": 2}
DEFAULT_TRANSPORT = "대중교통"
MAX_HOP_KM = {"자동차": 15, "대중교통": 5, "KTX/기차": 5, "도보": 1.5}   # 다음 장소까지 최대 거리

DIST_WEIGHT = 0.3          # 1km 멀어질 때마다 깎는 점수
MOOD_BONUS = 1.0           # 원하는 분위기 태그가 있으면 더하는 점수
NEGATIVE_RATIO_LIMIT = 0.4  # 후기 3개 이상 & 부정 비율 이 이상이면 '생각보다 별로' → 제외


def haversine_km(lat1, lng1, lat2, lng2):
    """두 좌표 사이 직선거리(km)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def is_disliked(p):
    return (p.get("review_count") or 0) >= 3 and (p.get("negative_ratio") or 0) >= NEGATIVE_RATIO_LIMIT


def _travel_min(dist_km, transport):
    return round(dist_km / SPEED_KMH[transport] * 60) + 5      # +5분: 출발/주차/도보 여유


def _minutes(t):
    return t.hour * 60 + t.minute


def build_course(origin, places, start="09:00", transport=None, mood=None, weekday=None, anchor=None):
    """origin {name, lat, lng}에서 출발해 COURSE_ORDER 순서로 가깝고 점수 높고 도착 시각에 영업 중인 곳을 하나씩 고름.

    places: [{id, name, category, address, lat, lng, score, moods[], review_count, negative_ratio, hours}]
    weekday: '월'~'일' (None이면 영업시간 확인 안 함)
    anchor: 꼭 들를 장소(테마파크 등, place와 같은 모양). 있으면 첫 방문지로 고정하고 관광지 단계는 생략.
            origin과 같은 곳이면(anchor["id"] == origin.get("id")) 출발지 자체를 그 장소로 봄
    반환: steps [{time, category, place, alternatives[2], travel_min, hours_today, warning}] (후보 없는 단계는 건너뜀)
    """
    # ponytail: 탐욕(greedy) 방식 + 직선거리. 실제 이동시간이 필요하면 길찾기 API(네이버 Directions)로 교체
    transport = transport if transport in SPEED_KMH else DEFAULT_TRANSPORT
    t = datetime.strptime(start, "%H:%M")
    cur = (origin["lat"], origin["lng"])
    used = set()
    steps = [{"time": start, "category": "출발", "travel_min": 0, "alternatives": [], "hours_today": None, "warning": None,
              "place": {"id": 0, "name": origin["name"], "category": "출발", "address": origin.get("address", ""),
                        "lat": origin["lat"], "lng": origin["lng"]}}]
    order = COURSE_ORDER

    if anchor:
        stay = STAY_MINUTES.get(anchor["category"], STAY_MINUTES["테마파크"])
        if anchor["id"] == origin.get("id"):
            travel = 0
            steps.pop()                                         # 출발지 = 테마파크
        else:
            travel = _travel_min(haversine_km(*cur, anchor["lat"], anchor["lng"]), transport)
            t += timedelta(minutes=travel)
        opened = is_open(anchor.get("hours"), weekday, _minutes(t), stay) if weekday else None
        steps.append({"time": t.strftime("%H:%M"), "category": anchor["category"], "travel_min": travel,
                      "place": anchor, "alternatives": [], "hours_today": describe(anchor.get("hours"), weekday),
                      "warning": "도착 시각에 영업하지 않을 수 있어요" if opened is False else None})
        used.add(anchor["id"])
        cur = (anchor["lat"], anchor["lng"])
        t += timedelta(minutes=stay)
        order = [c for c in COURSE_ORDER if c != "관광지"]

    for category in order:
        stay = STAY_MINUTES[category]
        ranked = []
        for p in places:
            if p["category"] != category or p["id"] in used or is_disliked(p):
                continue
            dist = haversine_km(*cur, p["lat"], p["lng"])
            if dist > MAX_HOP_KM[transport]:
                continue
            rank = (p.get("score") or 0) - dist * DIST_WEIGHT + (MOOD_BONUS if mood and mood in (p.get("moods") or []) else 0)
            if weekday:
                opened = is_open(p.get("hours"), weekday, _minutes(t + timedelta(minutes=_travel_min(dist, transport))), stay)
                if opened is False:
                    continue                                    # 휴무 / 영업 전후 / 브레이크타임 / 라스트오더 지남
                if opened is None:
                    rank -= UNKNOWN_HOURS_PENALTY
            ranked.append((rank, dist, p))
        if not ranked:
            continue
        ranked.sort(key=lambda r: r[0], reverse=True)
        _, dist, best = ranked[0]
        travel = _travel_min(dist, transport)
        t += timedelta(minutes=travel)
        steps.append({"time": t.strftime("%H:%M"), "category": category, "travel_min": travel,
                      "place": best, "alternatives": [r[2] for r in ranked[1:3]],
                      "hours_today": describe(best.get("hours"), weekday), "warning": None})
        used.add(best["id"])
        cur = (best["lat"], best["lng"])
        t += timedelta(minutes=stay)
    return steps


if __name__ == "__main__":
    assert round(haversine_km(37.5665, 126.9780, 37.5796, 126.9770), 1) == 1.5   # 시청 → 경복궁 약 1.5km
    base = {"address": "", "moods": [], "review_count": 1, "negative_ratio": 0}
    places = [
        {**base, "id": 1, "name": "가까운카페", "category": "카페", "lat": 37.5670, "lng": 126.9780, "score": 1},
        {**base, "id": 2, "name": "먼카페", "category": "카페", "lat": 37.6000, "lng": 126.9780, "score": 1.5},
        {**base, "id": 3, "name": "별로식당", "category": "맛집", "lat": 37.5671, "lng": 126.9781, "score": 3,
         "review_count": 5, "negative_ratio": 0.6},
        {**base, "id": 4, "name": "좋은식당", "category": "맛집", "lat": 37.5672, "lng": 126.9782, "score": 1},
        {**base, "id": 5, "name": "조용한카페", "category": "카페", "lat": 37.5671, "lng": 126.9780, "score": 0.5,
         "moods": ["조용한"]},
    ]
    origin = {"name": "시청", "lat": 37.5665, "lng": 126.9780}
    steps = build_course(origin, places, "09:00", "대중교통")
    assert [s["place"]["name"] for s in steps] == ["시청", "가까운카페", "좋은식당"], steps   # 먼 곳·별로인 곳 제외
    assert steps[1]["time"] == "09:05" and steps[2]["time"] == "10:10"
    assert build_course(origin, places, "09:00", "대중교통", "조용한")[1]["place"]["name"] == "조용한카페"

    # 영업시간: 월요일 휴무인 '가까운카페'는 빠지고, 영업 중인 '조용한카페'가 선택됨
    places[0]["hours"] = {"월": None}
    places[4]["hours"] = {"월": {"open": "08:00", "close": "22:00", "breaks": [], "last_order": None}}
    s = build_course(origin, places, "09:00", "대중교통", weekday="월")
    assert s[1]["place"]["name"] == "조용한카페" and s[1]["hours_today"] == "08:00~22:00", s
    assert build_course(origin, places, "09:00", "대중교통", weekday="화")[1]["place"]["name"] == "가까운카페"  # 화요일 정보 없음 → 점수순

    # 테마파크 고정: 첫 방문지가 테마파크, 관광지 단계 생략, 5시간 뒤 근처 카페
    park = {**base, "id": 9, "name": "테마파크", "category": "테마파크", "lat": 37.5668, "lng": 126.9780, "score": 2,
            "hours": {"월": {"open": "10:00", "close": "21:00", "breaks": [], "last_order": None}}}
    s = build_course(origin, places, "09:00", "대중교통", weekday="월", anchor=park)
    assert [x["category"] for x in s][:3] == ["출발", "테마파크", "카페"] and s[1]["warning"] == "도착 시각에 영업하지 않을 수 있어요"
    assert s[2]["time"] == "14:10", s[2]["time"]     # 09:05 도착 + 300분 + 이동 5분
    s = build_course({**park, "name": "테마파크"}, places, "10:00", "대중교통", weekday="월", anchor=park)
    assert s[0]["category"] == "테마파크" and s[0]["warning"] is None
    print("ok")
