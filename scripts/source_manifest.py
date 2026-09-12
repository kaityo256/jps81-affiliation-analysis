"""ローカルの一覧解析と取得履歴管理。通信はdownload.shだけで行う。"""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import re
from bs4 import BeautifulSoup

BASE = 'https://jps2026a.gakkai-web.net/data/html/program.html'
IDS = dict(sr='particle_theory', sj='particle_experiment', rk='nuclear_theory',
           jk='nuclear_experiment', u='cosmic_physics', si='beam_physics',
           kb='computational_physics', z='cross_area')


def discover():
    soup = BeautifulSoup(Path('data/raw/program.html').read_text(), 'html.parser')
    rows = []
    aliases = {}
    for heading in soup.select('h3'):
        label = heading.get_text(strip=True)
        if label not in ('口頭発表', 'ポスター発表'):
            continue
        nav = heading.find_next_sibling('nav')
        if nav is None:
            raise ValueError('発表一覧のnavがありません')
        for link in nav.select('a[href]'):
            href = link['href']
            match = re.fullmatch(r'program(ps)?(\d{2}|sr|sj|rk|jk|u|si|kb|z)\.html', href)
            if not match:
                raise ValueError(f'未知のプログラムリンク: {href}')
            code = match[2]
            area = f'area{int(code)}' if code.isdigit() else IDS[code]
            name = link.get_text(strip=True)
            aliases[name] = area
            rows.append(dict(area_id=area, area_name=name,
                             format='poster' if match[1] else 'oral',
                             source_url=urljoin(BASE, href), local_path='data/raw/' + href))
    if not rows or not any(r['format'] == 'poster' for r in rows):
        raise ValueError('口頭・ポスターの一覧を取得できません')
    with Path('data/source_urls.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with Path('data/area_aliases.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['raw_area_name', 'area_id'])
        writer.writerows(aliases.items())
    for row in rows:
        print(row['source_url'] + '\t' + row['local_path'])


def record(url, filename, status):
    path = Path(filename)
    item = dict(retrieved_at=datetime.now(timezone.utc).isoformat(), source_url=url,
                local_path=filename, status=status,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest() if status == 'ok' else None)
    with Path('data/raw/manifest.jsonl').open('a') as f:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['discover', 'record'])
    parser.add_argument('args', nargs='*')
    args = parser.parse_args()
    if args.action == 'discover':
        discover()
    else:
        record(*args.args)
