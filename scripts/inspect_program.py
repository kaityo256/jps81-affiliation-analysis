"""取得済みHTMLの構造・検証候補を抽出する。集計確定用パーサーではない。"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from bs4 import BeautifulSoup


def inspect():
    with Path('data/source_urls.csv').open(encoding='utf-8') as stream:
        sources = list(csv.DictReader(stream))
    latest = {}
    for line in Path('data/raw/manifest.jsonl').read_text().splitlines():
        record = json.loads(line)
        latest[record['source_url']] = record
    pages, examples = [], {}
    for source in sources:
        path = Path(source['local_path'])
        record = latest.get(source['source_url'], {})
        if record.get('status') != 'ok' or not path.exists():
            raise ValueError(f'取得未完了: {path}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError(f'ハッシュ不一致: {path}')
        soup = BeautifulSoup(path.read_text(), 'html.parser')
        lists = soup.select('ol.space-x')
        counts = Counter()
        for listing in lists:
            header = listing.find_previous_sibling('div')
            context = header.get_text(' ', strip=True) if header else ''
            for entry in listing.find_all('li', recursive=False):
                counts['listed_slots'] += 1
                fields = entry.find_all('small')
                categories = [source['format']]
                if len(fields) == 2:
                    counts['two_small_fields'] += 1
                    author = fields[1]
                    categories.append('explicit' if '○' in author.get_text() else 'no_mark')
                    if any(',' in tag.get_text() for tag in author.find_all('sup')):
                        categories.append('multiple_affiliation_symbols')
                else:
                    counts['other_structure'] += 1
                    categories.append('other_structure')
                if '合同' in context:
                    categories.append('joint_session')
                if '取消' in entry.get_text():
                    categories.append('cancelled')
                for category in categories:
                    if category not in examples:
                        examples[category] = dict(source_url=source['source_url'],
                                                  context=context, html=str(entry))
        pages.append(dict(**source, **counts, session_lists=len(lists)))
    Path('output').mkdir(exist_ok=True)
    Path('output/structure_audit.json').write_text(
        json.dumps(dict(pages=pages, examples=examples), ensure_ascii=False, indent=2) + '\n')
    print(f'{len(pages)}ページの取得・SHA-256を確認')
    print('掲載枠数（重複・取消を含む）:', sum(p.get('listed_slots', 0) for p in pages))
    print('検証候補:', ', '.join(examples))


if __name__ == '__main__':
    inspect()
