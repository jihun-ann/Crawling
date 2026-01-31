
import json
from pathlib import Path

from scrapy.utils.project import get_project_settings

from source.src.items import ContentItem


class SrcPipeline:
    def process_item(self, item, spider):

        if isinstance(item, ContentItem) :
            self.save_blog_content(item)

        return item

    def save_blog_content(self, item):
        settings = get_project_settings()
        path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"/f"{item["platform"]}"
        path.mkdir(parents=True, exist_ok=True)

        filename = f"{item["filename"]}.json"

        save_path = path / filename

        with open(save_path,"w", encoding="utf-8") as f :
            json.dump(dict(item), f, ensure_ascii=False)


