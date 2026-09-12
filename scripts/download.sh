#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/raw
python=.venv/bin/python
if [[ ! -x "$python" ]]; then
    echo '先に uv sync を実行してください。' >&2
    exit 1
fi
# 再取得前のHTML・マニフェストを丸ごと保存し、前回との差分検証に備える。
if [[ -f data/raw/manifest.jsonl ]]; then
    archive="data/raw/history/$(date -u +%Y%m%dT%H%M%S)-$$"
    mkdir -p "$archive"
    cp data/raw/*.html data/raw/manifest.jsonl "$archive/"
fi
# URL・保存先・取得条件を固定し、試行用取得もこの入口を利用する。
download() {
    local url="$1" destination="$2"
    sleep 1
    if wget --timeout=30 --tries=3 --waitretry=5 --output-document="${destination}.part" "$url"; then
        mv "${destination}.part" "$destination"
        "$python" scripts/source_manifest.py record "$url" "$destination" ok
    else
        "$python" scripts/source_manifest.py record "$url" "$destination" failed
        return 1
    fi
}
download https://jps2026a.gakkai-web.net/data/html/program.html data/raw/program.html
"$python" scripts/source_manifest.py discover > data/raw/download_queue.tsv
failures=0
while IFS=$'\t' read -r url destination; do
    if ! download "$url" "$destination"; then
        failures=$((failures + 1))
    fi
done < data/raw/download_queue.tsv
if (( failures > 0 )); then
    echo "取得失敗: ${failures}件。data/raw/manifest.jsonlを確認してください。" >&2
    exit 1
fi
