import datetime
import json
import uuid
from importlib import resources
from pathlib import Path

from scrapy.utils.project import get_project_settings

from source.src.items import BlogContentItem


class SrcPipeline:
    def process_item(self, item, spider):

        if isinstance(item, BlogContentItem):
            self.save_blog_content(item)

        return item

    def save_blog_content(self, item):
        settings = get_project_settings()
        path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"
        path.mkdir(parents=True, exist_ok=True)

        filename = f"{item["filename"]}.json"

        save_path = path / filename

        with open(save_path,"w", encoding="utf-8") as f :
            json.dump(dict(item), f, ensure_ascii=False)


