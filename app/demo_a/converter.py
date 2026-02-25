"""Step 1: ファイル→PDF変換"""

import io
import subprocess
from dataclasses import dataclass
from pathlib import Path

import msoffcrypto


@dataclass
class TextContent:
    """PDF変換せずテキストとして扱うコンテンツ（CSV/TXT等）。"""

    text: str


# LibreOfficeで変換可能な拡張子
_LIBREOFFICE_EXTENSIONS = {".docx", ".xlsx", ".xlsm", ".pptx", ".xls"}

# テキストとして直接扱う拡張子
_TEXT_EXTENSIONS = {".csv", ".txt", ".md", ".tsv"}

# パスワード保護の可能性がある拡張子
_ENCRYPTED_EXTENSIONS = {".xlsx", ".xlsm"}


def ensure_pdf(
    file_path: Path,
    output_dir: Path | None = None,
    password: str = "scaiagent",
) -> Path | TextContent:
    """あらゆるファイル形式をPDFに変換。PDFはそのまま返す。

    Args:
        file_path: 入力ファイルパス
        output_dir: PDF出力先ディレクトリ（Noneの場合はoutput/converted）
        password: パスワード保護Excelの復号パスワード

    Returns:
        PDFファイルパス、またはTextContent（CSV/TXT等）
    """
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return file_path

    if suffix in _TEXT_EXTENSIONS:
        text = file_path.read_text(encoding="utf-8")
        return TextContent(text=text)

    if suffix in _LIBREOFFICE_EXTENSIONS:
        # パスワード保護Excelの復号
        actual_path = file_path
        if suffix in _ENCRYPTED_EXTENSIONS:
            actual_path = _decrypt_if_needed(file_path, password=password)

        # LibreOfficeでPDF変換
        if output_dir is None:
            output_dir = Path("output/converted")
        output_dir.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(actual_path),
            ],
            check=True,
            capture_output=True,
        )
        return output_dir / f"{actual_path.stem}.pdf"

    raise ValueError(f"未対応の形式: {suffix}")


def _decrypt_if_needed(path: Path, password: str = "scaiagent") -> Path:
    """パスワード保護Excelの復号。保護されていなければそのまま返す。"""
    with open(path, "rb") as f:
        office_file = msoffcrypto.OfficeFile(f)
        if office_file.is_encrypted():
            decrypted = io.BytesIO()
            office_file.load_key(password=password)
            office_file.decrypt(decrypted)
            out_path = path.parent / f"{path.stem}_decrypted{path.suffix}"
            out_path.write_bytes(decrypted.getvalue())
            return out_path
    return path
