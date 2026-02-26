"""デモA パイプライン統合（フェーズ1 + フェーズ2）"""

import json
import logging
from datetime import datetime
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

from app.demo_a.chunker import build_document_index
from app.demo_a.extractor import extract_structured_data, postprocess_result
from app.demo_a.grouper import group_fields
from app.demo_a.merger import build_extraction_context
from app.demo_a.schema_builder import build_extraction_schema
from app.demo_a.schemas import SemanticChunk
from app.demo_a.searcher import search_chunks
from app.demo_a.splitter import load_and_split

LOGS_DIR = Path(__file__).parent.parent.parent / "logs"


def _save_json_log(name: str, data: dict | list) -> Path:
    """中間結果をJSONファイルとしてlogs/に保存する。"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = LOGS_DIR / f"{ts}_{name}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    logger.info("ログ保存: %s", path)
    return path


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

        # チャンクインデックスをJSON出力
        _save_json_log(
            "chunk_index",
            {
                "source_pdf": str(pdf_path),
                "total_batches": len(batches),
                "batches": [
                    {
                        "id": b["id"],
                        "label": b["label"],
                        "page_start": b["page_start"],
                        "page_end": b["page_end"],
                        "page_count": b["page_count"],
                    }
                    for b in batches
                ],
                "total_chunks": len(chunk_index),
                "chunks": [c.model_dump() for c in chunk_index],
            },
        )

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

        # グルーピング結果をJSON出力
        _save_json_log(
            "field_groups",
            {
                "field_definitions": field_definitions,
                "groups": [g.model_dump() for g in field_groups.groups],
            },
        )

        # Step 6. チャンク検索
        search_results = search_chunks(chunk_index, field_groups)

        # 検索結果をJSON出力
        _save_json_log(
            "search_results",
            {
                "total_chunks": len(chunk_index),
                "matched_chunks": len(search_results),
                "matched": [c.model_dump() for c in search_results],
            },
        )

        # Step 7. コンテキスト統合
        context_pdf = build_extraction_context(
            search_results,
            pdf_path,
        )

        # コンテキストPDFのページ数を確認してログ出力
        ctx_doc = pymupdf.open(stream=context_pdf, filetype="pdf")
        ctx_pages = len(ctx_doc)
        ctx_doc.close()

        _save_json_log(
            "extraction_context",
            {
                "source_pdf": str(pdf_path),
                "context_pdf_bytes": len(context_pdf),
                "context_pdf_pages": ctx_pages,
                "source_chunks": [
                    {
                        "chunk_id": c.chunk_id,
                        "page_start": c.page_start,
                        "page_end": c.page_end,
                        "query": c.query,
                        "description": c.description,
                    }
                    for c in search_results
                ],
            },
        )

        # Step 8. 構造化抽出
        extracted = extract_structured_data(
            context_pdf,
            field_definitions,
            extraction_model,
        )

    # Step 9. 後処理
    results = postprocess_result(extracted, field_definitions)

    # 最終結果をJSON出力
    _save_json_log("extraction_result", results)

    return results
