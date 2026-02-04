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

from source.src.items import ContentItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class NaverSpider(Spider):
    name = "naver_crawling"
    platform = "naver"

    def start_requests(self):
        province = self.prov
        location_q = self.location_list(province)
        # location_q = self.location_name(province)

        keyword_q = deque()
        keyword_q.append("맛집") #단건 테스트
        #keyword_q = self.keyword_list() #리스트 조회

        for location in location_q:
            for keyword in keyword_q:
                search_query = " ".join([location,keyword])
                yield from self.searching_naver(search_query, 1)

    def searching_naver(self, query, start):
        re_query = urllib.parse.quote(query)
        options = ["blog"]

        for opt in options:
            url = f"https://search.naver.com/search.naver?ssc=tab.{opt}.all&query={re_query}&start={start}"
            #url = "https://search.naver.com/search.naver?query=" + re_query                       #전체 통합 검색
            #url = "https://search.naver.com/search.naver?ssc=tab.blog.all&query=" + re_query      #블로그 검색
            #url = "https://search.naver.com/search.naver?ssc=tab.cafe.all&query=" + re_query      #카페 검색
            yield scrapy.Request(url, self.parse_init_html, meta={"query":re_query,"start":start})


    def parse_init_html(self, response):
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

            block_keywords = ("경매", "법원경매", "부동산", "광고", "협찬", "임장", "의원", "병원", "학비", "거주", "원룸", "투룸")
            if any(keyword in span_text for keyword in block_keywords):
                continue
            else:
                href = a.get("href")
                init_url = href.replace("https://","").replace("http://","").replace("/","_")

                if not self.has_content(init_url):
                    continue

                yield scrapy.Request(href, self.parse_main_html,meta={"init_url":init_url})

        if cont == 0:
            return

        yield from self.searching_naver(urllib.parse.unquote(response.meta["query"]),
                                        response.meta["start"]+30)


    def has_content(self, url):
        result = False
        settings = get_project_settings()
        path = Path(settings.get("BASE_DIR"))/"source"/"src"/"content"/f"{self.platform}"/f"{url}.json"

        if path.exists() :
            result = False
            logger.info(f"Cralwing : {url}")
        else :
            result = True
            logger.info(f"Already Cralwed : {url}")

        return result


    def parse_main_html(self, response):
        filename = response.meta["init_url"]
        init_url = response.url
        soup = BeautifulSoup(response.text,"html.parser")

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

        yield scrapy.Request(url, self.parse_main_container_export, meta={"init_url":init_url, "filename":filename})


    def parse_main_container_export(self, response):
        soup = BeautifulSoup(response.text,"html.parser")
        title = str
        content_text = str
        content = (soup.select_one("div.se-main-container") or soup.select_one("div.ContentRenderer")) #se-main-container는 블로그용, div.ContentRenderer 카페용

        if content is not None:
            title = (soup.select_one("div.se-title-text") or soup.select_one("h3.title_text"))    #se-title-text는 블로그용, title_text 카페용
            content_text = content.get_text().replace("\n"," ").replace("  "," ")

        elif soup.select("#postViewArea") is not None :
            content = soup.select_one("#postViewArea")
            content_text = content.get_text().replace("\n"," ").replace("  "," ")

        parsing_item = self.parsing_content_items(title.get_text().replace("\n"," "),
                                                            response.meta["filename"],
                                                            response.meta["init_url"],
                                                            response.url,
                                                            content_text)
        yield parsing_item


    def parsing_content_items(self, title, filename, init_url, content_url, content):
        item = ContentItem()
        item['filename'] = filename
        item['init_url'] = init_url
        item['content_url'] = content_url
        item['platform'] = self.platform
        item['title'] = title
        item['context'] = content
        item['crawled_at'] = datetime.date.today().isoformat()
        return item


    def location_list(self, prov):
        settings = get_project_settings()
        client_param = {"consumer_key":f"{settings.get("CLIENT_ID")}","consumer_secret":f"{settings.get("CLIENT_KEY")}"}
        token_url = "https://sgisapi.mods.go.kr/OpenAPI3/auth/authentication.json"
        token_response = requests.get(token_url,params=client_param)

        q = deque()

        if token_response.status_code == 200 :
            access_token_json = token_response.json()
            access_token = access_token_json["result"]["accessToken"]

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
                        logger.error(f"Error Full Stage Retrived: {token_response.text}")
                        print()
            else :
                logger.error()
                print(f"Error Stage Retrived: {token_response.text}")
            return q
        else :
            logger.error()
            print(f"Error Code: {token_response.text}")

    def location_name(self, prov_value):
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
        q = deque()
        resource_path = resources.files("source.src.properties")

        # 키워드 JSON 추출
        with resource_path.joinpath("keyword.json").open(encoding="utf-8") as f :
            keywords = json.load(f)

        for purpose, contents in keywords.items():
            for content in contents:
                q.append(content)

        return q