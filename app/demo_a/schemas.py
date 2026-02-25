"""デモA用 Pydanticスキーマ定義（LLM入出力）"""

from pydantic import BaseModel

# --- Step 3: セマンティックチャンク ---


class SemanticChunk(BaseModel):
    """セマンティックチャンク。意味のある文書単位。"""

    chunk_id: str
    page_start: int
    page_end: int
    query: str
    description: str


class BatchChunkResult(BaseModel):
    """1バッチから生成されたセマンティックチャンクのリスト。"""

    chunks: list[SemanticChunk]


# --- Step 5: フィールドグルーピング ---


class FieldGroup(BaseModel):
    """意味的に近いフィールドのグループ。"""

    group_name: str
    field_names: list[str]
    search_query: str


class GroupingResult(BaseModel):
    """フィールドグルーピングの結果。"""

    groups: list[FieldGroup]


# --- Step 6: チャンク検索 ---


class ChunkMatch(BaseModel):
    """チャンクとグループの照合結果。"""

    chunk_id: str
    relevance: str  # "high" / "medium"


class GroupSearchResult(BaseModel):
    """1グループの検索結果。"""

    group_name: str
    matched_chunks: list[ChunkMatch]


class SearchResults(BaseModel):
    """全グループの検索結果。"""

    results: list[GroupSearchResult]
