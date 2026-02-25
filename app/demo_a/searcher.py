"""Step 6: チャンク検索（評価型 - LLMはrelevanceを付けるだけでIDを生成しない）"""

from app.demo_a.llm_client import get_client
from app.demo_a.schemas import ChunkEvaluations, GroupingResult, SemanticChunk


def search_chunks(
    chunk_index: list[SemanticChunk],
    field_groups: GroupingResult,
) -> list[SemanticChunk]:
    """チャンクインデックスに対してクエリベース検索。

    LLMにchunk_idを「選ばせる」のではなく、各チャンクを「評価させる」ことで
    ハルシネーションによるID不一致を防ぐ。

    Args:
        chunk_index: セマンティックチャンクのリスト
        field_groups: フィールドグルーピング結果

    Returns:
        high / medium と評価されたSemanticChunkのリスト（noneは除外済み）
    """
    client = get_client()

    # 検索クエリをまとめる
    queries_text = "\n".join(f"- {g.group_name}: {g.search_query}" for g in field_groups.groups)

    # chunk_idとqueryを列挙（LLMはこのIDをそのまま返すだけでよい）
    chunks_text = "\n".join(
        f"chunk_id={c.chunk_id} | {c.query}" for c in chunk_index
    )

    messages = [
        {
            "role": "user",
            "content": (
                "以下の検索クエリに対して、各チャンクの関連度を評価してください。\n\n"
                "ルール:\n"
                "- relevance='high': 検索クエリに直接関連する情報が含まれる可能性が高い\n"
                "- relevance='medium': 補足的な情報が含まれる可能性がある\n"
                "- relevance='none': 関連しない\n"
                "- chunk_idは与えられた値をそのままコピーすること（変更禁止）\n"
                "- 全チャンクを評価し、evaluationsリストに全件返すこと\n\n"
                f"## 検索クエリ\n{queries_text}\n\n"
                f"## 評価対象チャンク（全{len(chunk_index)}件）\n{chunks_text}"
            ),
        }
    ]

    result: ChunkEvaluations = client.structured_extract(
        messages=messages,
        output_format=ChunkEvaluations,
    )

    # LLMが返したevaluationsからhigh/mediumのchunk_idを抽出
    relevant_ids = {
        e.chunk_id for e in result.evaluations if e.relevance in ("high", "medium")
    }

    # chunk_indexから該当するチャンクを順番通りに返す（IDはこちらが持つ）
    matched = [c for c in chunk_index if c.chunk_id in relevant_ids]

    # LLMが全件noneと判定した場合は先頭5チャンクをフォールバックとして返す
    if not matched:
        return chunk_index[:5]

    return matched
