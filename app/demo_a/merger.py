"""Step 7: コンテキスト統合（関連チャンク→PDFページ切出し）"""

from pathlib import Path

import pymupdf

from app.demo_a.schemas import SemanticChunk


def _merge_page_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """ページ範囲をソートし、重複・隣接する範囲をマージする。"""
    if not ranges:
        return []

    sorted_ranges = sorted(ranges)
    merged: list[tuple[int, int]] = [sorted_ranges[0]]

    for start, end in sorted_ranges[1:]:
        if start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    return merged


def build_extraction_context(
    relevant_chunks: list[SemanticChunk],
    pdf_path: Path,
    max_pages: int = 100,
) -> bytes:
    """関連チャンクからPDFのページを統合して抽出用コンテキストを構築。

    searcher.pyがIDではなくSemanticChunkを返すため、chunk_mapルックアップは不要。

    Args:
        relevant_chunks: high/mediumと評価されたSemanticChunkのリスト
        pdf_path: 元PDFファイルパス
        max_pages: 最大ページ数

    Returns:
        統合されたPDFのバイト列（チャンクが0件の場合は全文PDFを返す）
    """
    # ページ範囲を収集（max_pages以内に収める）
    page_ranges: list[tuple[int, int]] = []
    total_pages = 0
    for chunk in relevant_chunks:
        pages = chunk.page_end - chunk.page_start + 1
        if total_pages + pages <= max_pages:
            page_ranges.append((chunk.page_start, chunk.page_end))
            total_pages += pages

    # チャンクが0件 or 全件がmax_pagesを超えた場合は全文PDFにフォールバック
    if not page_ranges:
        return pdf_path.read_bytes()

    # マージ・重複排除
    merged = _merge_page_ranges(page_ranges)

    # 元PDFから該当ページを切り出し
    doc = pymupdf.open(pdf_path)
    out_doc = pymupdf.open()
    for start, end in merged:
        out_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)

    if len(out_doc) == 0:
        out_doc.close()
        doc.close()
        return pdf_path.read_bytes()

    pdf_bytes = out_doc.tobytes()
    out_doc.close()
    doc.close()

    return pdf_bytes
