"""사설 데이터 모델."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Editorial:
    source: str
    title: str
    url: str
    summary: Optional[str]
    content: Optional[str]
    published_date: str  # YYYY-MM-DD

    def to_dict(self):
        return {
            "source": self.source,
            "title": self.title,
            "url": self.url,
            "summary": self.summary or "",
            "content": self.content or "",
            "published_date": self.published_date,
        }
