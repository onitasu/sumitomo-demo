"""Step 2: PDF物理バッチ分割（オーバーラップ付き）"""

from pathlib import Path

import pymupdf


def load_and_split(
    pdf_path: Path,
    batch_size: int = 20,
    overlap: int = 2,
) -> list[dict]:
    """PDFを読み込み、必要に応じてオーバーラップ付きバッチに分割。

    100ページ以下の文書は分割不要（フェーズ2でそのまま丸ごとSonnetに投入）。
    100ページ超の文書は batch_size ページずつに物理分割し、
    隣接バッチ間で overlap ページのオーバーラップを持たせる。

    Args:
        pdf_path: PDFファイルパス
        batch_size: 1バッチあたりのページ数（デフォルト20）
        overlap: 隣接バッチ間のオーバーラップページ数（デフォルト2）

    Returns:
        list of {"id": str, "label": str, "pdf_bytes": bytes,
                 "page_start": int, "page_end": int, "page_count": int}
    """
    doc = pymupdf.open(pdf_path)
    total = len(doc)

    if total <= 100:
        pdf_bytes = pdf_path.read_bytes()
        doc.close()
        return [
            {
                "id": "full_document",
                "label": f"全文 ({total}ページ)",
                "pdf_bytes": pdf_bytes,
                "page_start": 1,
                "page_end": total,
                "page_count": total,
            }
        ]

    stride = batch_size - overlap
    batches = []
    for start in range(0, total, stride):
        end = min(start + batch_size - 1, total - 1)
        sub_doc = pymupdf.open()
        sub_doc.insert_pdf(doc, from_page=start, to_page=end)
        batches.append(
            {
                "id": f"batch_p{start + 1:03d}_{end + 1:03d}",
                "label": f"p.{start + 1}–{end + 1}",
                "pdf_bytes": sub_doc.tobytes(),
                "page_start": start + 1,
                "page_end": end + 1,
                "page_count": end - start + 1,
            }
        )
        sub_doc.close()
        if end == total - 1:
            break

    doc.close()
    return batches
