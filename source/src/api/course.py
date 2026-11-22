# 코스 생성 로직 (DB/외부 API 없는 순수 함수). main.py의 /courses/recommend가 사용
import math
from datetime import datetime, timedelta

from source.src.hours import describe, is_open

# 코스에 넣는 종류와 장소별 머무는 시간(분). 순서는 고정이 아니라 시간대/영업시간/다양성으로 매번 고름
COURSE_ORDER = ["관광지", "카페", "소품샵", "맛집"]
STAY_MINUTES = {"관광지": 90, "카페": 60, "소품샵": 40, "맛집": 70}
MEAL_WINDOWS = [(11 * 60 + 30, 13 * 60 + 30), (17 * 60 + 30, 19 * 60 + 30)]   # 점심/저녁: 이때만, 시간대마다 1번 맛집
MEAL_BONUS = 5.0            # 식사 시간대엔 맛집을 최우선
AFTER_MEAL_CAFE_BONUS = 0.5  # 밥 먹고 카페
REPEAT_PENALTY = 1.0        # 이미 간 종류 1번당 감점 → 여러 종류가 섞이게
WAIT_MINUTES = 30           # 지금 열린 곳이 없으면 이만큼 기다렸다 다시 찾음 (예: 10시 오픈 카페)
DEFAULT_END = "20:00"
# 일부러 찾아가는 가볼만한 곳(anchor) 체류 시간: 종일 노는 곳은 길게, 나머지는 2시간
LONG_STAY_WORDS = ("테마파크", "워터파크", "놀이", "스키")
LONG_STAY, SPOT_STAY = 300, 120


def spot_stay(spot_type):
    return LONG_STAY if any(w in (spot_type or "") for w in LONG_STAY_WORDS) else SPOT_STAY
UNKNOWN_HOURS_PENALTY = 0.3   # 영업시간 정보 없는 곳은 확인된 곳보다 약간 뒤로

# 교통수단별 평균 속도(km/h)와 탐색 반경(km)
SPEED_KMH = {"자동차": 35, "대중교통": 20, "KTX/기차": 35, "도보": 4}
SEARCH_RADIUS_KM = {"자동차": 30, "대중교통": 15, "KTX/기차": 15, "도보": 2}
DEFAULT_TRANSPORT = "대중교통"
MAX_HOP_KM = {"자동차": 15, "대중교통": 5, "KTX/기차": 5, "도보": 1.5}   # 다음 장소까지 최대 거리

DIST_WEIGHT = 0.3          # 1km 멀어질 때마다 깎는 점수
MOOD_BONUS = 1.0           # 원하는 분위기 태그가 있으면 더하는 점수
NEGATIVE_RATIO_LIMIT = 0.4  # 후기 3개 이상 & 부정 비율 이 이상이면 '생각보다 별로' → 제외
ALTERNATIVES = 5           # 단계별로 함께 보여줄 다른 후보 수 (추천 1곳 + 최대 5곳)


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


def _meal_window(minute):
    """그 시각이 속한 식사 시간대 번호. 아니면 None."""
    return next((i for i, (a, b) in enumerate(MEAL_WINDOWS) if a <= minute <= b), None)


def build_course(origin, places, start="09:00", transport=None, mood=None, weekday=None, anchor=None, end=DEFAULT_END,
                 meals_done=None, history=None, used=None):
    """origin {name, lat, lng}에서 출발해 end까지, 매번 '지금 갈 수 있는 곳' 중 가장 좋은 곳을 다음 장소로 고름.

    다음 장소 점수 = 인기 점수 - 거리 + 분위기 + 식사 시간대 맛집 / 밥 다음 카페 - 이미 간 종류 감점
    제외: 직전과 같은 종류, 식사 시간대가 아닌 맛집, 도착~머무는 동안 영업 안 함, end 안에 못 끝남
    places: [{id, name, category, address, lat, lng, score, moods[], review_count, negative_ratio, hours}]
    weekday: '월'~'일' (None이면 영업시간 확인 안 함)
    anchor: 꼭 들를 장소(테마파크 등, place와 같은 모양). 있으면 첫 방문지로 고정.
            origin과 같은 곳이면(anchor["id"] == origin.get("id")) 출발지 자체를 그 장소로 봄
    반환: steps [{time, category, place, alternatives[ALTERNATIVES], travel_min, hours_today, warning}]
    """
    # ponytail: 탐욕(greedy) 방식 + 직선거리. 실제 이동시간이 필요하면 길찾기 API(네이버 Directions)로 교체
    transport = transport if transport in SPEED_KMH else DEFAULT_TRANSPORT
    t = datetime.strptime(start, "%H:%M")
    end_min = _minutes(datetime.strptime(end, "%H:%M"))
    cur = (origin["lat"], origin["lng"])
    # meals_done/history: 앞 구간(가는 길)에서 이어받는 식사 시간대·방문 종류. 넘기면 그 객체를 갱신
    used = set() if used is None else used
    meals_done = set() if meals_done is None else meals_done
    history = [] if history is None else history
    steps = [{"time": start, "category": "출발", "travel_min": 0, "alternatives": [], "hours_today": None, "warning": None,
              "place": {"id": 0, "name": origin["name"], "category": "출발", "address": origin.get("address", ""),
                        "lat": origin["lat"], "lng": origin["lng"]}}]

    if anchor:
        stay = spot_stay(anchor["category"])
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
        history.append("관광지")
        cur = (anchor["lat"], anchor["lng"])
        t += timedelta(minutes=stay)

    while t.date() == datetime.strptime(start, "%H:%M").date() and _minutes(t) < end_min:
        last = history[-1] if history else None
        ranked = []
        for p in places:
            category = p["category"]
            if category not in STAY_MINUTES or category == last or p["id"] in used or is_disliked(p):
                continue
            dist = haversine_km(*cur, p["lat"], p["lng"])
            if dist > MAX_HOP_KM[transport]:
                continue
            stay = STAY_MINUTES[category]
            arrive = _minutes(t) + _travel_min(dist, transport)
            if arrive + stay > end_min:
                continue
            meal = _meal_window(arrive)
            if category == "맛집" and (meal is None or meal in meals_done):
                continue
            rank = ((p.get("score") or 0) - dist * DIST_WEIGHT
                    + (MOOD_BONUS if mood and mood in (p.get("moods") or []) else 0)
                    + (MEAL_BONUS if category == "맛집" else 0)
                    + (AFTER_MEAL_CAFE_BONUS if category == "카페" and last == "맛집" else 0)
                    - REPEAT_PENALTY * history.count(category))
            if weekday:
                opened = is_open(p.get("hours"), weekday, arrive, stay)
                if opened is False:
                    continue                                    # 휴무 / 영업 전후 / 브레이크타임 / 라스트오더 지남
                if opened is None:
                    rank -= UNKNOWN_HOURS_PENALTY
            ranked.append((rank, dist, p))
        if not ranked:
            t += timedelta(minutes=WAIT_MINUTES)                # 지금 갈 곳 없음 → 기다렸다 다시 (오픈 전, 식사 전 등)
            continue
        ranked.sort(key=lambda r: r[0], reverse=True)
        _, dist, best = ranked[0]
        category = best["category"]
        travel = _travel_min(dist, transport)
        t += timedelta(minutes=travel)
        if category == "맛집":
            meals_done.add(_meal_window(_minutes(t)))
        steps.append({"time": t.strftime("%H:%M"), "category": category, "travel_min": travel,
                      "place": best, "alternatives": [r[2] for r in ranked[1:] if r[2]["category"] == category][:ALTERNATIVES],
                      "hours_today": describe(best.get("hours"), weekday), "warning": None})
        used.add(best["id"])
        history.append(category)
        cur = (best["lat"], best["lng"])
        t += timedelta(minutes=STAY_MINUTES[category])
    return steps


# 출발지 → 도착지 가는 길 (교통수단은 자동차로 가정. 나중에 교통편 예매 기능으로 대체 가능)
ROUTE_CORRIDOR_KM = 5          # 실제 도로 경로에서 이 거리 안의 장소만 '지나가는 길'로 봄 (왕복 우회 최대 약 10km)
ROUTE_MAX_DETOUR_KM = 2 * ROUTE_CORRIDOR_KM   # 후보 장소 DB 조회 범위 여유분 (main.py)
GOOD_STOP_SCORE = 1.5          # 식사 외에 일부러 들를 만한 곳의 최소 점수 (언급 3~4회 이상)
MIN_DRIVE_BEFORE_STOP = 30     # 식사 외 들르기 전 최소 운전 시간(분). 출발하자마자/연달아 서지 않게
ARRIVAL_ZONE_KM = 10          # 도착지 이 거리 안의 장소는 "가는 길"이 아니라 도착 후 코스에서 고름
LOCAL_SPEED_KMH = 35           # 경로에서 벗어나 장소까지 가는 일반도로 속도


def _drive_min(km):
    # 실제 경로를 못 받았을 때 직선거리 ÷ 평균속도(장거리는 고속도로라 빠르게)로 추정
    return round(km / (60 if km > 30 else 35) * 60) + 5


def straight_route(a, b):
    """경로 API 대신 쓰는 직선 경로 (drive_route와 같은 모양). 약 2km 간격 지점, 시각은 _drive_min 비례."""
    total = _drive_min(haversine_km(*a, *b))
    n = max(1, int(haversine_km(*a, *b) / 2))
    return {"minutes": total,
            "points": [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, total * i / n) for i in range(n + 1)]}


def build_route(origin, dest, places, start="09:00", mood=None, weekday=None, meals_done=None, history=None, used=None,
                route_fn=None):
    """origin → dest 실제 도로 경로를 따라가며 지나가는 곳 중 들를 곳을 넣음. 들를 곳이 더 없으면 도착.

    route_fn(a, b): 자동차 경로 {"minutes", "points": [(lat, lng, 출발 후 분)]} 또는 None (routing.drive_route).
                    None이거나 실패하면 직선 경로로 추정
    후보: 경로에서 ROUTE_CORRIDOR_KM 안 + 도착지 ARRIVAL_ZONE_KM 밖. 도착 시각 = 경로상 가장 가까운 지점 시각 + 빠져나가는 시간
    맛집: 도착 시각이 점심/저녁 시간대일 때 (시간대마다 1번)
    카페/관광지/소품샵: 점수 GOOD_STOP_SCORE 이상이고, 30분 이상 달렸거나 방금 밥 먹었을 때
    공통: 도착~머무는 동안 영업 중, 직전과 다른 종류. 들른 뒤에는 그 장소에서 도착지까지 경로를 다시 구함
    반환: build_course와 같은 steps, 마지막은 category '도착'
    """
    route_fn = route_fn or (lambda a, b: None)
    t = datetime.strptime(start, "%H:%M")
    day = t.date()
    cur = (origin["lat"], origin["lng"])
    goal = (dest["lat"], dest["lng"])
    # meals_done/history: 앞 구간(가는 길)에서 이어받는 식사 시간대·방문 종류. 넘기면 그 객체를 갱신
    used = set() if used is None else used
    meals_done = set() if meals_done is None else meals_done
    history = [] if history is None else history

    def point(name, category, p):
        return {"id": 0, "name": name, "category": category, "address": p.get("address", ""), "lat": p["lat"], "lng": p["lng"]}

    steps = [{"time": start, "category": "출발", "travel_min": 0, "alternatives": [], "hours_today": None, "warning": None,
              "place": point(origin["name"], "출발", origin)}]
    while True:
        route = route_fn(cur, goal) or straight_route(cur, goal)
        last = history[-1] if history else None
        ranked = []
        for p in places:
            category = p["category"]
            if category not in STAY_MINUTES or category == last or p["id"] in used or is_disliked(p):
                continue
            if haversine_km(p["lat"], p["lng"], *goal) < ARRIVAL_ZONE_KM:
                continue
            off, at = min((haversine_km(p["lat"], p["lng"], lat, lng), m) for lat, lng, m in route["points"])
            if off > ROUTE_CORRIDOR_KM:
                continue
            detour = 2 * off                                     # 경로에서 빠졌다가 돌아오는 거리
            drive = round(at + off / LOCAL_SPEED_KMH * 60)
            arrive = _minutes(t) + drive
            score = p.get("score") or 0
            if category == "맛집":
                meal = _meal_window(arrive)
                if meal is None or meal in meals_done:
                    continue
                rank = score + MEAL_BONUS
            else:
                if score < GOOD_STOP_SCORE or (last != "맛집" and drive < MIN_DRIVE_BEFORE_STOP):
                    continue
                rank = (score + (MOOD_BONUS if mood and mood in (p.get("moods") or []) else 0)
                        + (AFTER_MEAL_CAFE_BONUS if category == "카페" and last == "맛집" else 0)
                        - REPEAT_PENALTY * history.count(category))
            rank -= detour * DIST_WEIGHT
            if weekday:
                opened = is_open(p.get("hours"), weekday, arrive, STAY_MINUTES[category])
                if opened is False:
                    continue
                if opened is None:
                    rank -= UNKNOWN_HOURS_PENALTY
            ranked.append((rank, drive, p))
        if not ranked:
            break
        ranked.sort(key=lambda r: r[0], reverse=True)
        _, drive, best = ranked[0]
        category = best["category"]
        t += timedelta(minutes=drive)
        if t.date() != day:
            break
        if category == "맛집":
            meals_done.add(_meal_window(_minutes(t)))
        steps.append({"time": t.strftime("%H:%M"), "category": category, "travel_min": drive,
                      "place": best, "alternatives": [r[2] for r in ranked[1:] if r[2]["category"] == category][:ALTERNATIVES],
                      "hours_today": describe(best.get("hours"), weekday), "warning": None})
        used.add(best["id"])
        history.append(category)
        cur = (best["lat"], best["lng"])
        t += timedelta(minutes=STAY_MINUTES[category])
    drive = route["minutes"]
    t += timedelta(minutes=drive)
    steps.append({"time": t.strftime("%H:%M"), "category": "도착", "travel_min": drive, "alternatives": [],
                  "hours_today": None, "warning": None, "place": point(dest["name"], "도착", dest)})
    return steps


def build_trip(home, origin, route_places, places, start="09:00", transport=None, mood=None, weekday=None, anchor=None,
               end=DEFAULT_END, route_fn=None):
    """집(home) → 여행지 가는 길(build_route) + 도착 시각부터 여행지 코스(build_course)를 한 코스로 이어 붙임.

    가는 길에 먹은 식사·마지막 방문 종류를 여행지 코스가 이어받음 (점심 두 번, 카페 연속 방지)
    여행지 = anchor(테마파크 등)가 있으면 그곳, 없으면 origin(지역/숙소)
    """
    meals, hist, used = set(), [], set()
    route = build_route(home, anchor or origin, route_places, start, mood, weekday, meals, hist, used, route_fn)
    arrive = route[-1]
    if not (start <= arrive["time"] < end):                        # 자정을 넘기거나 종료 시각 이후 도착
        return route
    course = build_course(anchor or origin, places, arrive["time"], transport, mood, weekday, anchor, end, meals, hist, used)
    if course[0]["category"] == "출발":
        return route + course[1:]                                   # 도착 단계가 곧 여행지 코스의 출발
    course[0]["travel_min"] = arrive["travel_min"]                  # 테마파크가 도착지 → 도착 단계 대신 테마파크 방문
    return route[:-1] + course


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
    places += [
        {**base, "id": 6, "name": "공원", "category": "관광지", "lat": 37.5666, "lng": 126.9781, "score": 2},
        {**base, "id": 7, "name": "소품가게", "category": "소품샵", "lat": 37.5667, "lng": 126.9779, "score": 0.5},
        {**base, "id": 8, "name": "두번째식당", "category": "맛집", "lat": 37.5668, "lng": 126.9781, "score": 0.8},
    ]
    origin = {"name": "시청", "lat": 37.5665, "lng": 126.9780}
    steps = build_course(origin, places, "09:00", "대중교통")
    names = [s["place"]["name"] for s in steps]
    # 여러 종류가 섞이고, 같은 종류 연속 없음, 맛집은 점심/저녁에 1번씩, 별로식당·종료 안에 못 끝나는 먼카페 제외
    assert names == ["시청", "공원", "가까운카페", "좋은식당", "소품가게", "조용한카페", "두번째식당"], names
    assert [s["time"] for s in steps] == ["09:00", "09:05", "10:40", "11:45", "13:00", "13:45", "17:50"], steps
    cats = [s["category"] for s in steps]
    assert all(a != b for a, b in zip(cats, cats[1:]))
    assert all(_meal_window(_minutes(datetime.strptime(s["time"], "%H:%M"))) is not None for s in steps if s["category"] == "맛집")
    assert steps[2]["alternatives"] and all(a["category"] == "카페" for a in steps[2]["alternatives"])

    # 종료 시각: 10시까지면 40분짜리 소품샵만 들어감
    assert [s["place"]["name"] for s in build_course(origin, places, "09:00", "대중교통", end="10:00")] == ["시청", "소품가게"]

    # 분위기: 카페만 있을 때 '조용한' 태그 카페 우선
    cafes = [p for p in places if p["category"] == "카페"]
    assert build_course(origin, cafes, "09:00", "대중교통", "조용한")[1]["place"]["name"] == "조용한카페"

    # 영업시간: 10시 오픈 카페뿐이면 기다렸다가 10시대에 방문 / 월요일 휴무면 제외
    open10 = [{**base, "id": 20, "name": "오픈카페", "category": "카페", "lat": 37.5670, "lng": 126.9780, "score": 1,
               "hours": {"월": {"open": "10:00", "close": "22:00", "breaks": [], "last_order": None}, "화": None}}]
    s = build_course(origin, open10, "09:00", "대중교통", weekday="월")
    assert s[1]["place"]["name"] == "오픈카페" and s[1]["time"] == "10:05" and s[1]["hours_today"] == "10:00~22:00", s
    assert len(build_course(origin, open10, "09:00", "대중교통", weekday="화")) == 1

    # 경로 모드: A(경도 127.0) → B(128.0) 약 88km. 길 위의 괜찮은 카페 → 점심때 길 위 식당 → 도착
    A = {"name": "A", "lat": 37.5, "lng": 127.0}
    B = {"name": "B", "lat": 37.5, "lng": 128.0}
    road = [
        {**base, "id": 30, "name": "출발옆카페", "category": "카페", "lat": 37.5, "lng": 127.05, "score": 3},   # 운전 30분 미만
        {**base, "id": 31, "name": "길위카페", "category": "카페", "lat": 37.5, "lng": 127.35, "score": 2},
        {**base, "id": 32, "name": "별점낮은카페", "category": "카페", "lat": 37.5, "lng": 127.4, "score": 0.5},
        {**base, "id": 33, "name": "길위식당", "category": "맛집", "lat": 37.5, "lng": 127.5, "score": 1},
        {**base, "id": 34, "name": "먼식당", "category": "맛집", "lat": 37.8, "lng": 127.5, "score": 5},     # 33km 벗어남
    ]
    s = build_route(A, B, road, "10:00")
    assert [x["place"]["name"] for x in s] == ["A", "길위카페", "길위식당", "B"], s
    assert [x["category"] for x in s] == ["출발", "카페", "맛집", "도착"]
    assert _meal_window(_minutes(datetime.strptime(s[2]["time"], "%H:%M"))) is not None, s[2]["time"]
    assert [x["place"]["name"] for x in build_route(A, B, road, "14:00")] == ["A", "길위카페", "B"]   # 식사 시간 아님
    assert [x["place"]["name"] for x in build_route(A, B, [], "10:00")] == ["A", "B"]

    # 실제 도로가 북쪽(위도 37.8)으로 돌아가면: 직선 기준으론 제외됐던 그 길가 '먼식당'을 들르고, 직선상 '길위식당'은 제외
    def bent(a, b):     # a → (37.8, 중간 경도) → b, 120분짜리 가짜 경로
        mid = (37.8, (a[1] + b[1]) / 2)
        pts = straight_route(a, mid)["points"][:-1] + straight_route(mid, b)["points"]
        return {"minutes": 120, "points": [(lat, lng, 120 * i / (len(pts) - 1)) for i, (lat, lng, _) in enumerate(pts)]}
    s = build_route(A, B, road, "10:40", route_fn=bent)
    names = [x["place"]["name"] for x in s]
    assert "먼식당" in names and "길위식당" not in names and s[-1]["category"] == "도착", names

    # 집(A) → 여행지(B): 가는 길에 점심 먹었으면 B에선 저녁 전까지 맛집 없음, 도착 시각부터 B 코스가 이어짐
    near_b = [
        {**base, "id": 40, "name": "B카페", "category": "카페", "lat": 37.5005, "lng": 128.0, "score": 1},
        {**base, "id": 41, "name": "B식당", "category": "맛집", "lat": 37.501, "lng": 128.0, "score": 1},
        {**base, "id": 42, "name": "B공원", "category": "관광지", "lat": 37.5, "lng": 128.001, "score": 1},
    ]
    s = build_trip(A, B, road, near_b, "10:00")
    names = [x["place"]["name"] for x in s]
    assert names[:4] == ["A", "길위카페", "길위식당", "B"] and s[3]["category"] == "도착", names   # B 도착 후 B 코스
    after = s[4:]
    assert after[0]["place"]["name"] == "B공원" and after[0]["time"] >= s[3]["time"], s   # 카페 감점(이미 감) → 공원
    assert all(x["category"] != "맛집" or x["time"] >= "17:30" for x in after), s           # 점심은 가는 길에 먹음
    assert [x["place"]["name"] for x in build_route(A, B, near_b, "11:00")] == ["A", "B"]   # 도착지 근처는 '가는 길' 아님
    s = build_trip(A, B, near_b, near_b, "11:00")                     # 같은 곳 두 번 방문 없음
    ids = [x["place"]["id"] for x in s if x["place"]["id"]]
    assert len(ids) == len(set(ids)) and s[1]["category"] == "도착", s
    s = build_trip(A, B, [], near_b, "09:00")                         # 가는 길에 들를 곳 없음 → 도착 후 B 코스
    assert [x["place"]["name"] for x in s] == ["A", "B", "B카페", "B식당", "B공원"] and s[1]["time"] == "10:33", s
    # 테마파크가 여행지: 도착 단계 대신 테마파크 방문(이동 시간 유지)
    bpark = {**base, "id": 43, "name": "B파크", "category": "테마파크", "lat": 37.5, "lng": 128.0, "score": 2}
    s = build_trip(A, {**bpark, "name": "B파크"}, [], near_b, "09:00", anchor=bpark)
    assert [x["category"] for x in s][:2] == ["출발", "테마파크"] and s[1]["travel_min"] > 60, s

    # 테마파크 고정: 첫 방문지가 테마파크, 5시간 뒤 근처에서 이어짐 (식사 시간 아니면 맛집 아님)
    park = {**base, "id": 9, "name": "테마파크", "category": "테마파크", "lat": 37.5668, "lng": 126.9780, "score": 2,
            "hours": {"월": {"open": "10:00", "close": "21:00", "breaks": [], "last_order": None}}}
    s = build_course(origin, places, "09:00", "대중교통", weekday="월", anchor=park)
    assert [x["category"] for x in s][:2] == ["출발", "테마파크"] and s[1]["warning"] == "도착 시각에 영업하지 않을 수 있어요"
    assert s[2]["time"] == "14:10" and s[2]["category"] != "맛집", s[2]     # 09:05 도착 + 300분 + 이동 5분
    s = build_course({**park, "name": "테마파크"}, places, "10:00", "대중교통", weekday="월", anchor=park)
    assert s[0]["category"] == "테마파크" and s[0]["warning"] is None
    assert spot_stay("테마파크") == 300 and spot_stay("수목원,식물원") == 120
    print("ok")
