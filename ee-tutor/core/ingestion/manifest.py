from pydantic import BaseModel
from typing import Literal, Optional
import yaml

class Source(BaseModel):
    id: str
    type: Literal["pdf", "youtube_playlist", "youtube_video", "web"]
    url: Optional[str] = None
    path: Optional[str] = None
    license: str
    topics: list[str]
    tier: Literal["A", "local"]

def load_manifest(p="sources.yaml") -> list[Source]:
    with open(p, encoding="utf-8") as f:
        return [Source(**s) for s in yaml.safe_load(f)]

if __name__ == "__main__":
    for s in load_manifest():
        print(s.id, "OK")