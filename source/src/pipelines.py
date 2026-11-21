# 스파이더가 만든 item을 받아 중복/광고/AI글 판별 후 JSON 파일로 저장 (settings.ITEM_PIPELINES에 등록)
import json
import logging
from pathlib import Path

from scrapy.utils.project import get_project_settings
from source.src.items import ContentItem
from source.src.content_filter import content_hash, exclude_reason, is_borderline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class SrcPipeline:
    def open_spider(self, spider):
        """크롤링 시작 시 1회 호출. 이미 저장된 글의 본문 해시를 모아 둠 (본문 중복 판별용)."""
        # ponytail: 시작 시 저장된 JSON 전부 읽어 해시 수집. 수만 건 넘어가면 DB unique index로 이동
        base = Path(get_project_settings().get("BASE_DIR"))/"source"/"src"/"blog_content"
        self.seen_hashes = {}
        for f in base.glob("*/*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not str(d.get("excluded_reason") or "").startswith("duplicate"):
                self.seen_hashes.setdefault(d.get("content_hash") or content_hash(d.get("context")), d.get("filename"))

    def process_item(self, item, spider):
        """item마다 호출. excluded_reason: None(사용) / duplicate:원본파일명 / ad:사유 / ai:점수."""
        if isinstance(item, ContentItem) :
            # 제외된 글도 저장 → 다음 크롤링 때 재요청 안 함 + 오탐 확인 가능
            h = item["content_hash"] = content_hash(item["context"])
            if h in self.seen_hashes:
                item["excluded_reason"] = f"duplicate:{self.seen_hashes[h]}"
            else:
                self.seen_hashes[h] = item["filename"]
                item["excluded_reason"] = exclude_reason(item["title"], item["context"])
                if (not item["excluded_reason"] and spider.settings.getbool("AI_CHECK_WITH_LLM")
                        and is_borderline(item["title"], item["context"])):
                    item["excluded_reason"] = self.llm_reason(item)
            if item["excluded_reason"]:
                logger.info(f"Excluded|{item['excluded_reason']}|{item['filename']}")
            self.save_blog_content(item)

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

    def save_blog_content(self, item):
        """blog_content/{platform}/{filename}.json 으로 저장. 같은 파일명이면 덮어씀."""
        try:
            settings = get_project_settings()
            path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"/f"{item["platform"]}"
            path.mkdir(parents=True, exist_ok=True)

            filename = f"{item["filename"]}.json"

            save_path = path / filename
            print(f">>>>>>>>{filename}")
            with open(save_path,"w", encoding="utf-8") as f :
                json.dump(dict(item), f, ensure_ascii=False)

        except Exception as e:
            logger.exception(f"BlogContentLoader|file_load Error|{e}")

