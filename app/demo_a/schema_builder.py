"""Step 4: 動的Pydanticモデル生成"""

from pydantic import BaseModel, Field, create_model

TYPE_MAP: dict[str, type] = {
    "テキスト": str,
    "数値": float,
    "整数": int,
    "真偽": bool,
}


def build_extraction_schema(
    field_definitions: list[dict],
) -> type[BaseModel]:
    """UIで定義されたフィールドからPydanticモデルを動的生成。

    各フィールドは Optional（None許容）。文書に記載がない場合 None を返せるように。

    Args:
        field_definitions: [{"name": str, "type": str, "description": str}, ...]

    Returns:
        動的生成されたPydanticモデルクラス
    """
    pydantic_fields = {}
    for f in field_definitions:
        field_type = TYPE_MAP.get(f["type"], str)
        pydantic_fields[f["name"]] = (
            field_type | None,
            Field(None, description=f["description"]),
        )
    return create_model("DynamicExtraction", **pydantic_fields)
