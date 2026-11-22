import datetime
import json
import logging
import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup
from scrapy.utils.project import get_project_settings
from sqlalchemy import text as sql_text

from source.src.content_filter import is_negative, mood_tags, normalize_category
from source.src.hours import open_days, parse_naver_hours
from source.src.sqlalchemy import database
from source.src.sqlalchemy.crud import place_crud, raw_post_crud

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# 본문에서 도로명 주소 찾는 정규식: (시/도) 시/군/구 + 도로명 + 건물번호
SI_DO = r'(?:서울(?:특별시|시)|부산(?:광역시|시)|대구(?:광역시|시)|인천(?:광역시|시)|광주(?:광역시|시)|대전(?:광역시|시)|울산(?:광역시|시)|세종(?:특별자치시|시)|경기(?:도)|강원(?:특별자치도|도)|충북(?:도)|충청북도|충남(?:도)|충청남도|전북(?:도)|전라북도|전남(?:도)|전라남도|경북(?:도)|경상북도|경남(?:도)|경상남도|제주(?:특별자치도|도))'
SI_GUN_GU = r'[가-힣]+(?:시|군|구)'
ROAD = r'[가-힣\d]+(?:로|길)(?:[ \t]*\d+번?길)?'
BUILDING_INFO = r'\d{1,4}(?:-\d{1,4})?'
ADDRESS_PATTERN = re.compile(rf'(?:(?:{SI_DO}[ \t]+)?{SI_GUN_GU}[ \t]+){ROAD}[ \t]+{BUILDING_INFO}')

IGNORE_PLACE_KEYWORDS = ("주차장", "병원", "유치원", "약국", "은행", "아파트", "호선", "주민센터", "학교", "빌딩")
MOBILE_UA = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"}
# 동네 이름과 같은 상호(예: 고깃집 '공항동')는 이름만으로 매칭하면 동네 언급 글까지 붙음 → 상호명 매칭에서 제외
AREA_LIKE_NAME = re.compile(r'^[가-힣]{1,4}(?:동|구|시|군|읍|면|리)$')


def _nospace(s):
    return s.replace(" ", "")


class BlogContentLoader:
    """크롤링 원문(raw_post) 중 새 글만 → 본문 속 주소/상호명으로 장소 확인 → place / place_review 저장 → 점수 갱신.

    장소 찾기 2가지:
      1) 주소: 본문 속 도로명 주소 → (DB에 이미 있는 장소면 재사용, 없으면 네이버 검색/지역검색/영업시간 조회)
      2) 상호명: 주소가 없는 글(유튜브 등) → 검색어 지역 안의 DB 장소 중 이름이 본문에 나오는 곳
    실행: python -m source.src.sqlalchemy.services.blog_content_loader
    """
    def __init__(self):
        settings = get_project_settings()
        self.headers = {"X-Naver-Client-Id": settings.get("NAVER_CLIENT_ID"),
                        "X-Naver-Client-Secret": settings.get("NAVER_CLIENT_KEY")}
        self.db = database.SessionLocal()

    def run(self):
        """처리 대기 글 전체 처리 후 점수 갱신. 글 하나가 실패하면 대기로 남겨 다음 실행 때 다시 시도."""
        # ponytail: 전체 장소를 메모리에 올려 이름 매칭. 장소가 수만 개 넘으면 지역별로 나눠 조회
        self.places = [(r.place_id, _nospace(r.name or ""), _nospace(r.location_detail or ""))
                       for r in self.db.execute(sql_text("SELECT place_id, name, location_detail FROM place"))]
        saved = 0
        for post in raw_post_crud.pending():
            try:
                saved += self.load_post(post)
                raw_post_crud.mark_processed(post["content_id"])
            except Exception as e:
                self.db.rollback()
                logger.exception(f"BlogContentLoader|load_post Error|{post['content_id']}|{e}")
        updated = place_crud.update_scores(self.db)
        logger.info(f"BlogContentLoader|done|장소 연결 {saved}건|점수 갱신 {updated}곳")

    def load_post(self, post):
        """글 1개 처리. 찾은 장소마다 후기 연결, 연결한 장소 수 반환."""
        text = post["body"] or ""
        review = {
            "content_id": post["content_id"],
            "platform": post["platform"],
            "url": post["url"],
            "title": (post.get("title") or "").strip(),
            "posted_at": post.get("posted_at"),
            "is_negative": is_negative(text),
            "moods": json.dumps(mood_tags(text), ensure_ascii=False),
        }

        place_ids = set()
        for address in self.unique_addresses(text):
            place_id = self.known_place_at(address, text) or self.lookup_place(address, text)
            if place_id:
                place_ids.add(place_id)
        place_ids |= self.known_places_named(text, post.get("keyword"))

        for place_id in place_ids:
            place_crud.add_review(self.db, {**review, "place_id": place_id})
        if place_ids:
            logger.info(f"BlogContentLoader|linked|{len(place_ids)}곳|{post['content_id']}")
        return len(place_ids)

    def lookup_place(self, address, text):
        """처음 보는 주소: 네이버로 상호명 확인 → 지역검색 → 영업시간 → DB 저장. place_id 또는 None."""
        place_name = self.pick_place_name(address, text)
        if not place_name:
            return None
        place = self.retrive_place(place_name, address)
        if not place:
            return None
        place_id = place_crud.save_place(self.db, place)
        self.places.append((place_id, _nospace(place["name"]), _nospace(place["location_detail"])))
        logger.info(f"BlogContentLoader|new place|{place['name']}|{place['category']}")
        return place_id

    def known_place_at(self, address, text):
        """DB에 이미 있는 장소 중 주소가 같고 이름이 본문에 나오는 곳 → 네이버 호출 없이 재사용."""
        addr = _nospace(address)
        body = _nospace(text)
        hits = [(body.count(name), pid) for pid, name, road in self.places if addr in road and name and name in body]
        return max(hits)[1] if hits else None

    def known_places_named(self, text, keyword):
        """검색어 속 지역(예: '강릉 카페' → 강릉)에 있는 DB 장소 중 이름이 본문에 나오는 곳들."""
        # ponytail: 이미 DB에 있는 장소만 찾음(주소 있는 블로그 글로 먼저 발견돼야 함). 2글자 이름은 오탐 가능
        regions = [_nospace(t) for t in (keyword or "").split() if len(t) >= 2]
        body = _nospace(text)
        return {pid for pid, name, road in self.places
                if len(name) >= 2 and not AREA_LIKE_NAME.match(name) and name in body and any(r in road for r in regions)}

    def unique_addresses(self, text):
        """본문 속 도로명 주소 목록. 같은 주소의 다른 표기(시/도 유무 등)는 하나로."""
        kept = []
        for add in ADDRESS_PATTERN.findall(text):
            if not any(_nospace(add) in _nospace(k) or _nospace(k) in _nospace(add) for k in kept):
                kept.append(add)
        return kept

    def pick_place_name(self, address, text):
        """주소에 있는 장소 후보 중 본문에 가장 많이 나온 이름. 없거나 제외 업종이면 None."""
        candidates = self.find_place_name(address)
        if not candidates:
            logger.info(f"BlogContentLoader|주소에 장소 후보 없음|{address}")
            return None
        counts = {c.get_text(): text.count(c.get_text()) for c in candidates if c.get_text()}
        counts = {k: v for k, v in counts.items() if v}
        if not counts:
            return None
        name = max(counts, key=counts.get)
        return None if any(k in name for k in IGNORE_PLACE_KEYWORDS) else name

    def retrive_place(self, place_name, address):
        """네이버 지역검색 API로 (상호명 + 주소) 검색 → 도로명 주소가 일치하는 첫 결과를 place 컬럼 dict로. 없으면 None."""
        res = requests.get("https://openapi.naver.com/v1/search/local.json",
                           params={"query": f"{place_name} {address}", "display": 5},
                           headers=self.headers, timeout=10)
        if res.status_code != 200:
            logger.error(f"BlogContentLoader|지역검색 실패|{res.status_code}|{res.text[:200]}")
            return None

        for item in res.json().get("items", []):
            road = item.get("roadAddress") or ""
            if _nospace(address) not in _nospace(road):
                continue
            parts = road.split()
            name = re.sub(r"<[^>]+>", "", item["title"])
            hours = self.fetch_hours(name, road)
            return {
                "business_hours": json.dumps(hours, ensure_ascii=False) if hours else None,
                "business_days": open_days(hours),
                "break_time": json.dumps(sorted({tuple(b) for d in hours.values() if d for b in d["breaks"]}))
                              if hours else None,
                "name": name,
                "type": item.get("category"),
                "category": normalize_category(item.get("category")),
                "phone_number": item.get("telephone") or None,
                "location_detail": road,
                "location_province": parts[0] if parts else None,
                "location_city": parts[1] if len(parts) > 1 else None,
                "latitude": int(item["mapy"]) / 10_000_000,          # WGS84 x 1e7 정수로 내려옴
                "longitude": int(item["mapx"]) / 10_000_000,
                "crawled_at": datetime.date.today().isoformat(),
            }
        return None

    def fetch_hours(self, name, road_address):
        """네이버 모바일 지도 검색으로 플레이스 ID를 찾고, 플레이스 페이지에서 요일별 영업시간 수집. 실패하면 None."""
        # ponytail: 네이버 화면 내부 데이터(__RQ_STREAMING_STATE__, __APOLLO_STATE__) 구조에 의존. 개편되면 None만 나옴
        try:
            # 상세주소(층/호수)까지 넣으면 검색 결과가 비어서 "상호명 + 시/구"로 검색, 도로명+건물번호까지만 비교
            parts = road_address.split()
            road_base = _nospace(" ".join(parts[:4]))
            q = urllib.parse.quote(f"{name} {' '.join(parts[:2])}")
            res = requests.get(f"https://m.map.naver.com/search?query={q}&type=all&displayCount=5",
                               headers=MOBILE_UA, timeout=10)
            place_id = None
            for chunk in re.findall(r'window\.__RQ_STREAMING_STATE__\.push\((.*?)\);', res.content.decode("utf-8")):
                for query in json.loads(chunk).get("queries", []):
                    data = query.get("state", {}).get("data")
                    for it in (data.get("items") or []) if isinstance(data, dict) else []:
                        if _nospace(it.get("name", "")) == _nospace(name) or road_base in _nospace(it.get("roadAddress") or ""):
                            place_id = place_id or it["id"]
            if not place_id:
                return None
            time.sleep(0.3)     # 연속 요청 간격
            page = requests.get(f"https://m.place.naver.com/place/{place_id}/home", headers=MOBILE_UA, timeout=10)
            m = re.search(r'window\.__APOLLO_STATE__\s*=\s*(\{.*?\});', page.content.decode("utf-8"), re.S)
            if not m:
                return None
            root = json.loads(m.group(1)).get("ROOT_QUERY", {})
            detail = next((v for k, v in root.items() if k.startswith("placeDetail(") and isinstance(v, dict)), {})
            return parse_naver_hours(detail.get("newBusinessHours"))
        except Exception as e:
            logger.warning(f"BlogContentLoader|영업시간 수집 실패|{name}|{e}")
            return None

    def find_place_name(self, address):
        """주소로 네이버 통합검색 → 해당 주소에 있는 장소(상호명) 후보 목록 반환. 없으면 None."""
        # ponytail: 네이버 검색 화면 HTML 클래스(._5Dken)에 의존. 화면 개편되면 깨짐 → 후보가 계속 0이면 여기부터 확인
        encoding_address = urllib.parse.quote(address)
        url = f"https://search.naver.com/search.naver?ssc=tab.nx.all&query={encoding_address}"
        search_response = requests.get(url, timeout=10)

        if search_response.status_code == 200 :
            soup = BeautifulSoup(search_response.text,"html.parser")
            loc_main = soup.select_one("#loc-main-section-root")
            if loc_main:
                return loc_main.select("div ._5Dken")
        return None


if __name__=="__main__":
    BlogContentLoader().run()
