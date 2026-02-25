"""デモA パイプライン統合（フェーズ1 + フェーズ2）"""

from pathlib import Path

from app.demo_a.chunker import build_document_index
from app.demo_a.extractor import extract_structured_data, postprocess_result
from app.demo_a.grouper import group_fields
from app.demo_a.merger import build_extraction_context
from app.demo_a.schema_builder import build_extraction_schema
from app.demo_a.schemas import SemanticChunk
from app.demo_a.searcher import search_chunks
from app.demo_a.splitter import load_and_split


def build_index(
    pdf_path: Path,
) -> tuple[Path, list[dict], list[SemanticChunk] | None]:
    """フェーズ1: インデックス構築（ファイルアップロード時に1回だけ実行）。

    Args:
        pdf_path: PDFファイルパス

    Returns:
        (pdf_path, batches, chunk_index)
        chunk_index は100ページ以下の文書ではNone
    """
    batches = load_and_split(pdf_path)

    chunk_index = None
    if len(batches) > 1:
        chunk_index = build_document_index(batches)

    return pdf_path, batches, chunk_index


def extract_with_schema(
    pdf_path: Path,
    batches: list[dict],
    chunk_index: list[SemanticChunk] | None,
    field_definitions: list[dict],
) -> list[dict]:
    """フェーズ2: 検索→抽出（スキーマ提出ごとに実行）。

    スキーマを変えて再実行する場合、この関数だけ呼び直す。

    Args:
        pdf_path: 元PDFファイルパス
        batches: フェーズ1で作成されたバッチ
        chunk_index: セマンティックチャンクインデックス（小文書ではNone）
        field_definitions: 抽出フィールド定義

    Returns:
        抽出結果リスト
    """
    extraction_model = build_extraction_schema(field_definitions)

    if chunk_index is None:
        # 小さい文書: そのまま丸ごとSonnetに投入（Step 5-7スキップ）
        extracted = extract_structured_data(
            batches[0]["pdf_bytes"],
            field_definitions,
            extraction_model,
        )
    else:
        # 大きい文書: クエリベース検索 → コンテキスト統合 → 抽出
        # Step 5. フィールドグルーピング + クエリ生成
        field_groups = group_fields(field_definitions)

        # Step 6. チャンク検索
        search_results = search_chunks(chunk_index, field_groups)

        # Step 7. コンテキスト統合
        context_pdf = build_extraction_context(
            search_results,
            chunk_index,
            pdf_path,
        )

        # Step 8. 構造化抽出
        extracted = extract_structured_data(
            context_pdf,
            field_definitions,
            extraction_model,
        )

    # Step 9. 後処理
    return postprocess_result(extracted, field_definitions)
