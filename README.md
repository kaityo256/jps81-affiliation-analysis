# 第81回日本物理学会年次大会・登壇者所属調査

## 本リポジトリについて

- 第81回日本物理学会年次大会の公開HTMLから登壇者の所属を講演単位で調べるスクリプトです。
- 公開されている第81回年次大会のプログラムを用いて、筆者が個人の立場で行った分析であり、非公開情報は使用していません。
- 略称から正式名称を推定しているため、結果が正確でない可能性があります。
- このリポジトリには集計結果のみが含まれ、個人情報を特定できる情報は含まれていません。
- 日本物理学会および筆者の所属機関による公式調査・公式見解ではありません。
- 本データについて、筆者は正確性を保証しません。ご自身の責任においてお使いください。

## 集計結果

集計結果は[こちら](output/report.md)です。

## 実行方法

Python 3.9以上、uv、Bash、wgetが必要です。

```sh
uv sync --locked
bash scripts/download.sh
.venv/bin/python scripts/inspect_program.py
.venv/bin/python scripts/parse_program.py
.venv/bin/python scripts/normalize_affiliations.py
.venv/bin/python scripts/build_report.py
.venv/bin/python -m unittest discover -s tests -v
```

依存関係は `pyproject.toml` と `uv.lock` で管理し、`.venv` に導入します。コマンドはリポジトリのルートから順番に実行します。
取得済みHTMLから再解析するときは、`parse_program.py` と `normalize_affiliations.py` の2コマンドを実行してください。解析・正規化スクリプトは通信しません。

## 出力

| ファイル                             | 内容                                                                 |
| ------------------------------------ | -------------------------------------------------------------------- |
| `output/presentations.jsonl`         | 講演ごとの著者・所属・上付き記号・登壇者判定・元HTML断片・掲載先一覧 |
| `output/areas/<area_id>.csv`         | 主領域ごとに講演1行、口頭・ポスターを統合                            |
| `output/unresolved_presenters.csv`   | 登壇者を決められない講演と根拠HTML                                   |
| `output/unresolved_affiliations.csv` | 未登録・曖昧・所属記号不一致等の件数と該当箇所                       |
| `output/unresolved_areas.csv`        | 主領域を決められない場合の保留先                                     |
| `output/audit.csv`                   | 取消、移動元、重複、内容補正、要確認の記録                           |
| `output/extraction_summary.md`       | 日本語の実行結果と制約                                               |
| `output/extraction_summary.json`     | 件数、取得日時、対応表のハッシュ等                                   |
| `output/report.md`                   | 全体・領域別の機関上位20位ランキング                                 |
| `output/ranking.json`                | ランキングの機械可読データ                                           |
| `output/structure_audit.json`        | ページ別の掲載枠数と構造検証候補                                     |

CSVはUTF-8（BOMなし）です。`presenter_affiliation_raw`、`affiliation_alias`、`affiliation_official` は対応順をそろえたJSON配列で、未確定値は `null` です。同じ正式機関の所属は1件に畳み、畳む前の原所属配列を `presenter_affiliation_all_raw` に残します。全部局の原文は `presentations.jsonl` にも保持します。

`status` は `resolved`、`unresolved_affiliation`、`unresolved_presenter` 等です。問題が複数あればセミコロンで併記します。`resolved` でも登壇者が筆頭著者による推定の場合があるため、必ず `presenter_detection` と併せて解釈してください。未解決講演を行ごと削除しません。

機関に対応付けられなかった表記には、調査未着手の表記や、複数機関・部局の境界が曖昧な表記が含まれます。これらは機関別集計に加算できません。海外機関には公式の原語名称を用いる場合があります。

## ライセンス

コードは[MIT License](LICENSE)で公開しています。
