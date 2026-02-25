"""Step 3: セマンティックチャンク生成（LLM使用・並列処理）"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import pymupdf
from anthropic import BadRequestError

from app.demo_a.llm_client import get_client
from app.demo_a.schemas import BatchChunkResult, SemanticChunk

logger = logging.getLogger(__name__)


def build_semantic_chunks(
    batch: dict,
    batch_index: int,
) -> BatchChunkResult:
    """20ページPDFバッチをSonnetに見せてセマンティックチャンクを生成。

    Args:
        batch: バッチ情報（pdf_bytes, page_start, page_end）
        batch_index: バッチの通し番号（0始まり）
    """
    client = get_client()

    messages = [
        {
            "role": "user",
            "content": [
                client.build_pdf_content_block(batch["pdf_bytes"]),
                {
                    "type": "text",
                    "text": (
                        "この文書を意味のある単位（セクション・章・条項など）でチャンクに分割してください。\n\n"
                        "各チャンクには以下を付与してください:\n"
                        f"- chunk_id: 'chunk_{batch_index:03d}_001' からバッチ内連番\n"
                        f"- page_start / page_end: 実際のページ番号"
                        f"（この文書はp.{batch['page_start']}–{batch['page_end']}）\n"
                        "- query: このチャンクを検索で見つけるためのキーワード（1-2文）\n"
                        "- description: チャンクの内容説明（2-3文）\n\n"
                        "分割のルール:\n"
                        "- 1つのセクション/条項が複数ページにまたがる場合は、1つのチャンクとしてまとめる\n"
                        "- 新しいセクション/条項が始まる箇所で区切る\n"
                        "- テーブルは前後のテキストと同じチャンクに含める\n"
                        "- 1バッチあたり5-10チャンクが目安"
                    ),
                },
            ],
        }
    ]

    return client.structured_extract(
        messages=messages,
        output_format=BatchChunkResult,
    )


def _text_fallback_chunks(
    pdf_bytes: bytes,
    page_start: int,
    page_end: int,
    pages_per_chunk: int = 5,
) -> list[SemanticChunk]:
    """PDFバイト列からpymupdfでテキスト抽出し、簡易チャンクを生成する。

    Claude APIでPDF処理エラーが発生した場合のフォールバック。

    Args:
        pdf_bytes: PDFバイト列
        page_start: バッチの開始ページ番号（1始まり）
        page_end: バッチの終了ページ番号
        pages_per_chunk: 1チャンクあたりのページ数
    """
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    total_pages = len(doc)
    chunks: list[SemanticChunk] = []

    for start in range(0, total_pages, pages_per_chunk):
        end = min(start + pages_per_chunk - 1, total_pages - 1)
        text_parts = []
        for p in range(start, end + 1):
            page_text = doc[p].get_text().strip()
            if page_text:
                text_parts.append(page_text)

        actual_page_start = page_start + start
        actual_page_end = page_start + end

        # テキストの先頭200文字を説明に使用
        combined_text = " ".join(text_parts)
        snippet = combined_text[:200] if combined_text else "(空白ページ)"

        chunks.append(
            SemanticChunk(
                chunk_id=f"fallback_{start}",
                page_start=actual_page_start,
                page_end=actual_page_end,
                query=snippet[:100],
                description=f"[テキスト抽出フォールバック] p.{actual_page_start}-{actual_page_end}: {snippet}",
            )
        )

    doc.close()

    # 空の場合でも最低1チャンクを返す
    if not chunks:
        chunks.append(
            SemanticChunk(
                chunk_id="fallback_0",
                page_start=page_start,
                page_end=page_end,
                query="(内容なし)",
                description=f"[テキスト抽出フォールバック] p.{page_start}-{page_end}: (空白ページ)",
            )
        )

    return chunks


def _deduplicate_chunks(
    all_batch_chunks: list[list[SemanticChunk]],
    batches: list[dict],
    overlap: int = 2,
) -> list[SemanticChunk]:
    """オーバーラップ部分の重複チャンクを除去し、chunk_idを通し番号で振り直す。

    2番目以降のバッチについて、page_startがオーバーラップ領域内
    （バッチ開始ページ + overlap未満）のチャンクを除去する。

    Args:
        all_batch_chunks: バッチごとのチャンクリスト
        batches: バッチ情報のリスト（page_start必須）
        overlap: オーバーラップページ数
    """
    deduped: list[SemanticChunk] = []

    for i, chunks in enumerate(all_batch_chunks):
        if i == 0:
            deduped.extend(chunks)
        else:
            own_start = batches[i]["page_start"] + overlap
            for chunk in chunks:
                if chunk.page_start >= own_start:
                    deduped.append(chunk)

    # chunk_idを通し番号で振り直す
    for idx, chunk in enumerate(deduped, 1):
        chunk.chunk_id = f"chunk_{idx:03d}"

    return deduped


def build_document_index(
    batches: list[dict],
    overlap: int = 2,
) -> list[SemanticChunk]:
    """全バッチを並列処理してセマンティックチャンクのインデックスを構築。

    Args:
        batches: バッチ情報のリスト
        overlap: オーバーラップページ数（重複排除に使用）

    Returns:
        全チャンクのリスト（重複除去・ID振り直し済み）
    """
    all_batch_chunks: list[list[SemanticChunk] | None] = [None] * len(batches)

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_idx = {executor.submit(build_semantic_chunks, batch, i): i for i, batch in enumerate(batches)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            batch = batches[idx]
            try:
                result = future.result()
                all_batch_chunks[idx] = result.chunks
            except BadRequestError as e:
                if "Could not process PDF" in str(e):
                    logger.warning(
                        "バッチ %d (p.%d-%d) のPDF処理に失敗。テキスト抽出にフォールバック: %s",
                        idx,
                        batch["page_start"],
                        batch["page_end"],
                        e,
                    )
                    all_batch_chunks[idx] = _text_fallback_chunks(
                        batch["pdf_bytes"],
                        batch["page_start"],
                        batch["page_end"],
                    )
                else:
                    raise

    return _deduplicate_chunks(all_batch_chunks, batches, overlap)
