# Tistory 등 다음(Daum) 블로그 + 일반 웹문서 후기 크롤러. 카카오 검색 API(블로그/웹문서, 무료)로 URL을 받고 본문은 직접 수집
# 실행: scrapy crawl daum_crawling -a query="강릉 카페"
# 필요: .env 의 KAKAO_REST_API_KEY (developers.kakao.com > 내 애플리케이션 > REST API 키)
import datetime
import json
import logging
import urllib.parse

import scrapy
from bs4 import BeautifulSoup

from source.src.content_filter import content_id, parse_post_date
from source.src.items import ContentItem
from source.src.sqlalchemy.crud import raw_post_crud

logger = logging.getLogger(__name__)

# Tistory 스킨마다 본문 영역 클래스가 다름 → 순서대로 시도
BODY_SELECTORS = ("div.tt_article_useless_p_margin", "div.entry-content", "div.article_view", "div#article-view",
                  "div.contents_style", "div.area_view", "article")
# 다른 수집기가 담당하거나(네이버 블로그, 유튜브) 로그인/앱 전용이라 본문을 못 읽는 곳
SKIP_HOSTS = ("blog.naver.com", "youtube.com", "youtu.be", "instagram.com", "cafe.naver.com", "facebook.com")


class DaumBlogSpider(scrapy.Spider):
    name = "daum_crawling"
    pages = 3                   # 검색 결과 페이지 수 (페이지당 50건)

    def start_requests(self):
        key = self.settings.get("KAKAO_REST_API_KEY")
        query = getattr(self, "query", None)
        if not key or not query:
            logger.error("KAKAO_REST_API_KEY(.env)와 -a query=검색어 가 필요합니다")
            return
        # blog: Tistory 등 블로그 / web: 일반 웹문서 (Google 검색 대신 쓰는 무료 웹 검색)
        for target, platform in (("blog", "daum"), ("web", "web")):
            for page in range(1, self.pages + 1):
                url = f"https://dapi.kakao.com/v2/search/{target}?query={urllib.parse.quote(query)}&size=50&page={page}"
                yield scrapy.Request(url, self.parse_search, headers={"Authorization": f"KakaoAK {key}"},
                                     meta={"keyword": query, "platform": platform})

    def parse_search(self, response):
        """검색 결과(JSON) → 글마다 본문 요청. 다른 수집기 담당(네이버 블로그, 유튜브)과 본문을 못 읽는 곳, 이미 저장된 글은 제외."""
        docs = {content_id(d["url"]): d for d in json.loads(response.text).get("documents", [])
                if not any(s in d["url"] for s in SKIP_HOSTS)}
        known = raw_post_crud.known_ids(docs)
        for cid, doc in docs.items():
            if cid not in known:
                yield scrapy.Request(doc["url"], self.parse_post, meta={**response.meta, "cid": cid, "doc": doc})

    def parse_post(self, response):
        """글 페이지에서 제목/본문 추출 → ContentItem (pipelines에서 중복/광고/AI글 판별 후 저장)."""
        soup = BeautifulSoup(response.text, "html.parser")
        body = next((soup.select_one(s) for s in BODY_SELECTORS if soup.select_one(s)), None)
        if body is None:
            logger.info(f"본문 영역 없음, 건너뜀: {response.url}")
            return
        doc = response.meta["doc"]
        og_title = soup.select_one('meta[property="og:title"]')
        item = ContentItem()
        item["filename"] = response.meta["cid"]
        item["init_url"] = doc["url"]
        item["content_url"] = response.url
        item["platform"] = response.meta["platform"]
        item["title"] = og_title["content"] if og_title else BeautifulSoup(doc["title"], "html.parser").get_text()
        item["context"] = body.get_text("\n")
        item["crawled_at"] = datetime.date.today().isoformat()
        item["posted_at"] = parse_post_date(doc.get("datetime"))
        item["keyword"] = response.meta["keyword"]
        yield item
