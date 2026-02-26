"""デモA: 汎用文書構造化エンジン — Streamlit UI"""

import sys
import json
import logging
import tempfile
import traceback
from pathlib import Path

# Streamlit Cloud ではプロジェクトルートが sys.path に含まれないため明示的に追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Streamlit Cloud のログに WARNING 以上を出力する
logging.basicConfig(level=logging.WARNING, format="%(name)s %(levelname)s: %(message)s")

import streamlit as st

from app.demo_a.converter import TextContent, ensure_pdf
from app.demo_a.pipeline import build_index, extract_with_schema
from app.demo_a.presets import get_preset, list_presets

# --- プリセット文書定義 ---
RESOURCES_BASE = Path(__file__).parent.parent.parent / "resources" / "PoC見積依頼_実際の業務資料"

PRESET_DOCUMENTS = {
    "Instructions to Bidders (Word)": RESOURCES_BASE / "受注前" / "テンダー書類" / "Instructions to Bidders_OCTG.docx",
    "Project Overview (Word)": RESOURCES_BASE / "受注前" / "テンダー書類" / "Project Overview_Mozambique.docx",
    "Exhibit D (Word)": RESOURCES_BASE / "受注前" / "テンダー書類" / "4.1-Exhibit D Comp and Paym_OCTG_All.docx",
    "Exhibit D - Large OD (Excel)": (
        RESOURCES_BASE / "受注前" / "テンダー書類" / "Large OD" / "Att 1-Exhibit D - OCTG Large OD.xlsx"
    ),
    "Exhibit D - Chrome (Excel)": (
        RESOURCES_BASE / "受注前" / "テンダー書類" / "Chrome" / "Att 1-Exhibit D - OCTG Cr.xlsx"
    ),
    "Base Contract (PDF, 230p)": (
        RESOURCES_BASE / "受注後" / "Input from customer & mill" / "PO" / "Base Contract_00008772-CTR109083 TEPRH AGUP Ph2 OCTG CRA CONTRACT Signed.pdf"
    ),
    "CallOff PO (PDF)": (
        RESOURCES_BASE / "受注後" / "Input from customer & mill" / "PO" / "CallOff 4300062653 - AGUP P2 - Sumitomo (FINAL).pdf"
    ),
}

# --- ロギング設定 ---
# StreamlitのUIにログを表示するためのハンドラ
class StreamlitLogHandler(logging.Handler):
    """ログをst.session_stateに蓄積するハンドラ。"""

    def emit(self, record: logging.LogRecord) -> None:
        if "log_messages" not in st.session_state:
            st.session_state.log_messages = []
        msg = self.format(record)
        st.session_state.log_messages.append(msg)


# app配下のロガーにハンドラを設定
_log_handler = StreamlitLogHandler()
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"))
_app_logger = logging.getLogger("app")
_app_logger.setLevel(logging.DEBUG)
if not any(isinstance(h, StreamlitLogHandler) for h in _app_logger.handlers):
    _app_logger.addHandler(_log_handler)

# --- ページ設定 ---
st.set_page_config(page_title="デモA: 汎用文書構造化エンジン", page_icon="📄", layout="wide")
st.title("基盤① 文書処理・構造化生成 デモ")

# --- セッション状態初期化 ---
for key, default in {
    "index_cache": None,  # (pdf_path, batches, chunk_index)
    "extraction_results": None,
    "current_file_id": None,  # ファイル識別キー
    "current_schema_key": None,  # スキーマ識別キー
    "uploaded_temp_path": None,  # アップロードファイルの一時保存パス
    "uploaded_file_id": None,  # アップロードファイルの識別キー（temp再作成判定用）
    "log_messages": [],  # 実行ログ
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


def _make_schema_key(fields: list[dict]) -> str:
    """スキーマのフィールド定義からキャッシュキーを生成する。"""
    parts = tuple((f.get("name", ""), f.get("type", ""), f.get("description", "")) for f in fields)
    return str(parts)


# ===== サイドバー =====
with st.sidebar:
    st.header("📄 文書選択")
    doc_source = st.radio("入力方法", ["プリセット文書", "アップロード"], horizontal=True)

    selected_file_path: Path | None = None
    file_id: str | None = None

    if doc_source == "プリセット文書":
        available_docs = {name: path for name, path in PRESET_DOCUMENTS.items() if path.exists()}
        if not available_docs:
            st.warning("プリセット文書が見つかりません。resources/ディレクトリを確認してください。")
        else:
            selected_doc_name = st.selectbox("文書を選択", list(available_docs.keys()))
            selected_file_path = available_docs[selected_doc_name]
            file_id = f"preset:{selected_file_path}"
            st.caption(f"形式: {selected_file_path.suffix.upper()}")
    else:
        uploaded_file = st.file_uploader(
            "ファイルをアップロード",
            type=["pdf", "docx", "xlsx", "xlsm", "pptx", "csv", "txt"],
        )
        if uploaded_file:
            file_id = f"upload:{uploaded_file.name}:{uploaded_file.size}"
            # ファイルが変わった場合のみ一時ファイルを作成（rerunごとのリークを防止）
            if st.session_state.uploaded_file_id != file_id:
                suffix = Path(uploaded_file.name).suffix
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp.write(uploaded_file.getvalue())
                tmp.close()
                st.session_state.uploaded_temp_path = tmp.name
                st.session_state.uploaded_file_id = file_id
            selected_file_path = Path(st.session_state.uploaded_temp_path)
            st.caption(f"形式: {Path(uploaded_file.name).suffix.upper()} / サイズ: {uploaded_file.size / 1024:.0f} KB")

    st.divider()
    st.header("📋 スキーマ選択")
    schema_mode = st.radio("定義方法", ["プリセット", "カスタム定義"], horizontal=True)

    field_definitions: list[dict] = []

    if schema_mode == "プリセット":
        presets = list_presets()
        preset_names = [p["name"] for p in presets]
        selected_preset_name = st.selectbox("プリセットを選択", preset_names)
        preset = get_preset(selected_preset_name)
        field_definitions = preset["fields"]
        st.caption(f"{len(field_definitions)} 項目")

        with st.expander("フィールド一覧"):
            for f in field_definitions:
                st.text(f"  {f['name']} ({f['type']}): {f['description']}")
    else:
        st.caption("抽出したい項目を定義してください")
        num_fields = st.number_input("フィールド数", min_value=1, max_value=20, value=3)
        for i in range(int(num_fields)):
            cols = st.columns([2, 1, 3])
            name = cols[0].text_input(f"名前 #{i + 1}", key=f"fname_{i}", value=f"field_{i + 1}")
            ftype = cols[1].selectbox(f"型 #{i + 1}", ["テキスト", "数値", "整数", "真偽"], key=f"ftype_{i}")
            desc = cols[2].text_input(f"説明 #{i + 1}", key=f"fdesc_{i}", value="")
            if name and desc:
                field_definitions.append({"name": name, "type": ftype, "description": desc})

    # --- キャッシュ無効化 ---
    schema_key = _make_schema_key(field_definitions)

    # ファイルが変わったらインデックスと抽出結果をクリア
    if file_id != st.session_state.current_file_id:
        st.session_state.index_cache = None
        st.session_state.extraction_results = None
        st.session_state.current_file_id = file_id

    # スキーマが変わったら抽出結果をクリア（インデックスは再利用可）
    if schema_key != st.session_state.current_schema_key:
        st.session_state.extraction_results = None
        st.session_state.current_schema_key = schema_key

    # 文書情報
    if st.session_state.index_cache:
        st.divider()
        st.header("📊 文書情報")
        _, batches, chunk_index = st.session_state.index_cache
        if len(batches) == 1:
            st.metric("ページ数", batches[0]["page_count"])
            st.caption("処理方式: 直接投入（100p以下）")
        else:
            total_pages = batches[-1]["page_end"]
            st.metric("ページ数", total_pages)
            st.metric("バッチ数", len(batches))
            if chunk_index:
                st.metric("チャンク数", len(chunk_index))
            st.caption("処理方式: セマンティックチャンク")

    # 実行ログ（サイドバー下部に常時表示）
    if st.session_state.log_messages:
        st.divider()
        st.header("📝 実行ログ")
        log_text = "\n".join(st.session_state.log_messages)
        st.code(log_text, language="text")
        if st.button("ログをクリア", use_container_width=True):
            st.session_state.log_messages = []
            st.rerun()


# ===== メインエリア =====

if selected_file_path and field_definitions:
    # --- フェーズ1: インデックス構築 ---
    if st.session_state.index_cache is None:
        st.subheader("フェーズ1: インデックス構築")

        with st.status("ファイルを処理中...", expanded=True) as status:
            # Step 1: PDF変換
            st.write("Step 1: ファイル受付 → PDF化")
            try:
                pdf_result = ensure_pdf(selected_file_path, output_dir=Path("output/converted"))
            except Exception as e:
                st.error(f"ファイル変換エラー: {e}")
                with st.expander("トレースバック（詳細）", expanded=True):
                    st.code(traceback.format_exc(), language="python")
                st.stop()

            if isinstance(pdf_result, TextContent):
                st.warning(
                    "テキストファイルは現在PDFパイプラインに対応していません。PDF/Word/Excelを使用してください。"
                )
                st.stop()

            st.write(f"  → PDF変換完了: {pdf_result.name}")

            # Step 2-3: バッチ分割 + チャンク生成
            st.write("Step 2-3: バッチ分割 + インデックス構築")
            try:
                pdf_path, batches, chunk_index = build_index(pdf_result)
            except Exception as e:
                st.error(f"インデックス構築エラー: {e}")
                with st.expander("トレースバック（詳細）", expanded=True):
                    st.code(traceback.format_exc(), language="python")
                st.stop()

            if len(batches) == 1:
                st.write(f"  → {batches[0]['page_count']}ページ（分割不要）")
            else:
                st.write(f"  → {len(batches)}バッチに分割")
                if chunk_index:
                    st.write(f"  → {len(chunk_index)}個のセマンティックチャンクを生成")

            st.session_state.index_cache = (pdf_path, batches, chunk_index)
            status.update(label="インデックス構築完了", state="complete", expanded=False)
    else:
        st.subheader("フェーズ1: インデックス構築")
        st.success("インデックス構築済み（キャッシュ利用）")

    # --- フェーズ2: 検索→抽出 ---
    st.subheader("フェーズ2: 検索 → 抽出")

    col1, col2 = st.columns([1, 4])
    run_extraction = col1.button("▶ 抽出実行", type="primary", use_container_width=True)

    if run_extraction:
        pdf_path, batches, chunk_index = st.session_state.index_cache
        # ログをクリア
        st.session_state.log_messages = []

        with st.status("抽出中...", expanded=True) as status:
            if chunk_index:
                st.write("Step 5: フィールドグルーピング")
                st.write("Step 6: チャンク検索")
                st.write("Step 7: コンテキスト統合")
            st.write("Step 8: 構造化抽出（Sonnet 4.6）")
            st.write(f"  フィールド数: {len(field_definitions)}")
            st.write(f"  フィールド: {', '.join(f['name'] for f in field_definitions)}")

            try:
                results = extract_with_schema(pdf_path, batches, chunk_index, field_definitions)
            except Exception as e:
                status.update(label="抽出失敗", state="error", expanded=True)
                st.error(f"抽出エラー: {e}")

                # トレースバック表示
                tb = traceback.format_exc()
                with st.expander("トレースバック（詳細）", expanded=True):
                    st.code(tb, language="python")

                # スキーマ情報表示
                from app.demo_a.schema_builder import build_extraction_schema

                try:
                    debug_model = build_extraction_schema(field_definitions)
                    schema_json = debug_model.model_json_schema()
                    with st.expander("送信スキーマ（JSON Schema）", expanded=True):
                        st.json(schema_json)
                except Exception:
                    pass

                st.info("詳細ログはサイドバーの「実行ログ」を確認してください。")

                st.stop()

            st.session_state.extraction_results = results
            status.update(label="抽出完了", state="complete", expanded=False)

    # --- 結果表示 ---
    if st.session_state.extraction_results:
        results = st.session_state.extraction_results

        st.subheader("抽出結果")

        # テーブル表示
        table_data = []
        for r in results:
            status_icon = "✅" if r["found_in_document"] else "❌"
            table_data.append(
                {
                    "状態": status_icon,
                    "項目": r["field_name"],
                    "説明": r["description"],
                    "抽出値": str(r["value"]) if r["value"] is not None else "—",
                    "ステータス": r["status"],
                }
            )

        st.dataframe(table_data, use_container_width=True, hide_index=True)

        # 統計
        found = sum(1 for r in results if r["found_in_document"])
        total = len(results)
        st.metric("抽出率", f"{found}/{total} ({found / total * 100:.0f}%)")

        # JSONダウンロード
        json_data = {r["field_name"]: r["value"] for r in results}
        st.download_button(
            "📥 JSONダウンロード",
            data=json.dumps(json_data, ensure_ascii=False, indent=2),
            file_name="extraction_result.json",
            mime="application/json",
        )

        # 詳細JSON（展開可能）
        with st.expander("生データ（JSON）"):
            st.json(results)

elif not selected_file_path:
    st.info("サイドバーから文書を選択してください。")
elif not field_definitions:
    st.info("サイドバーでスキーマを定義してください。")
