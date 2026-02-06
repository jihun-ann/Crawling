
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