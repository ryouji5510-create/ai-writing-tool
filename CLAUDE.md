# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 概要

個人用のAIライティングツール。Python + Streamlit + Gemini API (`google-genai` SDK)。DB・認証は意図的に持たない。UIとコメントは日本語。テスト・linter未導入。

## コマンド

```
pip install -r requirements.txt
python -m streamlit run app.py          # http://localhost:8501
```

APIキーは利用者が各自取得し、サイドバーのパスワード欄(`st.session_state["api_key"]`)に入力して使う仕様。環境変数・`.env` は読まない(サーバー側にキーを持たない)。

## アーキテクチャ

全ロジックは単一ファイル [app.py](app.py)。

- `PAGES` 辞書(表示名 → `page_*` 関数)をサイドバーの `st.radio` で切り替える。機能追加は `page_*` 関数を作って `PAGES` に登録するだけ。
- 各 `page_*` は入力ウィジェットからプロンプト文字列を組み立て、共通の `run(label, prompt)` に渡す。`run` が ストリーミング生成 → 履歴(`st.session_state["history"]`)保存 → `show_result`(表示・コピー用・txt保存)までを担当する。
- `stream_generate` は `generate_content_stream` を使い、サイドバーの `model` / `temperature`(session_state)を参照する。システムプロンプト `BASE_SYSTEM` は「本文のみ出力、前置き禁止」。
- 履歴はセッション内のみ(リロードで消える)。永続化はしない方針。

## 注意点(ハマりどころ)

- Geminiのモデルは世代交代が早く、旧モデル(例: `gemini-2.5-flash`)は新規ユーザーに対し404で終了する。そのためモデル一覧は `fetch_models` で APIキーから動的取得し(画像・音声系は除外)、`MODELS` のハードコード値は取得失敗時のフォールバックにすぎない。モデル名を固定で書き足す方向に戻さないこと。
- 最新モデルは 503(高負荷)になることがあり、その間SDKがリトライして長時間止まって見える。`gemini-3.5-flash` で動作確認済み。
- `genai.Client(...)` は変数に保持すること。一時オブジェクトのままイテレートするとGCで closed になり `Cannot send a request, as the client has been closed.` が出る(`fetch_models` で踏んだ)。
- Windows環境。Bashから日本語を含むPythonを実行する際は `PYTHONIOENCODING=utf-8` を付けないと文字化けする。
