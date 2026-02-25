"""Step 5: フィールドグルーピング + クエリ生成（LLM使用）"""

from app.demo_a.llm_client import get_client
from app.demo_a.schemas import GroupingResult


def group_fields(field_definitions: list[dict]) -> GroupingResult:
    """フィールドを意味的にグルーピングし、各グループに検索クエリを生成。

    Args:
        field_definitions: [{"name": str, "type": str, "description": str}, ...]

    Returns:
        GroupingResult
    """
    client = get_client()

    fields_text = "\n".join(f"- {f['name']}: {f['description']}" for f in field_definitions)

    messages = [
        {
            "role": "user",
            "content": (
                "以下の抽出フィールドを意味的に近いもの同士でグループ化してください。\n"
                "各グループには、関連する文書セクションを見つけるための検索クエリを生成してください。\n\n"
                "ルール:\n"
                "- 1グループ2-5フィールド程度\n"
                "- 全フィールドがいずれかのグループに属すること（漏れなし）\n"
                "- 検索クエリは日本語と英語を混ぜてOK（文書が英語の可能性があるため）\n\n"
                f"## フィールド一覧\n{fields_text}"
            ),
        }
    ]

    return client.structured_extract(
        messages=messages,
        output_format=GroupingResult,
    )
