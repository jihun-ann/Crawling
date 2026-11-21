
import scrapy


class SrcItem(scrapy.Item):
    pass


class ContentItem(scrapy.Item):
    filename = scrapy.Field()               #파일명
    init_url = scrapy.Field()               #글 URL
    content_url = scrapy.Field()            #IFrameURL, 본문URL
    platform = scrapy.Field()               #검색 플랫폼
    title = scrapy.Field()                  #글 제목
    context = scrapy.Field()                #글 내용
    crawled_at = scrapy.Field()             #크롤링 일자
    posted_at = scrapy.Field()              #글 작성일 (YYYY-MM-DD, 모르면 None) → 최근 30일 언급 수 계산용
    keyword = scrapy.Field()
    content_hash = scrapy.Field()           #본문 해시 (동일 본문 중복 판별)
    excluded_reason = scrapy.Field()        #제외 사유 (ad:*, ai:*, duplicate:*) / None이면 사용