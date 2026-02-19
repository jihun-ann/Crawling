
import json
import logging
from pathlib import Path

from scrapy.utils.project import get_project_settings
from source.src.items import ContentItem

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class SrcPipeline:
    def process_item(self, item, spider):

        if isinstance(item, ContentItem) :
            self.save_blog_content(item)

        return item

    def save_blog_content(self, item):
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

