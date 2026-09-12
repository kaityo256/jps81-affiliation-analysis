import contextlib
import csv
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from source_manifest import discover, record
from inspect_program import inspect

INDEX = '''<h3>口頭発表</h3><nav><a href="program11.html">領域11</a>
<a href="programz.html">領域横断（理事会企画）</a></nav>
<h3>ポスター発表</h3><nav><a href="programps11.html">領域11</a></nav>
<h3>展示</h3><nav><a href="https://example.com/">展示企業</a></nav>'''


class SourcesTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.previous = Path.cwd()
        os.chdir(self.directory.name)
        Path('data/raw').mkdir(parents=True)
        Path('data/raw/program.html').write_text(INDEX)

    def tearDown(self):
        os.chdir(self.previous)
        self.directory.cleanup()

    def discover(self):
        with contextlib.redirect_stdout(io.StringIO()):
            discover()
        with Path('data/source_urls.csv').open() as f:
            return list(csv.DictReader(f))

    def test_only_presentations_and_fixed_ids(self):
        rows = self.discover()
        self.assertEqual([r['area_id'] for r in rows], ['area11', 'cross_area', 'area11'])
        self.assertEqual([r['format'] for r in rows], ['oral', 'oral', 'poster'])
        self.assertTrue(all(r['source_url'].startswith('https://jps2026a.gakkai-web.net/') for r in rows))

    def test_unknown_link_fails(self):
        Path('data/raw/program.html').write_text(INDEX.replace('program11.html', 'new.html'))
        with self.assertRaisesRegex(ValueError, '未知'):
            self.discover()

    def test_latest_failed_download_rejects_old_file(self):
        rows = self.discover()
        for row in rows:
            Path(row['local_path']).write_text('<ol class="space-x"><li>test</li></ol>')
            record(row['source_url'], row['local_path'], 'ok')
        row = rows[0]
        record(row['source_url'], row['local_path'], 'failed')
        with self.assertRaisesRegex(ValueError, '取得未完了'):
            inspect()

    def test_modified_html_rejected(self):
        rows = self.discover()
        for row in rows:
            Path(row['local_path']).write_text('<ol class="space-x"><li>test</li></ol>')
            record(row['source_url'], row['local_path'], 'ok')
        Path(rows[0]['local_path']).write_text('modified')
        with self.assertRaisesRegex(ValueError, 'ハッシュ不一致'):
            inspect()


if __name__ == '__main__':
    unittest.main()
