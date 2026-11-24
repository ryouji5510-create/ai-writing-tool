"""危険パターンの候補を ファイル:行 で列挙する(誤検知を含む。判断は人間/Claudeが行う)。
使い方: python scan.py <対象フォルダ>
"""
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".claude"}
# (重大度の目安, 説明, 正規表現)
RULES = [
    ("高", "APIキーらしき文字列の直書き", r"AIza[0-9A-Za-z_\-]{20,}"),
    ("高", "キー/シークレットの代入(直書きの疑い)", r"(?i)(api[_-]?key|secret|token|password)\s*=\s*[\"'][^\"']{8,}[\"']"),
    ("高", "eval/exec", r"\b(eval|exec)\s*\("),
    ("高", "シェル実行", r"\b(os\.system|subprocess\.\w+)\s*\("),
    ("高", "危険なデシリアライズ", r"\b(pickle\.loads?|yaml\.load)\s*\("),
    ("中", "HTML非エスケープ描画(XSS)", r"unsafe_allow_html\s*=\s*True|components\.html|st\.html\("),
    ("中", "キーのprint/log/表示", r"(?i)(print|logging\.\w+|st\.(write|code|text|error|info))\s*\(.*(api_?key|\bkey\b)"),
    ("中", "共有キャッシュ(別ユーザーと共有され得る)", r"st\.cache_(resource|data)"),
    ("中", "環境変数への書き込み", r"os\.environ\[.*\]\s*="),
    ("中", "例外内容をそのまま表示", r"st\.(error|warning)\(.*(\{\s*e\s*\}|str\(e\))"),
    ("中", "XSRF/CORS保護の無効化", r"(?i)enable(Xsrf|CORS)\w*\s*=\s*false"),
    ("低", "全IF公開設定", r"(?i)address\s*=\s*[\"']?0\.0\.0\.0"),
    ("低", "ファイルアップロード", r"file_uploader"),
    ("低", "グローバル可変状態", r"^[A-Za-z_]\w*\s*=\s*(\[\]|\{\}|dict\(\)|list\(\))\s*$"),
]


def main(root: Path) -> None:
    hits = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or SKIP_DIRS & set(p.parts):
            continue
        if p.suffix not in {".py", ".toml", ".txt", ".yaml", ".yml", ".json", ".env", ""} and p.name != "Dockerfile":
            continue
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for no, line in enumerate(lines, 1):
            for sev, desc, pat in RULES:
                if re.search(pat, line):
                    hits += 1
                    shown = line.strip()[:120]
                    print(f"[{sev}] {p.relative_to(root)}:{no}  {desc}\n      {shown}")
    # .env の存在と .gitignore(値は表示しない)
    envs = [f.name for f in root.glob(".env*") if f.is_file()]
    gi = root / ".gitignore"
    ignored = gi.exists() and ".env" in gi.read_text(encoding="utf-8", errors="replace")
    print(f"\n[情報] .env系ファイル: {envs or 'なし'} / .gitignoreに.envあり: {ignored}  (値は表示しません)")
    print(f"[情報] 候補 {hits} 件。誤検知を含むので、各ヒットの前後を読んで判断してください。")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve())
