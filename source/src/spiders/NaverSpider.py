import urllib
import json

import datetime
from pathlib import Path

import scrapy
from scrapy import Spider
from importlib import resources
from collections import deque
from bs4 import BeautifulSoup
from scrapy.utils.project import get_project_settings

from source.src.items import BlogContentItem


class NaverSpider(Spider):
    name = "naver_crawling"

    def start_requests(self):
        province = self.prov
        location_q = self.location_name(province)

        keyword_q = deque()
        keyword_q.append("맛집") #단건 테스트
        #keyword_q = self.keyword_list() #리스트 조회

        for location in location_q:
            for keyword in keyword_q:
                search_query = " ".join([location,keyword])
                yield from self.searching_naver_blog(search_query)
                #self.searching_naver_api_blog(search_query)

    def searching_naver_blog(self, query):
        re_query = urllib.parse.quote(query)
        #url = "https://search.naver.com/search.naver?query=" + re_query                       #전체 통합 검색
        url = "https://search.naver.com/search.naver?ssc=tab.blog.all&query=" + re_query       #블로그 검색
        #url = "https://search.naver.com/search.naver?ssc=tab.cafe.all&query=" + re_query      #카페 검색

        yield scrapy.Request(url, self.parse_init_blog_html)
        # request = urllib.request.Request(url)
        # response = urllib.request.urlopen(request)
        # rescode = response.getcode()
        # if(rescode==200):
        #     response_body = response.read()
        #     self.parsing_init_blog_html(response_body.decode('utf-8'))
        # else:
        #     print("Error Code:" + rescode)

    def parse_init_blog_html(self, response):
        soup = BeautifulSoup(response.text,"html.parser")
        for span in soup.select("span.sds-comps-text-type-headline1"):
            text = span.get_text()
            if(text in ("경매", "법원경매", "부동산")) :
                continue
            else :
                a = span.find_parent("a")
                href = a.get("href")
                blog_url = href.replace("https://","").replace("http://","").replace("/","_")

                if self.has_blog_content(blog_url) :
                    yield scrapy.Request(href, self.parse_main_blog_html,meta={"blog_url":blog_url})
                else :
                    print("Already crawling")
                    continue

    def has_blog_content(self, url):
        result = False
        settings = get_project_settings()
        path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"/f"{url}.json"

        if path.exists() :
            result = False
        else :
            result = True

        return result

    def parse_main_blog_html(self, response):
        filename = response.meta["blog_url"]
        blog_url = response.url
        soup = BeautifulSoup(response.text,"html.parser")
        iframe = soup.select_one("iframe#mainFrame")
        if iframe :
            iframe_src = iframe.get("src")
            url = "https://blog.naver.com/"+iframe_src
            yield scrapy.Request(url, self.parse_main_container_export, meta={"blog_url":blog_url, "filename":filename})


    def parse_main_container_export(self, response):
        soup = BeautifulSoup(response.text,"html.parser")
        title = str
        content_text = str
        if soup.select("div.se-main-container") is not None:
            title = soup.select_one("div.se-title-text")
            content = soup.select_one("div.se-main-container")
            content_text = content.get_text().replace("\n"," ").replace("  "," ")

        elif soup.select("#postViewArea") is not None :
            content = soup.select_one("#postViewArea")
            content_text = content.get_text().replace("\n"," ").replace("  "," ")

        parsing_blog_item = self.parsing_blog_content_items(title.get_text().replace("\n"," "),
                                                            response.meta["filename"],
                                                            response.meta["blog_url"],
                                                            response.url,
                                                            content_text)
        yield parsing_blog_item
        print(parsing_blog_item)


    def parsing_blog_content_items(self, title, filename, blog_url, content_url, content):
        item = BlogContentItem()
        item['filename'] = filename
        item['blog_url'] = blog_url
        item['content_url'] = content_url
        item['title'] = title
        item['context'] = content
        item['crawled_at'] = datetime.date.today().isoformat()
        return item

    def searching_naver_api_blog(self,query):
        client_id = "lBn2OlsTkSAo6Dyr6h1c"
        client_secret = "rFc99bozMu"
        re_query = urllib.parse.quote(query)

        url = "https://openapi.naver.com/v1/search/blog?query=" + re_query # JSON 결과
        #url = "https://openapi.naver.com/v1/search/blog.xml?query=" + encText # XML 결과
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id",client_id)
        request.add_header("X-Naver-Client-Secret",client_secret)
        response = urllib.request.urlopen(request)
        rescode = response.getcode()
        if(rescode==200):
            response_body = response.read()
            print(query)
            print(response_body.decode('utf-8'))
        else:
            print("Error Code:" + rescode)

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