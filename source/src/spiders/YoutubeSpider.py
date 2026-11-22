# 유튜브 후기 수집. YouTube Data API v3로 영상 검색 → 제목 + 설명 + 인기 댓글을 하나의 글처럼 저장
# 실행: scrapy crawl youtube_crawling -a query="강릉 카페 브이로그"
# 필요: .env 의 YOUTUBE_API_KEY (Google Cloud Console > YouTube Data API v3 사용 설정 > API 키)
# 할당량: 하루 10,000 unit. search 1회 = 100 unit, videos/commentThreads 1회 = 1 unit → 검색은 하루 약 90회
import datetime
import json
import logging
import urllib.parse

import scrapy

from source.src.content_filter import parse_post_date
from source.src.items import ContentItem
from source.src.sqlalchemy.crud import raw_post_crud

logger = logging.getLogger(__name__)
API = "https://www.googleapis.com/youtube/v3"


class YoutubeSpider(scrapy.Spider):
    name = "youtube_crawling"
    platform = "youtube"        # raw_post.platform 값
    max_results = 25            # 검색 1회당 영상 수 (최대 50)
    comments = 20               # 영상당 댓글 수

    def start_requests(self):
        self.key = self.settings.get("YOUTUBE_API_KEY")
        query = getattr(self, "query", None)
        if not self.key or not query:
            logger.error("YOUTUBE_API_KEY(.env)와 -a query=검색어 가 필요합니다")
            return
        params = {"part": "id", "q": query, "type": "video", "maxResults": self.max_results,
                  "regionCode": "KR", "relevanceLanguage": "ko", "key": self.key}
        yield scrapy.Request(f"{API}/search?{urllib.parse.urlencode(params)}", self.parse_search, meta={"keyword": query})

    def parse_search(self, response):
        """검색 결과 → 아직 저장 안 한 영상만 상세 정보(videos) 요청."""
        found = [it["id"]["videoId"] for it in json.loads(response.text).get("items", [])]
        known = raw_post_crud.known_ids(f"youtube.com_{v}" for v in found)
        ids = [v for v in found if f"youtube.com_{v}" not in known]
        if ids:
            params = {"part": "snippet", "id": ",".join(ids), "key": self.key}
            yield scrapy.Request(f"{API}/videos?{urllib.parse.urlencode(params)}", self.parse_videos, meta=response.meta)

    def parse_videos(self, response):
        """영상마다 댓글 요청. 댓글이 꺼진 영상(403)도 설명만으로 저장되도록 errback 사용."""
        for v in json.loads(response.text).get("items", []):
            params = {"part": "snippet", "videoId": v["id"], "maxResults": self.comments, "order": "relevance",
                      "textFormat": "plainText", "key": self.key}
            meta = {**response.meta, "video": v}
            yield scrapy.Request(f"{API}/commentThreads?{urllib.parse.urlencode(params)}", self.parse_comments,
                                 errback=self.comments_failed, meta=meta)

    def parse_comments(self, response):
        comments = [c["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                    for c in json.loads(response.text).get("items", [])]
        yield self.make_item(response.meta["video"], comments, response.meta["keyword"])

    def comments_failed(self, failure):
        meta = failure.request.meta
        yield self.make_item(meta["video"], [], meta["keyword"])

    def make_item(self, video, comments, keyword):
        s = video["snippet"]
        url = f"https://www.youtube.com/watch?v={video['id']}"
        item = ContentItem()
        item["filename"] = f"youtube.com_{video['id']}"
        item["init_url"] = url
        item["content_url"] = url
        item["platform"] = self.platform
        item["title"] = s["title"]
        # ponytail: 자막(실제 말한 내용)은 공식 API로 못 받음. 필요하면 youtube-transcript-api(비공식) 추가
        item["context"] = "\n".join([s["title"], s.get("description", ""), "[댓글]", *comments])
        item["crawled_at"] = datetime.date.today().isoformat()
        item["posted_at"] = parse_post_date(s.get("publishedAt"))
        item["keyword"] = keyword
        return item
