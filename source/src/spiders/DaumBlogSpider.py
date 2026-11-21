# Tistory 등 다음(Daum) 블로그 후기 크롤러. 카카오 블로그 검색 API로 글 URL을 받고 본문은 직접 수집
# 실행: scrapy crawl daum_crawling -a query="강릉 카페"
# 필요: .env 의 KAKAO_REST_API_KEY (developers.kakao.com > 내 애플리케이션 > REST API 키)
import datetime
import json
import logging
import urllib.parse
from pathlib import Path

import scrapy
from bs4 import BeautifulSoup

from source.src.content_filter import content_id, parse_post_date
from source.src.items import ContentItem

logger = logging.getLogger(__name__)

# Tistory 스킨마다 본문 영역 클래스가 다름 → 순서대로 시도
BODY_SELECTORS = ("div.tt_article_useless_p_margin", "div.entry-content", "div.article_view", "div#article-view",
                  "div.contents_style", "div.area_view", "article")


class DaumBlogSpider(scrapy.Spider):
    name = "daum_crawling"
    platform = "daum"           # 저장 폴더명 (blog_content/daum)
    pages = 3                   # 검색 결과 페이지 수 (페이지당 50건)

    def start_requests(self):
        key = self.settings.get("KAKAO_REST_API_KEY")
        query = getattr(self, "query", None)
        if not key or not query:
            logger.error("KAKAO_REST_API_KEY(.env)와 -a query=검색어 가 필요합니다")
            return
        for page in range(1, self.pages + 1):
            url = f"https://dapi.kakao.com/v2/search/blog?query={urllib.parse.quote(query)}&size=50&page={page}"
            yield scrapy.Request(url, self.parse_search, headers={"Authorization": f"KakaoAK {key}"},
                                 meta={"keyword": query})

    def parse_search(self, response):
        """검색 결과(JSON) → 글마다 본문 요청. 네이버 블로그는 NaverSpider가 담당하므로 제외, 이미 저장된 글도 제외."""
        base = Path(self.settings.get("BASE_DIR")) / "source" / "src" / "blog_content" / self.platform
        for doc in json.loads(response.text).get("documents", []):
            url = doc["url"]
            if "blog.naver.com" in url:
                continue
            cid = content_id(url)
            if (base / f"{cid}.json").exists():
                continue
            yield scrapy.Request(url, self.parse_post, meta={**response.meta, "cid": cid, "doc": doc})

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
        item["platform"] = self.platform
        item["title"] = og_title["content"] if og_title else BeautifulSoup(doc["title"], "html.parser").get_text()
        item["context"] = body.get_text("\n")
        item["crawled_at"] = datetime.date.today().isoformat()
        item["posted_at"] = parse_post_date(doc.get("datetime"))
        item["keyword"] = response.meta["keyword"]
        yield item
