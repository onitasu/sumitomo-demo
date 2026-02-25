"""Step 8: 構造化抽出（LLM使用）"""

from pydantic import BaseModel

from app.demo_a.llm_client import get_client


def extract_structured_data(
    pdf_bytes: bytes,
    field_definitions: list[dict],
    extraction_model: type[BaseModel],
) -> BaseModel:
    """PDFからStructured Outputで構造化抽出。

    Args:
        pdf_bytes: PDFのバイト列
        field_definitions: フィールド定義リスト
        extraction_model: 動的生成されたPydanticモデルクラス

    Returns:
        抽出結果のPydanticモデルインスタンス
    """
    client = get_client()

    fields_text = "\n".join(f"- {f['name']}: {f['description']}" for f in field_definitions)

    messages = [
        {
            "role": "user",
            "content": [
                client.build_pdf_content_block(pdf_bytes),
                {
                    "type": "text",
                    "text": (
                        "この文書から以下の項目を抽出してください。\n"
                        "文書に記載がない項目は null にしてください（推測しない）。\n"
                        "数値は単位なしの数値型で返してください。\n\n"
                        f"## 抽出項目\n{fields_text}"
                    ),
                },
            ],
        }
    ]

    return client.structured_extract(
        messages=messages,
        output_format=extraction_model,
    )


def postprocess_result(
    extracted: BaseModel,
    field_definitions: list[dict],
) -> list[dict]:
    """抽出結果に「文書に記載があったか」を付与。"""
    results = []
    for f in field_definitions:
        value = getattr(extracted, f["name"], None)
        results.append(
            {
                "field_name": f["name"],
                "description": f["description"],
                "type": f["type"],
                "value": value,
                "found_in_document": value is not None,
                "status": "抽出済み" if value is not None else "記載なし",
            }
        )
    return results
