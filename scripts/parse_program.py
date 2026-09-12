"""公開HTMLをローカルで解析し、講演・著者・所属の根拠をJSONLに保存する。"""
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from collections import Counter, defaultdict
from pathlib import Path

from bs4 import BeautifulSoup, Tag

MARKS = '○◯'
AREA_NAMES = {
    '素粒子論領域': 'particle_theory', '素粒子実験領域': 'particle_experiment',
    '理論核物理領域': 'nuclear_theory', '実験核物理領域': 'nuclear_experiment',
    '宇宙線・宇宙物理領域': 'cosmic_physics', 'ビーム物理領域': 'beam_physics',
    '計算物理領域': 'computational_physics', '計算物理領': 'computational_physics',
    '領域横断': 'cross_area', **{f'領域{i}': f'area{i}' for i in range(1, 14)},
}
AREA_RE = re.compile('|'.join(sorted(AREA_NAMES, key=len, reverse=True)))


def read_csv(path):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def compact(text):
    return re.sub(r'\s+', ' ', text).strip()


def presentation_sort_key(row):
    session, number = row['presentation_id'].rsplit('-', 1)
    return session, int(number)


def split_dom(field):
    """上付き記号内と括弧内のカンマを保護し、DOM片のまま分割。"""
    parts, current, depth = [], [], 0
    for node in field.children:
        if isinstance(node, Tag):
            current.append(str(node))
            continue
        text = ''
        for char in str(node):
            if char in '(（[':
                depth += 1
            elif char in ')）]':
                depth = max(0, depth - 1)
            if char in ',，' and depth == 0:
                current.append(text)
                parts.append(''.join(current).strip())
                current, text = [], ''
            else:
                text += char
        current.append(text)
    parts.append(''.join(current).strip())
    return [BeautifulSoup(p, 'html.parser') for p in parts if p]


def decode_person(fragment):
    symbols, invalid = [], []
    marked = sum(fragment.get_text().count(m) for m in MARKS)
    for sup in fragment.find_all('sup'):
        value = sup.get_text(strip=True)
        if value in MARKS:
            sup.decompose()
        elif re.fullmatch(r'[A-Za-z]+(?:\s*,\s*[A-Za-z]+)*', value):
            symbols.extend(re.split(r'\s*,\s*', value))
            sup.decompose()
        elif re.fullmatch(r'[A-Z]-[A-Z]', value) and value[0] <= value[2]:
            symbols.extend(chr(i) for i in range(ord(value[0]), ord(value[2]) + 1))
            sup.decompose()
        else:
            invalid.append(value)
            sup.decompose()
    name = compact(fragment.get_text()).strip(MARKS + ' ')
    return dict(name=name, symbols=symbols or [''], marker_count=marked,
                invalid_symbols=invalid)


def parse_people(field):
    people, groups = [], []
    for part in split_dom(field):
        person = decode_person(part)
        # 共同研究グループの表記は著者の人数に含めず、原文は別途保存する。
        if re.match(r'^(?:他|for\b|on behalf\b)', person['name'], re.I):
            groups.append(person['name'])
            continue
        person['name'] = re.split(r'\s+for\s+|\s+on behalf of\s+', person['name'], flags=re.I)[0]
        people.append(person)
    return people, groups


def parse_affiliations(field):
    result, unmarked, pending = [], [], []
    for part in split_dom(field):
        symbols = []
        # 機関名中のSKCM^2等を所属記号として扱わない。
        for sup in part.find_all('sup'):
            value = sup.get_text(strip=True)
            if re.fullmatch(r'[A-Za-z]+(?:\s*,\s*[A-Za-z]+)*', value):
                symbols.extend(re.split(r'\s*,\s*', value))
                sup.decompose()
        raw = compact(part.get_text())
        if symbols:
            # 英文の部局・機関名中のカンマは、直後の上付き記号まで同じ所属。
            # 先頭が大学名等なら、その先頭ブロックは記号なし所属として残す。
            if pending:
                english_department = re.match(
                    r'^(?:Dept\b|Department\b|Faculty\b|Fac\b|School\b|Sch\b|Graduate\b|Grad\b|Inst\b|Institute\b|Lab\b|Laboratory\b|Center\b|Centre\b|Div\b)', pending[0])
                english_continuation = result and all(not re.search(r'[ぁ-んァ-ン一-龯]', p) for p in pending)
                # 最初の無記号所属も英文部局から始まる場合がある。
                # 例: Dept. Phys., Nagoya Univ., Grad. Sch. Eng., Nagoya Univ.^A
                if english_department and not result and re.search(r'Univ|University|IIT\b|QPEC\b', raw):
                    end = next((i for i, p in enumerate(pending) if re.search(r'Univ|University', p)), None)
                    if end is not None:
                        unmarked.extend(pending[:end + 1])
                        pending = pending[end + 1:]
                if english_department or english_continuation:
                    raw = ', '.join(pending + [raw])
                else:
                    unmarked.extend(pending)
                pending = []
            result.append(dict(raw=raw, symbols=symbols))
        else:
            pending.append(raw)
    unmarked.extend(pending)
    if unmarked:
        # 英文部局名のカンマか複数機関かはここで推測せず原表記を保つ。
        result.insert(0, dict(raw=', '.join(unmarked), symbols=['']))
    return result


def detect_presenter(people, groups=None):
    marked = [p for p in people if p['marker_count']]
    if len(marked) > 1 or any(p['marker_count'] > 1 for p in marked):
        return None, 'unresolved', 'multiple_presenter_marks'
    selected = marked[0] if marked else (people[0] if people else None)
    if selected is None or not selected['name'] or selected['invalid_symbols']:
        return None, 'unresolved', 'unreadable_presenter_or_symbols'
    method = 'explicit' if marked else ('single_author' if len(people) == 1 and not groups else 'inferred_first_author')
    return selected, method, ''


def session_areas(text, number, first_half):
    matches = list(AREA_RE.finditer(text))
    if not matches or matches[0].start() != 0:
        return '', [], 'unknown_primary_area'
    primary = AREA_NAMES[matches[0][0]]
    # 領域横断（80周年サテライト）は領域名の一部。
    clean = text.replace('（80周年サテライト）', '')
    base, _, conditions = clean.partition('（')
    joint = [AREA_NAMES[m[0]] for m in AREA_RE.finditer(base)]
    reason = ''
    if conditions:
        pattern = r'([0-9０-９][0-9０-９，,〜～\-]*|前半|後半)番?目?[^，。]*?のみ(.*?)(?:と合同)'
        clauses = list(re.finditer(pattern, conditions))
        if not clauses:
            reason = 'unparsed_joint_condition'
        for clause in clauses:
            selector = clause[1]
            if selector in ('前半', '後半'):
                applies = first_half if selector == '前半' else not first_half
            else:
                indices = set()
                for token in re.split('[，,]', selector):
                    ends = re.split('[〜～-]', token)
                    if len(ends) == 2:
                        indices.update(range(int(ends[0]), int(ends[1]) + 1))
                    else:
                        indices.add(int(token))
                applies = number in indices
            if applies:
                joint.extend(AREA_NAMES[m[0]] for m in AREA_RE.finditer(clause[2]))
    return primary, list(dict.fromkeys(a for a in joint if a != primary)), reason


def parse_page(source, overrides=None):
    soup = BeautifulSoup(Path(source['local_path']).read_text(encoding='utf-8'), 'html.parser')
    listings = soup.select('ol.space-x')
    if not listings:
        raise ValueError(f'講演一覧なし: {source["source_url"]}')
    rows, audit = [], []
    for listing in listings:
        header = listing.find_previous_sibling('div')
        anchor = header.select_one('h3 a[id]') if header else None
        if not anchor or not re.fullmatch(r'j\d{2}[ap].+', anchor['id']):
            raise ValueError(f'セッション番号なし: {source["source_url"]}')
        session = anchor['id'][1:]
        paragraphs = [p.get_text('', strip=True) for p in header.find_all('p')
                      if '講演座長' not in p.get_text()]
        area_text = paragraphs[-1] if paragraphs else ''
        number, first_half, session_title = int(listing.get('start', 1)) - 1, True, ''
        for entry in listing.children:
            if not isinstance(entry, Tag):
                continue
            if entry.name == 'h3':
                session_title = entry.get_text(' ', strip=True)
            if entry.name == 'div' and '休憩' in entry.get_text():
                first_half = False
            if entry.name != 'li':
                continue
            number = int(entry.get('value', number + 1))
            listed_id = f'{session}-{number:02d}'
            pid = listed_id
            correction = (overrides or {}).get((source['source_url'], listed_id))
            if correction:
                digest = hashlib.sha256(Path(source['local_path']).read_bytes()).hexdigest()
                if digest != correction['source_sha256']:
                    raise ValueError('取得内容が変わったため講演番号補正を再確認してください: ' + listed_id)
                pid = correction['presentation_id']
                audit.append(dict(presentation_id=pid, reason='reviewed_id_correction',
                                  detail=listed_id + ': ' + correction['note'], source_url=source['source_url']))
            smalls = entry.find_all('small')
            full_text = compact(entry.get_text(' ', strip=True))
            no_space = re.sub(r'\s+', '', full_text)
            exclusion = ''
            if not smalls and '取消' in no_space:
                exclusion = 'cancelled'
            elif not smalls and '移動' in no_space:
                exclusion = 'moved_placeholder'
            elif not full_text:
                exclusion = 'empty_slot'
            elif not smalls and any(s in full_text for s in ['休憩', '座長', 'インフォーマル', '展示']):
                exclusion = 'non_presentation'
            if exclusion:
                audit.append(dict(presentation_id=pid, reason=exclusion, detail=full_text,
                                  source_url=source['source_url']))
                continue
            title_parts = []
            for child in entry.children:
                if isinstance(child, Tag) and child.name in ('br', 'small'):
                    break
                title_parts.append(child.get_text() if isinstance(child, Tag) else str(child))
            title = re.sub(r'\s*[（(]\d+分[）)]\s*$', '', compact(''.join(title_parts)))
            type_match = re.match(r'^[（(]([^）)]+講演)[）)]', title)
            lecture_type = type_match[1] if type_match else '一般'
            primary, joint, area_reason = session_areas(area_text, number, first_half)
            reasons = [area_reason] if area_reason else []
            for link in entry.select('a[href]'):
                match = re.search(r'/([^/]+)\.pdf$', link['href'])
                if match and match[1] != pid:
                    reasons.append('presentation_id_mismatch:' + match[1])
            people, groups, affs = [], [], []
            if len(smalls) == 2:
                people, groups = parse_people(smalls[1])
                affs = parse_affiliations(smalls[0])
            presenter, method, why = detect_presenter(people, groups)
            raw = []
            if why:
                reasons.append(why)
            if presenter:
                for symbol in presenter['symbols']:
                    matching = [a['raw'] for a in affs if symbol in a['symbols']]
                    if not matching:
                        reasons.append('unmatched_affiliation_symbol:' + symbol)
                    # 同じ記号の複数所属も全て保持。機関名の正規化は別段階。
                    raw.extend(matching)
            row = dict(presentation_id=pid, scheduled_presentation_id=listed_id, registration_id='', title=title,
                       area_id=primary, joint_areas=joint, format=source['format'],
                       lecture_type=lecture_type, presenter=presenter['name'] if presenter else '',
                       presenter_detection=method, presenter_affiliation_raw=list(dict.fromkeys(raw)),
                       source_url=source['source_url'], listed_area_id=source['area_id'],
                       session_area_text=area_text, session_title=session_title,
                       authors=people, collaboration_groups=groups, affiliations=affs,
                       authors_html=str(smalls[1]) if len(smalls) == 2 else '',
                       affiliations_html=str(smalls[0]) if len(smalls) == 2 else '',
                       reasons=reasons)
            rows.append(row)
    return rows, audit


def verified_sources():
    sources = read_csv('data/source_urls.csv')
    latest = {}
    for line in Path('data/raw/manifest.jsonl').read_text(encoding='utf-8').splitlines():
        item = json.loads(line)
        latest[item['source_url']] = item
    for source in sources:
        path = Path(source['local_path'])
        record = latest.get(source['source_url'], {})
        if record.get('status') != 'ok' or not path.is_file():
            raise ValueError(f'取得未完了: {path}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError(f'ハッシュ不一致: {path}')
    return sources


def parse_all():
    grouped, audit = defaultdict(list), []
    overrides = {(r['source_url'], r['listed_id']): r for r in read_csv('data/presentation_overrides.csv')}
    sources = verified_sources()
    for source in sources:
        rows, excluded = parse_page(source, overrides)
        audit.extend(excluded)
        for row in rows:
            grouped[row['presentation_id']].append(row)
    result = []
    for pid, variants in sorted(grouped.items()):
        selected = next((r for r in variants if r['listed_area_id'] == r['area_id']), variants[0])
        keys = ['title', 'area_id', 'presenter', 'presenter_detection', 'authors', 'affiliations', 'format']
        if any(any(v[k] != selected[k] for k in keys) for v in variants):
            selected['reasons'].append('conflicting_duplicate')
        selected['source_urls'] = sorted(set(v['source_url'] for v in variants))
        selected['listed_areas'] = sorted(set(v['listed_area_id'] for v in variants))
        for duplicate in variants:
            if duplicate is not selected:
                audit.append(dict(presentation_id=pid, reason='duplicate',
                                  detail='主領域へ統合: ' + selected['area_id'], source_url=duplicate['source_url']))
        for reason in selected['reasons']:
            audit.append(dict(presentation_id=pid, reason=reason, detail=selected['session_area_text'],
                              source_url=selected['source_url']))
        result.append(selected)
    # 一方のページが取消なのに他方に講演が残る場合は確定させない。
    cancelled = {a['presentation_id'] for a in audit if a['reason'] == 'cancelled'}
    for row in result:
        if row['presentation_id'] in cancelled:
            row['reasons'].append('conflicting_cancellation')
            audit.append(dict(presentation_id=row['presentation_id'], reason='conflicting_cancellation',
                              detail='別ページに取消と講演の両方が存在', source_url=row['source_url']))
    Path('output').mkdir(exist_ok=True)
    with Path('output/presentations.jsonl').open('w', encoding='utf-8') as stream:
        for row in result:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    write_csv('output/audit.csv', audit, ['presentation_id', 'reason', 'detail', 'source_url'])
    paths = [s['local_path'] for s in sources] + ['data/source_urls.csv', 'data/presentation_overrides.csv',
             'scripts/parse_program.py', 'output/presentations.jsonl', 'output/audit.csv']
    metadata = dict(parsed_at=datetime.now(timezone.utc).isoformat(),
                    inputs={p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths})
    Path('output/parse_manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('重複排除後の講演:', len(result))
    print('登壇者判定:', dict(Counter(r['presenter_detection'] for r in result)))
    print('要確認:', dict(Counter(reason for r in result for reason in r['reasons'])))


if __name__ == '__main__':
    parse_all()
