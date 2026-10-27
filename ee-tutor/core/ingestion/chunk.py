from pydantic import BaseModel
from typing import Optional

class Chunk(BaseModel):
    chunk_id: str
    source_id: str
    text: str
    page: Optional[int] = None
    timestamp: Optional[str] = None
    topics: list[str]
    license: str
    tier: str
