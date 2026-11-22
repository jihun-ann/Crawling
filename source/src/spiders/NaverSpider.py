import re
import urllib.parse
import json
import logging
import datetime

import requests
import scrapy
from scrapy import Spider
from importlib import resources
from collections import deque
from bs4 import BeautifulSoup

from source.src.api.token import total_token
from source.src.items import ContentItem
from source.src.content_filter import content_id, parse_post_date
from source.src.sqlalchemy.crud import raw_post_crud

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class NaverSpider(Spider):
    """네이버 블로그/카페 후기 크롤러.

    흐름: 검색어(지역 + 키워드) → 네이버 검색 결과 → 글 페이지(iframe) → 본문 추출 → ContentItem
    실행: scrapy crawl naver_crawling -a prov=서울특별시   (prov → self.prov)
    """
    name = "naver_crawling"
    platform = "naver"      # raw_post.platform 값

    def start_requests(self):
        """크롤링 시작점. 지역 목록 × 키워드 목록으로 검색 요청 생성 (현재는 단건 테스트용 고정 검색어).
        -a query="용인 테마파크" 를 주면 그 검색어 하나만 크롤링."""
        if getattr(self, "query", None):
            yield from self.searching_naver(self.query, 1, self.query)
            return
        province = self.prov
        location_q = self.location_list(province)
        # location_q = self.location_name(province)

        keyword_q = deque()
        keyword_q.append("맛집") #단건 테스트
        #keyword_q = self.keyword_list() #리스트 조회

        # keyword 자리에 검색어 전체를 넘김 → 로더가 주소 없는 글의 지역 힌트로 사용
        # for location in location_q:
        #     for keyword in keyword_q:
        #         search_query = " ".join([location,keyword])
        #         yield from self.searching_naver(search_query, 1, search_query)
        yield from self.searching_naver("서울특별시 강서구 방화동 맛집", 1, "서울특별시 강서구 방화동 맛집")

    def searching_naver(self, query, start, keyword):
        """네이버 블로그 검색 API 요청 (하루 25,000회 무료, 지역검색과 같은 NAVER_CLIENT_ID/KEY). start는 1부터의 순번."""
        # ponytail: 블로그만, 1페이지(100건)만. 카페는 본문이 로그인/SPA라 별도 처리 필요, 더 필요하면 start=101,201...
        params = urllib.parse.urlencode({"query": query, "display": 100, "start": start, "sort": "sim"})
        headers = {"X-Naver-Client-Id": self.settings.get("NAVER_CLIENT_ID"),
                   "X-Naver-Client-Secret": self.settings.get("NAVER_CLIENT_KEY")}
        yield scrapy.Request(f"https://openapi.naver.com/v1/search/blog.json?{params}", self.parse_search,
                             headers=headers, meta={"keyword": keyword})


    def parse_search(self, response):
        """검색 결과(JSON) → 글 링크. 제목에 차단 키워드가 있거나 이미 저장된 글(raw_post)은 건너뜀."""
        # 제목 기준 1차 필터: 여행/맛집 후기와 무관한 글, 광고 표기 글 제외 (본문 기준 2차 필터는 pipelines)
        block_keywords = ("경매", "법원경매", "부동산", "광고", "협찬", "임장", "의원", "병원", "학비", "거주", "원룸", "투룸", "직거래", "시술", "공고", "매매")
        posts = {}
        for it in json.loads(response.text).get("items", []):
            title = BeautifulSoup(it["title"], "html.parser").get_text()
            if not any(k in title for k in block_keywords):
                posts[content_id(it["link"])] = it["link"]

        known = raw_post_crud.known_ids(posts)
        logger.info(f"검색 결과 {len(posts)}건 중 새 글 {len(posts) - len(known)}건")
        for cid, link in posts.items():
            if cid not in known:
                yield scrapy.Request(link, self.parse_main_html, meta={"file_name": cid, "keyword": response.meta["keyword"]},
                                     dont_filter=True)


    def parse_main_html(self, response):
        """글 페이지는 본문이 iframe 안에 있음 → iframe 실제 주소를 찾아 다시 요청 (블로그: mainFrame, 카페: cafe_main)."""
        filename = response.meta["file_name"]
        init_url = response.url
        soup = BeautifulSoup(response.text,"html.parser")
        print(response.url)
        iframe = None
        url = None

        if "blog.naver.com" in response.url :
            iframe = soup.select_one("iframe#mainFrame")
            url = f"https://blog.naver.com{iframe.get("src")}"
        elif "cafe.naver.com" in response.url :
            iframe = soup.select_one("iframe#cafe_main")

            main_area = soup.select_one("div#main-area")
            scripts = main_area.find_all("script")
            script_text = "".join(s.string for s in scripts if s.string)

            m = re.search(
                r'cafe_main"\)\.src\s*=\s*"([^"]+)"',
                script_text
            )

            url = f"https:{m.group(1)}"
        else :
            return

        yield scrapy.Request(url, self.parse_main_container_export, meta={"init_url":init_url, "filename":filename,"keyword":response.meta["keyword"]})


    def parse_main_container_export(self, response):
        """iframe 본문 페이지에서 제목/본문 텍스트 추출 → ContentItem 생성 (스마트에디터, 카페, 구버전 에디터 순으로 시도)."""
        soup = BeautifulSoup(response.text,"html.parser")
        # 본문: 스마트에디터(블로그) → 카페 → 구버전 에디터(블로그) 순
        content = (soup.select_one("div.se-main-container") or soup.select_one("div.ContentRenderer")
                   or soup.select_one("#postViewArea"))
        if content is None:
            logger.warning(f"본문 영역 없음, 건너뜀: {response.url}")
            return

        title_tag = (soup.select_one("div.se-title-text") or soup.select_one("h3.title_text")
                     or soup.select_one("div.htitle") or soup.title)
        title = title_tag.get_text().replace("\n", " ") if title_tag else ""
        date_tag = soup.select_one("span.se_publishDate") or soup.select_one("p.date") or soup.select_one("span.date")

        yield self.parsing_content_items(title,
                                         response.meta["filename"],
                                         response.meta["init_url"],
                                         response.url,
                                         content.get_text().replace("  "," "),
                                         response.meta["keyword"],
                                         parse_post_date(date_tag.get_text() if date_tag else ""))


    def parsing_content_items(self, title, filename, init_url, content_url, content, keyword, posted_at=None):
        """추출한 값으로 ContentItem 생성. 이후 pipelines.SrcPipeline이 필터링 후 저장."""
        item = ContentItem()
        item['posted_at'] = posted_at
        item['filename'] = filename
        item['init_url'] = init_url
        item['content_url'] = content_url
        item['platform'] = self.platform
        item['title'] = title
        item['context'] = content
        item['crawled_at'] = datetime.date.today().isoformat()
        item['keyword'] = keyword
        return item


    def location_list(self, prov):
        """SGIS API로 시/도(prov) 하위 전체 주소("서울특별시 강서구 방화동" 등) 목록 조회. 검색어의 지역 부분으로 사용."""
        q = deque()
        access_token = total_token.get_sgis_access_token()

        if access_token:
            stage_url = "https://sgisapi.mods.go.kr/OpenAPI3/addr/stage.json"

            resource_path = resources.files("source.src.properties")
            with resource_path.joinpath("location_kr.json").open(encoding="utf-8") as f :
                locations = json.load(f)

            cd = None
            for loc in locations:
                if loc["addr_name"] == prov:
                    cd = loc["cd"]

            if not cd :
                logger.error(f"Error prov [{prov}] is Not Found")
                return

            stage_param = {"accessToken":access_token,"cd":cd}
            stage_gu_response = requests.get(stage_url,params=stage_param)

            if stage_gu_response.status_code == 200:
                stage_list = stage_gu_response.json()["result"]
                for stage_gu in stage_list:
                    stage_param["cd"] = stage_gu["cd"]

                    full_stage_response = requests.get(stage_url,params=stage_param)
                    if full_stage_response.status_code == 200:
                        full_stage_list = full_stage_response.json()["result"]
                        for stage in full_stage_list:
                            q.append(stage["full_addr"])

                    else:
                        logger.error(f"Error Full Stage Retrived: {full_stage_response.text}")
            else :
                logger.error(f"Error Stage Retrived: {stage_gu_response.text}")
            return q
        else :
            logger.error(f"Not Have Token: {access_token}")
            return None

    def location_name(self, prov_value):
        """location_list와 같은 결과를 API 없이 로컬 파일(properties/location_kr.json)로 생성."""
        q = deque()
        resource_path = resources.files("source.src.properties")
        # 지역명 JSON 추출
        with resource_path.joinpath("location_kr.json").open(encoding="utf-8") as f :
            locations = json.load(f)

        for province, cities in locations.items():
            if province == prov_value :
                if province in ("서울특별시", "인천시", "대전광역시", "세종특별시", "부산광역시"):
                    # 구 조회
                    for country, towns in cities.items() :
                        for town in towns :
                            location_name = " ".join([province, country, town])
                            q.append(location_name)
                else:
                    # 시 조회
                    for city, countries in cities.items() :
                        # 구 조회
                        for country, towns in countries.items():
                            # 동 조회
                            for town in towns:
                                location_name = " ".join([province, city, country, town])
                                q.append(location_name)

        return q


    def keyword_list(self):
        """검색 키워드 목록(properties/keyword.json, 방문목적별 키워드) 로드."""
        q = deque()
        resource_path = resources.files("source.src.properties")

        # 키워드 JSON 추출
        with resource_path.joinpath("keyword.json").open(encoding="utf-8") as f :
            keywords = json.load(f)

        for purpose, contents in keywords.items():
            for content in contents:
                q.append(content)

        return q