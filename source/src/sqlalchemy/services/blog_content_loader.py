import json
import logging
import re
from scrapy.utils.project import get_project_settings
from pathlib import Path


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

class BlogContentLoader:
    def __init__(self):
        settings = get_project_settings()
        self.path = Path(settings.get("BASE_DIR"))/"source"/"src"/"blog_content"

    def file_load(self):
        try:
            for dir in self.path.iterdir():
                content_dir = self.path/dir

                for file in content_dir.glob("*.json"):
                # for file in content_dir.glob("*223396237018.json"):
                    if not file.name.startswith("s_"):
                        with open(file, "r+", encoding="utf-8") as f:
                            file_data = json.load(f)
                            address_pattern = r'(?:[가-힣]+(?:시|도)\s)?[가-힣]+(?:구|군)\s[가-힣\d\s-]+(?:로|길)\s?[\d-]+'
                            address = re.search(address_pattern, file_data["context"])
                            print(address)
                            # if not address:
                            #     print(file_data)
                            #     print(file_data["title"])
                            #     print(file_data["context"])
                            #     print(address)
        except Exception as e:
            logger.error(f"BlogContentLoader|file_load Error|{e}")



if __name__=="__main__":
    loader = BlogContentLoader()
    loader.file_load()