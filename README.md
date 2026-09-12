# 第81回日本物理学会年次大会・登壇者所属調査

## 本リポジトリについて

- 第81回日本物理学会年次大会の公開HTMLから登壇者の所属を講演単位で調べるスクリプトです。
- 公開されている第81回年次大会のプログラムを用いて、筆者が個人の立場で行った分析であり、非公開情報は使用していません。
- 略称から正式名称を推定しているため、結果が正確でない可能性があります。
- このリポジトリには集計結果のみが含まれ、個人情報を特定できる情報は含まれていません。
- 日本物理学会および筆者の所属機関による公式調査・公式見解ではありません。

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

## 登壇者・合同講演・番号の扱い

「○」「◯」を優先し、明示がないときだけ筆頭著者を推定します。複数マークや解釈できない所属記号は未解決にします。上付きの英字記号を所属記号として解釈し、機関名中の記号と区別します。共同研究グループの付記がある場合は、個人名が1人でも単著と断定しません。

主領域はセッションの領域表示の先頭で決めます。掲載範囲や前半・後半の条件付き合同表示も解釈し、合同先を残します。同一項目は統合しますが、内容が一致しない場合は未解決にします。

通常はセッションのHTML構造と表示順に基づいて掲載内容を識別します。合同表示や掲載内容の不整合がある場合は、根拠を監査記録に残して未解決として扱います。PDF自体は取得しません。対象HTMLのハッシュが変わった場合は、補正を自動適用せずエラーにします。再取得後は変更内容を確認してから再解析してください。

## 所属対応表の追加

1. 未解決所属一覧から対象箇所を確認し、`presentations.jsonl` と元HTMLを参照します。所属記号不一致は機関名の対応表で補いません。
2. 公式機関サイト等で正式名称と所属部局を確認し、`data/affiliation_aliases.csv` に `alias,official_name,source_url,note` を追加します。`note` に確認日と判断根拠を記します。
3. 採用する原表記と略称の組を `data/affiliation_forms.csv` に追加します。照合は完全一致であり、似た表記や前方一致からの推測はしません。
4. ローカルHTMLから再解析・再正規化し、未解決一覧とテストを確認します。

同じ略称が複数機関を指す場合は未解決にします。大学、研究機関、共同利用施設、企業など、法人や運営主体が異なる機関を一括で統合しません。

取得HTMLと氏名・題名を含む出力はGit管理対象外です。対応表、スクリプト、氏名のない実行サマリーはGit管理可能です。公開の必要がある場合は、PLAN.mdに従って公式サイトの利用条件と公開範囲を確認してください。

## ライセンス

コードは[MIT License](LICENSE)で公開しています。
