"""根拠付きの確定済み対応表だけを適用する。通信・推測による追加はしない。"""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from parse_program import read_csv, write_csv, verified_sources, presentation_sort_key

FIELDS = ['presentation_id', 'registration_id', 'title', 'area_id', 'area_name', 'joint_areas',
          'format', 'lecture_type', 'presenter', 'presenter_detection', 'presenter_affiliation_raw',
          'affiliation_alias', 'affiliation_official', 'status', 'source_url',
          'scheduled_presentation_id', 'session_area_text', 'source_urls', 'reasons',
          'presenter_affiliation_all_raw']


class AliasTable:
    def __init__(self, alias_path='data/affiliation_aliases.csv', form_path='data/affiliation_forms.csv'):
        self.aliases = defaultdict(set)
        for row in read_csv(alias_path):
            if not row['source_url'].startswith(('https://', 'http://')) or not row['official_name']:
                raise ValueError('機関名と根拠URLが必須: ' + row['alias'])
            self.aliases[row['alias']].add(row['official_name'])
        self.forms = defaultdict(set)
        for row in read_csv(form_path):
            if row['alias'] not in self.aliases:
                raise ValueError('未登録の機関略称: ' + row['alias'])
            self.forms[row['raw_affiliation']].add(row['alias'])

    def resolve(self, raw):
        if raw in {'無所属', '所属なし', 'N/A', '自宅'}:
            return None, None, 'no_institution_declared'
        candidates = self.forms.get(raw, set())
        if not candidates:
            return None, None, 'unregistered_form'
        if len(candidates) != 1:
            return None, None, 'ambiguous_form'
        alias = next(iter(candidates))
        names = self.aliases[alias]
        if len(names) != 1:
            return alias, None, 'ambiguous_alias'
        return alias, next(iter(names)), ''


def normalize_row(row, table):
    raw = row['presenter_affiliation_raw']
    resolved = [table.resolve(value) for value in raw]
    reasons = list(row['reasons'])
    statuses = []
    if row['presenter_detection'] == 'unresolved':
        statuses.append('unresolved_presenter')
    if not row['area_id']:
        statuses.append('unresolved_area')
    if any(x.startswith(('presentation_id_mismatch', 'conflicting_')) for x in reasons):
        statuses.append('unresolved_presentation')
        resolved = [(alias, None, 'unresolved_presentation') for alias, name, reason in resolved]
    if not raw or any(name is None for alias, name, reason in resolved) or any(
            r.startswith('unmatched_affiliation_symbol') for r in reasons):
        statuses.append('unresolved_affiliation')
    retained, seen = [], set()
    for index, (alias, name, reason) in enumerate(resolved):
        if name is not None and name in seen:
            continue
        seen.add(name)
        retained.append(index)
    return dict(row, presenter_affiliation_all_raw=raw,
                presenter_affiliation_raw=[raw[i] for i in retained],
                affiliation_alias=[resolved[i][0] for i in retained],
                affiliation_official=[resolved[i][1] for i in retained],
                affiliation_reasons=[resolved[i][2] for i in retained],
                status=';'.join(statuses) or 'resolved')


def main():
    sources = verified_sources()
    metadata = json.loads(Path('output/parse_manifest.json').read_text(encoding='utf-8'))
    for filename, digest in metadata['inputs'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise ValueError('解析入力が変わりました。parse_program.pyを再実行してください: ' + filename)
    table = AliasTable()
    rows = [normalize_row(json.loads(line), table) for line in
            Path('output/presentations.jsonl').read_text(encoding='utf-8').splitlines()]
    ids = [r['presentation_id'] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('重複する講演番号があります')
    area_names = {}
    for source in sources:
        area_names.setdefault(source['area_id'], source['area_name'])
    area_names['cross_area'] = '領域横断（80周年サテライト）'
    areas = defaultdict(list)
    unresolved_affs = defaultdict(set)
    unresolved_people = []
    unresolved_areas = []
    for row in rows:
        row['area_name'] = area_names.get(row['area_id'], '')
        if row['presenter_detection'] == 'unresolved':
            unresolved_people.append(dict(row, reason=';'.join(row['reasons'])))
        if not row['area_id']:
            unresolved_areas.append(row)
        else:
            areas[row['area_id']].append(row)
        for raw, alias, official, reason in zip(row['presenter_affiliation_raw'], row['affiliation_alias'],
                                              row['affiliation_official'], row['affiliation_reasons']):
            if official is None:
                unresolved_affs[raw, alias, reason].add(row['presentation_id'])
        for reason in row['reasons']:
            if reason.startswith('unmatched_affiliation_symbol'):
                # 対応する原所属を特定できないので空文字で記録し、講演番号から根拠に戻る。
                unresolved_affs['', '', reason].add(row['presentation_id'])
        if not row['presenter_affiliation_raw'] and row['presenter_detection'] == 'unresolved':
            unresolved_affs['', '', 'unresolved_presenter'].add(row['presentation_id'])
    json_fields = ['joint_areas', 'presenter_affiliation_raw', 'affiliation_alias', 'affiliation_official',
                   'source_urls', 'reasons', 'presenter_affiliation_all_raw']
    def encoded(row):
        return {k: json.dumps(v, ensure_ascii=False) if k in json_fields else v for k, v in row.items()}
    for area in area_names:
        write_csv(f'output/areas/{area}.csv', [encoded(r) for r in sorted(areas[area], key=presentation_sort_key)], FIELDS)
    write_csv('output/unresolved_presenters.csv', unresolved_people,
              ['presentation_id', 'reason', 'authors_html', 'affiliations_html', 'source_url'])
    write_csv('output/unresolved_areas.csv', [encoded(r) for r in unresolved_areas], FIELDS)
    unresolved_rows = [dict(raw_affiliation=raw, alias=alias, count=len(pids),
                            example_presentation_id=sorted(pids)[0], reason=reason,
                            presentation_ids=json.dumps(sorted(pids), ensure_ascii=False))
                       for (raw, alias, reason), pids in unresolved_affs.items()]
    write_csv('output/unresolved_affiliations.csv',
              sorted(unresolved_rows, key=lambda r:(-r['count'], r['raw_affiliation'], r['reason'])),
              ['raw_affiliation', 'alias', 'count', 'example_presentation_id', 'reason', 'presentation_ids'])
    assert sum(len(v) for v in areas.values()) + len(unresolved_areas) == len(rows)
    audit = read_csv('output/audit.csv')
    summary = dict(edition='暫定版', source_pages=len(sources), target_presentations=len(rows),
                   area_counts={k:len(v) for k,v in sorted(areas.items())},
                   presenter_detection=dict(Counter(r['presenter_detection'] for r in rows)),
                   status_counts=dict(Counter(r['status'] for r in rows)),
                   fully_resolved=sum(r['status']=='resolved' for r in rows),
                   unresolved_affiliation_presentations=sum('unresolved_affiliation' in r['status'] for r in rows),
                   unresolved_affiliation_forms=len(unresolved_rows),
                   confirmed_institutions=len({n for r in rows for n in r['affiliation_official'] if n}),
                   excluded_cancelled=len({r['presentation_id'] for r in audit if r['reason']=='cancelled'}),
                   excluded_moved_placeholders=len({r['presentation_id'] for r in audit if r['reason']=='moved_placeholder'}),
                   duplicate_listings=sum(r['reason']=='duplicate' for r in audit),
                   coverage_check='領域別一覧31ページのみ確認済み。検索・日程別一覧との突合は未実施。',
                   inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                           [Path('data/affiliation_aliases.csv'),Path('data/affiliation_forms.csv'),Path('output/presentations.jsonl')]})
    latest = {}
    for line in Path('data/raw/manifest.jsonl').read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        latest[record['source_url']] = record
    times = sorted(latest[s['source_url']]['retrieved_at'] for s in sources)
    summary['source_retrieved_at_utc'] = [times[0], times[-1]]
    summary['parsed_at_utc'] = metadata['parsed_at']
    Path('output/extraction_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    text = f'''# 登壇者抽出・所属正規化の実行結果（暫定版）

第81回日本物理学会年次大会（2026年）の[領域別プログラム](https://jps2026a.gakkai-web.net/data/html/program.html)を解析しました。
対象HTMLの取得日時は {times[0]} ～ {times[-1]}（UTC）です。解析対象は {len(sources)} ページです。

| 項目 | 件数 |
| --- | ---: |
| 重複排除後の対象講演 | {len(rows)} |
| 登壇者の明示 | {summary['presenter_detection'].get('explicit', 0)} |
| 筆頭著者による推定 | {summary['presenter_detection'].get('inferred_first_author', 0)} |
| 単著 | {summary['presenter_detection'].get('single_author', 0)} |
| 登壇者未解決 | {summary['presenter_detection'].get('unresolved', 0)} |
| 全所属の正規化済み講演 | {summary['fully_resolved']} |
| 所属未解決を含む講演 | {summary['unresolved_affiliation_presentations']} |
| 正規化した機関 | {summary['confirmed_institutions']} |
| 除外した取消講演 | {summary['excluded_cancelled']} |
| 除外した移動元の空枠 | {summary['excluded_moved_placeholders']} |

集計単位は講演です。筆頭著者による推定は検証済みの登壇者ではありません。
未解決には対応表未登録、所属記号の欠落、無所属・自宅等の機関名がない表記を含みます。
未登録の全表記について公式名称の調査が完了したわけではありません。推測で機関を割り当てていません。

全講演は主領域の [CSV](areas/) に1行ずつ保存しています。正式機関名の重複を畳み、畳む前の原所属は `presenter_affiliation_all_raw` と `presentations.jsonl` に保持しています。
[未解決所属一覧](unresolved_affiliations.csv)、[未解決登壇者一覧](unresolved_presenters.csv)、[監査記録](audit.csv)から根拠を確認できます。
機関名の根拠URLは [対応表](../data/affiliation_aliases.csv) に保存しています。

{summary['coverage_check']} ランキング・最終報告書の生成は未実装です。
'''
    Path('output/extraction_summary.md').write_text(text, encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('inputs','area_counts')},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
