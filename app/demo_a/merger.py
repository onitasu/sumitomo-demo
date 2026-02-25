"""Step 7: コンテキスト統合（検索結果→PDFページ切出し）"""

from pathlib import Path

import pymupdf

from app.demo_a.schemas import SearchResults, SemanticChunk


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


def _collect_page_ranges(
    search_results: SearchResults,
    chunk_index: list[SemanticChunk],
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """検索結果からhigh/mediumのページ範囲を収集する。"""
    chunk_map = {c.chunk_id: c for c in chunk_index}

    high_ids: set[str] = set()
    medium_ids: set[str] = set()

    for group_result in search_results.results:
        for match in group_result.matched_chunks:
            if match.relevance == "high":
                high_ids.add(match.chunk_id)
            else:
                medium_ids.add(match.chunk_id)

    high_ranges = [(chunk_map[cid].page_start, chunk_map[cid].page_end) for cid in high_ids if cid in chunk_map]
    medium_ranges = [
        (chunk_map[cid].page_start, chunk_map[cid].page_end) for cid in medium_ids - high_ids if cid in chunk_map
    ]

    return high_ranges, medium_ranges


def build_extraction_context(
    search_results: SearchResults,
    chunk_index: list[SemanticChunk],
    pdf_path: Path,
    max_pages: int = 100,
) -> bytes:
    """検索結果からPDFのページを統合して抽出用コンテキストを構築。

    Args:
        search_results: チャンク検索結果
        chunk_index: セマンティックチャンクインデックス
        pdf_path: 元PDFファイルパス
        max_pages: 最大ページ数

    Returns:
        統合されたPDFのバイト列
    """
    high_ranges, medium_ranges = _collect_page_ranges(search_results, chunk_index)

    # highを優先して追加、余裕があればmediumも
    page_ranges: list[tuple[int, int]] = []
    total_pages = 0

    for start, end in sorted(high_ranges):
        pages = end - start + 1
        if total_pages + pages <= max_pages:
            page_ranges.append((start, end))
            total_pages += pages

    for start, end in sorted(medium_ranges):
        pages = end - start + 1
        if total_pages + pages <= max_pages:
            page_ranges.append((start, end))
            total_pages += pages

    # マージ・重複排除
    merged = _merge_page_ranges(page_ranges)

    # 元PDFから該当ページを切り出し
    doc = pymupdf.open(pdf_path)
    out_doc = pymupdf.open()
    for start, end in merged:
        out_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
    pdf_bytes = out_doc.tobytes()
    out_doc.close()
    doc.close()

    return pdf_bytes
