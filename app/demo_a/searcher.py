"""Step 6: チャンク検索（LLM使用）"""

from app.demo_a.llm_client import get_client
from app.demo_a.schemas import GroupingResult, SearchResults, SemanticChunk


def search_chunks(
    chunk_index: list[SemanticChunk],
    field_groups: GroupingResult,
) -> SearchResults:
    """チャンクインデックスに対してクエリベース検索。

    queryとchunk_idのみで判断。descriptionは渡さない。

    Args:
        chunk_index: セマンティックチャンクのリスト
        field_groups: フィールドグルーピング結果

    Returns:
        SearchResults
    """
    client = get_client()

    # チャンクインデックス: queryとIDのみを渡す（descriptionは渡さない）
    index_text = "\n".join(f"- {c.chunk_id}: {c.query}" for c in chunk_index)

    # グループのsearch_query一覧
    groups_text = "\n".join(f"- {g.group_name}: {g.search_query}" for g in field_groups.groups)

    messages = [
        {
            "role": "user",
            "content": (
                "以下のチャンクインデックスから、各グループの検索クエリに関連するチャンクを選んでください。\n\n"
                "ルール:\n"
                "- relevance='high': 直接的に関連する情報が含まれている可能性が高い\n"
                "- relevance='medium': 補足的な情報が含まれている可能性がある\n"
                "- 関連しないチャンクは含めない\n"
                "- 各グループに対してhigh 1-3個 + medium 0-3個が目安\n\n"
                f"## チャンクインデックス\n{index_text}\n\n"
                f"## 検索クエリ\n{groups_text}"
            ),
        }
    ]

    return client.structured_extract(
        messages=messages,
        output_format=SearchResults,
    )
