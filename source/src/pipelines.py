# 스파이더가 만든 item을 받아 중복/광고/AI글 판별 후 DB(raw_post)에 저장 (settings.ITEM_PIPELINES에 등록)
import logging

from source.src.items import ContentItem
from source.src.content_filter import content_hash, exclude_reason, is_borderline
from source.src.sqlalchemy.crud import raw_post_crud

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class SrcPipeline:
    def process_item(self, item, spider):
        """item마다 호출. excluded_reason: None(사용) / duplicate:원본ID / ad:사유 / ai:점수 / llm:*."""
        if isinstance(item, ContentItem) :
            # 제외된 글도 저장 → 다음 크롤링 때 재요청 안 함 + 오탐 확인 가능
            h = item["content_hash"] = content_hash(item["context"])
            original = raw_post_crud.duplicate_of(h)
            if original:
                item["excluded_reason"] = f"duplicate:{original}"
            else:
                item["excluded_reason"] = exclude_reason(item["title"], item["context"])
                if (not item["excluded_reason"] and spider.settings.getbool("AI_CHECK_WITH_LLM")
                        and is_borderline(item["title"], item["context"])):
                    item["excluded_reason"] = self.llm_reason(item)
            if item["excluded_reason"]:
                logger.info(f"Excluded|{item['excluded_reason']}|{item['filename']}")
            raw_post_crud.insert(to_row(dict(item)))

        return item

    def llm_reason(self, item):
        """Claude 2차 판정 → 'llm:ad:근거' / 'llm:ai:근거' / None. 판정 실패하면 통과로 둠."""
        from source.src.llm_check import llm_verdict
        v = llm_verdict(item["title"], item["context"])
        if not v:
            return None
        if v["sponsored"]:
            return f"llm:ad:{v['reason']}"
        if v["ai_written"]:
            return f"llm:ai:{v['reason']}"
        return None


def to_row(item: dict):
    """ContentItem(또는 예전 JSON) 필드명 → raw_post 컬럼명."""
    return {**item, "content_id": item.get("filename"), "url": item.get("init_url"), "body": item.get("context")}
