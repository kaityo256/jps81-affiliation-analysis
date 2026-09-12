# 第81回日本物理学会年次大会・登壇者所属調査

公開HTMLから登壇者の所属を講演単位で調べるプロジェクトです。
対象・集計規則は [PLAN.md](PLAN.md)、作業時の実行規則は [AGENTS.md](AGENTS.md) を参照してください。

ランキング結果：[output/report.md](output/report.md)

本調査は、公開されている第81回年次大会のプログラムを用いて、筆者が個人の立場で行った分析です。日本物理学会および筆者の所属機関による公式調査・公式見解ではありません。学会の非公開情報は使用していません。

取得、登壇者抽出、所属の正規化、領域別CSV・未解決一覧、全体・領域別ランキングの生成を実装しています。大会前の取得結果は暫定版です。検索画面・日程別一覧との取得範囲の突合は未実装です。

## 環境構築と実行

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

## HTML取得と再現性

取得スクリプトは領域別一覧を取得し、口頭・ポスターのリンクだけを `data/source_urls.csv` に保存して順番に取得します。取得間隔は1秒、タイムアウトは30秒、最大試行回数は3回、再試行待機は最大5秒です。PDF・画像・展示リンクは取得しません。失敗URLがあれば終了コードを非ゼロにします。

`data/raw/manifest.jsonl` にURL、取得日時（UTC）、保存先、成功・失敗、SHA-256を追記します。再取得前のHTMLとマニフェストは `data/raw/history/` に保存します。公式プログラム自体は更新されるため、同じ取得手順でも内容が変わる場合があります。過去の取得内容は保存したHTMLとハッシュで確認してください。

構造検査と解析では、各対象ファイルの直近の取得結果とハッシュを検証します。`output/parse_manifest.json` に解析入力・出力のハッシュを保存し、正規化時に古い解析結果が混ざらないことも確認します。

## 出力

| ファイル | 内容 |
| --- | --- |
| `output/presentations.jsonl` | 講演ごとの著者・所属・上付き記号・登壇者判定・元HTML断片・掲載先一覧 |
| `output/areas/<area_id>.csv` | 主領域ごとに講演1行、口頭・ポスターを統合 |
| `output/unresolved_presenters.csv` | 登壇者を決められない講演と根拠HTML |
| `output/unresolved_affiliations.csv` | 未登録・曖昧・所属記号不一致等の件数と該当講演番号 |
| `output/unresolved_areas.csv` | 主領域を決められない場合の保留先 |
| `output/audit.csv` | 取消、移動元、重複、番号補正、要確認の記録 |
| `output/extraction_summary.md` | 日本語の実行結果と制約 |
| `output/extraction_summary.json` | 件数、取得日時、対応表のハッシュ等 |
| `output/report.md` | 全体・領域別の機関上位20位ランキング |
| `output/ranking.json` | ランキングの機械可読データ |
| `output/structure_audit.json` | ページ別の掲載枠数と構造検証候補 |

CSVはUTF-8（BOMなし）です。`presenter_affiliation_raw`、`affiliation_alias`、`affiliation_official` は対応順をそろえたJSON配列で、未確定値は `null` です。同じ正式機関の所属は1件に畳み、畳む前の原所属配列を `presenter_affiliation_all_raw` に残します。全部局の原文は `presentations.jsonl` にも保持します。

`status` は `resolved`、`unresolved_affiliation`、`unresolved_presenter` 等です。問題が複数あればセミコロンで併記します。`resolved` でも登壇者が筆頭著者による推定の場合があるため、必ず `presenter_detection` と併せて解釈してください。未解決講演を行ごと削除しません。

機関に対応付けられなかった表記には、調査未着手の表記、複数機関や部局の境界が曖昧な表記、無所属・自宅・N/A等も含まれます。これらは機関別集計に加算できません。海外機関には公式の原語名称を用いる場合があります。

## 登壇者・合同講演・番号の扱い

「○」「◯」を優先し、明示がないときだけ筆頭著者を推定します。複数マークや解釈できない所属記号は未解決にします。上付き `A, B` と `A-C` を所属記号として解釈し、研究所名中の `SKCM²` 等と区別します。共同研究グループの付記がある場合は、個人名が1人でも単著と断定しません。

主領域はセッションの領域表示の先頭で決めます。講演番号範囲や前半・後半の条件付き合同表示も解釈し、合同先を残します。同一番号の講演は統合しますが、内容が一致しない場合は未解決にします。

通常はセッション番号とHTMLの `ol start` / `li value` に基づく表示番号を使い、HTML内のPDFリンクの番号と照合します。PDF自体は取得しません。確認できた例外は [data/presentation_overrides.csv](data/presentation_overrides.csv) に根拠URL・元HTMLのハッシュとともに記録しています。

- `14pL1225`：一部の合同ページで取消枠が欠落して表示番号がずれるため、計算物理ページおよび各講演のPDFリンクと照合して補正。
- `17aL1214-08`：元枠の移動表示と移動先のPDFリンクを照合し、移動先 `16pL1214-14` を `scheduled_presentation_id`、元番号を `presentation_id` として保持。

対象HTMLのハッシュが変わった場合は、番号補正を自動適用せずエラーにします。再取得後は変更内容を確認し、補正表を更新・削除してから再解析してください。登録番号は対象HTMLに見つからないため空欄です。

## 所属対応表の追加

1. `output/unresolved_affiliations.csv` の講演番号から、`presentations.jsonl` と元HTMLを確認します。所属記号不一致は機関名の対応表で補いません。
2. 公式機関サイト等で正式名称と所属部局を確認し、`data/affiliation_aliases.csv` に `alias,official_name,source_url,note` を追加します。`note` に確認日と判断根拠を記します。
3. 採用する原表記と略称の組を `data/affiliation_forms.csv` に追加します。照合は完全一致であり、似た表記や前方一致からの推測はしません。
4. ローカルHTMLから再解析・再正規化し、未解決一覧とテストを確認します。

同じ略称が複数機関を指す場合は未解決にします。大学と共同利用機関、共同運営施設と運営法人などを一括で統合しません。例として、総研大と核融合研は別機関に対応付け、運営主体が特定できない `J-PARC` 単独表記は保留しています。

取得HTMLと氏名・題名を含む出力はGit管理対象外です。対応表、スクリプト、氏名のない実行サマリーはGit管理可能です。公開の必要がある場合は、PLAN.mdに従って公式サイトの利用条件と公開範囲を確認してください。
