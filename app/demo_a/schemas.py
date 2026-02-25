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


# --- Step 6: チャンク検索（評価型） ---
# LLMはchunk_idを「生成」せず、こちらが渡したIDに対して relevance を付けるだけ。
# ハルシネーションによるID不一致を根本的に防ぐ設計。


class ChunkEvaluation(BaseModel):
    """1チャンクの関連度評価。chunk_idはこちらから渡し、LLMはrelevanceだけ返す。"""

    chunk_id: str
    relevance: str  # "high" / "medium" / "none"


class ChunkEvaluations(BaseModel):
    """全チャンクの関連度評価リスト。"""

    evaluations: list[ChunkEvaluation]
