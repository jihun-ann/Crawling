import re
import urllib
import json
import logging
import datetime
from pathlib import Path

import requests
import scrapy
from scrapy import Spider
from importlib import resources
from collections import deque
from bs4 import BeautifulSoup
from scrapy.utils.project import get_project_settings
from urllib.parse import urlparse, parse_qs

from source.src.api.token import total_token
from source.src.items import ContentItem
from source.src.content_filter import content_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class NaverSpider(Spider):
    """네이버 블로그/카페 후기 크롤러.

    흐름: 검색어(지역 + 키워드) → 네이버 검색 결과 → 글 페이지(iframe) → 본문 추출 → ContentItem
    실행: scrapy crawl naver_crawling -a prov=서울특별시   (prov → self.prov)
    """
    name = "naver_crawling"
    platform = "naver"      # 저장 폴더명 (blog_content/naver)

    def start_requests(self):
        """크롤링 시작점. 지역 목록 × 키워드 목록으로 검색 요청 생성 (현재는 단건 테스트용 고정 검색어)."""
        province = self.prov
        location_q = self.location_list(province)
        # location_q = self.location_name(province)

        keyword_q = deque()
        keyword_q.append("맛집") #단건 테스트
        #keyword_q = self.keyword_list() #리스트 조회

        # for location in location_q:
        #     for keyword in keyword_q:
        #         search_query = " ".join([location,keyword])
        #         yield from self.searching_naver(search_query, 1, keyword)
        yield from self.searching_naver("서울특별시 강서구 방화동 맛집", 1, '맛집')

    def searching_naver(self, query, start, keyword):
        """네이버 검색 결과 페이지 요청. start는 페이지 오프셋, keyword는 결과 item에 기록할 검색 키워드."""
        re_query = urllib.parse.quote(query)
        options = ["blog"]

        for opt in options:
            url = f"https://search.naver.com/search.naver?ssc=tab.{opt}.all&query={re_query}&start={start}"
            #url = "https://search.naver.com/search.naver?query=" + re_query                       #전체 통합 검색
            #url = "https://search.naver.com/search.naver?ssc=tab.blog.all&query=" + re_query      #블로그 검색
            #url = "https://search.naver.com/search.naver?ssc=tab.cafe.all&query=" + re_query      #카페 검색
            yield scrapy.Request(url, self.parse_init_html, meta={"query":re_query,"start":start, "keyword":keyword})


    def parse_init_html(self, response):
        """검색 결과에서 글 링크 추출. 제목에 차단 키워드가 있거나 이미 저장된 글(content_id 기준)은 건너뜀."""
        soup = BeautifulSoup(response.text,"html.parser")
        cont = 0

        for a in soup.select("a"):
            init_url = None
            span_text = None

            #블로그 Link
            span = a.select_one("span.sds-comps-text-type-headline1")
            if  span:
                span_text = span.get_text()
                cont += 1


            #카페 Link
            elif "title_link" in a.get("class", []):
                span_text = a.get_text()
                cont += 1

            if not span_text:
                continue

            # 제목 기준 1차 필터: 여행/맛집 후기와 무관한 글, 광고 표기 글 제외 (본문 기준 2차 필터는 pipelines)
            block_keywords = ("경매", "법원경매", "부동산", "광고", "협찬", "임장", "의원", "병원", "학비", "거주", "원룸", "투룸", "직거래", "시술", "공고", "매매")
            if any(keyword in span_text for keyword in block_keywords):
                continue
            else:
                href = a.get("href")
                file_name = content_id(href)

                if self.has_content(file_name):
                    continue
                yield scrapy.Request(href, self.parse_main_html,meta={"file_name":file_name,"keyword":response.meta["keyword"]}, dont_filter=True)

        if cont == 0:
            return

        # yield from self.searching_naver(urllib.parse.unquote(response.meta["query"]),
        #                                 response.meta["start"]+30)


    def has_content(self, url):
        """이미 크롤링해서 JSON으로 저장된 글인지 확인 (url = content_id 파일명)."""
        result = False
        settings = get_project_settings()
        path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"/f"{self.platform}"/f"{url}.json"
        if not path.exists() :
            result = False
            logger.info(f"Cralwing : {url}")
        else :
            result = True
            logger.info(f"Already Cralwed : {url}")

        return result


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
        title = str
        content_text = str
        content = (soup.select_one("div.se-main-container") or soup.select_one("div.ContentRenderer")) #se-main-container는 블로그용, div.ContentRenderer 카페용

        if content is not None:
            title = (soup.select_one("div.se-title-text") or soup.select_one("h3.title_text"))    #se-title-text는 블로그용, title_text 카페용
            content_text = content.get_text().replace("  "," ")

        elif soup.select("#postViewArea") is not None :
            content = soup.select_one("#postViewArea")
            content_text = content.get_text().replace("  "," ")

        parsing_item = self.parsing_content_items(title.get_text().replace("\n"," "),
                                                            response.meta["filename"],
                                                            response.meta["init_url"],
                                                            response.url,
                                                            content_text,
                                                            response.meta["keyword"])
        yield parsing_item


    def parsing_content_items(self, title, filename, init_url, content_url, content, keyword):
        """추출한 값으로 ContentItem 생성. 이후 pipelines.SrcPipeline이 필터링 후 저장."""
        item = ContentItem()
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