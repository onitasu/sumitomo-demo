"""Claude API共通クライアント（デモA用）"""

import base64
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

# .envからAPIキーを読み込み
load_dotenv()

MODEL = "claude-sonnet-4-6"


class DemoAClient:
    """デモA用のClaude APIクライアント。

    全LLM呼び出しで messages.parse() + output_format を使用し、
    Structured Output でPydanticモデルを返す。
    """

    def __init__(self, api_key: str | None = None) -> None:
        if api_key is None:
            api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
        self.client = Anthropic(api_key=api_key, max_retries=5)

    def structured_extract(
        self,
        messages: list[dict],
        output_format: type[BaseModel],
        model: str = MODEL,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Structured OutputでPydanticモデルを返す。

        Args:
            messages: Claude API messagesパラメータ
            output_format: 出力Pydanticモデルクラス
            model: モデルID
            temperature: 温度（デフォルト0）
            max_tokens: 最大トークン数

        Returns:
            パースされたPydanticモデルインスタンス
        """
        response = self.client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
            output_format=output_format,
        )
        return response.parsed_output

    @staticmethod
    def build_pdf_content_block(pdf_bytes: bytes) -> dict:
        """PDFバイト列からClaude APIのdocumentコンテンツブロックを構築する。"""
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.b64encode(pdf_bytes).decode(),
            },
        }


# シングルトンインスタンス
_client: DemoAClient | None = None


def get_client() -> DemoAClient:
    """グローバルクライアントインスタンスを取得する。"""
    global _client
    if _client is None:
        _client = DemoAClient()
    return _client


def set_client(client: DemoAClient) -> None:
    """テスト用: クライアントを差し替える。"""
    global _client
    _client = client
