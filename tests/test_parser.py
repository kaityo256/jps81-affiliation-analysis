import json
import sys
import tempfile
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from parse_program import parse_people, parse_affiliations, detect_presenter, session_areas, parse_page
from normalize_affiliations import AliasTable, normalize_row
from build_report import ranking, pct


def html(text):
    return BeautifulSoup('<small>' + text + '</small>', 'html.parser').small


class PresenterTest(unittest.TestCase):
    def test_explicit_nonfirst_and_multiple_symbols(self):
        people, groups = parse_people(html('甲一郎<sup>A</sup>, <sup>○</sup>乙二郎<sup>A, B</sup>'))
        who, method, reason = detect_presenter(people)
        self.assertEqual((who['name'], method, reason), ('乙二郎', 'explicit', ''))
        self.assertEqual(who['symbols'], ['A', 'B'])

    def test_inferred_and_single(self):
        self.assertEqual(detect_presenter(parse_people(html('甲, 乙'))[0])[1], 'inferred_first_author')
        self.assertEqual(detect_presenter(parse_people(html('甲'))[0])[1], 'single_author')

    def test_multiple_marks_not_inferred(self):
        self.assertIsNone(detect_presenter(parse_people(html('<sup>○</sup>甲, <sup>◯</sup>乙'))[0])[0])

    def test_collaboration_not_named_author(self):
        people, groups = parse_people(html('甲<sup>A</sup>, for Example collaboration'))
        self.assertEqual(len(people), 1)
        self.assertEqual(detect_presenter(people, groups)[1], 'inferred_first_author')

    def test_symbol_range_and_unrecognized_footnote(self):
        self.assertEqual(parse_people(html('甲<sup>A-C</sup>'))[0][0]['symbols'], ['A','B','C'])
        self.assertEqual(detect_presenter(parse_people(html('甲<sup>A*</sup>'))[0])[1], 'unresolved')

    def test_affiliations_unmarked_and_superscript_number(self):
        actual = parse_affiliations(html('東大理, 広大WPI-SKCM<sup>2</sup><sup>A</sup>, 慶大<sup>B, C</sup>'))
        self.assertEqual(actual, [dict(raw='東大理', symbols=['']), dict(raw='広大WPI-SKCM2', symbols=['A']), dict(raw='慶大', symbols=['B','C'])])

    def test_english_department_commas(self):
        actual = parse_affiliations(html('Dept. of Physics, Example University<sup>A</sup>, School of Science, Other University<sup>B</sup>'))
        self.assertEqual(actual, [dict(raw='Dept. of Physics, Example University', symbols=['A']),dict(raw='School of Science, Other University', symbols=['B'])])

    def test_unlabelled_multiple_institutions_kept(self):
        self.assertEqual(parse_affiliations(html('甲大学, 乙大学')), [dict(raw='甲大学, 乙大学', symbols=[''])])

    def test_english_unmarked_department_before_labelled_department(self):
        actual = parse_affiliations(html('Dept. Phys., Nagoya Univ., Grad. Sch. Eng., Nagoya Univ.<sup>A</sup>'))
        self.assertEqual(actual, [dict(raw='Dept. Phys., Nagoya Univ.',symbols=['']),
                                 dict(raw='Grad. Sch. Eng., Nagoya Univ.',symbols=['A'])])

    def test_joint_area_ranges(self):
        text = '計算物理領域（1〜2，4番目のみ領域11と合同，3番目のみ領域4と合同）'
        self.assertEqual(session_areas(text, 4, False), ('computational_physics', ['area11'], ''))
        self.assertEqual(session_areas(text, 3, True), ('computational_physics', ['area4'], ''))
        self.assertEqual(session_areas(text, 5, False)[1], [])

    def test_joint_first_half_and_cross_area(self):
        text = '宇宙線・宇宙物理領域（前半のみ素粒子論領域，素粒子実験領域と合同）'
        self.assertEqual(session_areas(text, 1, True)[1], ['particle_theory','particle_experiment'])
        self.assertEqual(session_areas(text, 8, False)[1], [])
        self.assertEqual(session_areas('領域横断（80周年サテライト），領域1',1,True), ('cross_area',['area1'],''))

    def test_poster_start_cancelled_and_missing_symbol(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'page.html'
            path.write_text('''<div><h3><a id="j14pPS"></a></h3><p>領域3</p></div>
            <ol class="space-x" start="36"><li><a href="../pdf/14pPS-36.pdf">題名</a><br>
            <small>甲大学<sup>A</sup></small><br><small>甲<sup>B</sup></small></li>
            <li>取　　消</li><li>移　　動</li></ol>''', encoding='utf-8')
            rows, audit = parse_page(dict(local_path=str(path), source_url='https://example.com/page.html',format='poster',area_id='area3'))
            self.assertEqual(rows[0]['presentation_id'],'14pPS-36')
            self.assertEqual(rows[0]['presenter_affiliation_raw'],[])
            self.assertIn('unmatched_affiliation_symbol:B',rows[0]['reasons'])
            self.assertEqual([r['reason'] for r in audit],['cancelled','moved_placeholder'])
            self.assertEqual([r['presentation_id'] for r in audit],['14pPS-37','14pPS-38'])


class NormalizationTest(unittest.TestCase):
    def test_exact_match_no_prefix_guessing(self):
        table = AliasTable()
        self.assertEqual(table.resolve('東大理')[1], '東京大学')
        self.assertIsNone(table.resolve('東大理・未知機関')[1])
        self.assertIsNone(table.resolve('架空大学')[1])

    def test_different_institutions_remain_separate(self):
        table = AliasTable()
        self.assertNotEqual(table.resolve('総研大')[1],table.resolve('核融合研')[1])

    def test_collapse_same_institution_preserve_original(self):
        row=dict(presenter_affiliation_raw=['東大理','東大物性研','未確認'],reasons=[],presenter_detection='explicit',area_id='area11')
        result=normalize_row(row,AliasTable())
        self.assertEqual(result['affiliation_official'],['東京大学',None])
        self.assertEqual(result['presenter_affiliation_all_raw'],row['presenter_affiliation_raw'])
        self.assertEqual(result['status'],'unresolved_affiliation')

    def test_ambiguous_alias_not_arbitrarily_selected(self):
        table=AliasTable()
        table.aliases['曖昧']={'甲大学','乙大学'}
        table.forms['曖昧理']={'曖昧'}
        self.assertEqual(table.resolve('曖昧理'),('曖昧',None,'ambiguous_alias'))


class RankingTest(unittest.TestCase):
    def test_ranking_deduplicates_intra_presentation_affiliation(self):
        rows = [
            {'affiliation_official': '["東京大学", "東京大学"]'},
            {'affiliation_official': '["京都大学", null]'},
            {'affiliation_official': '["東京大学"]'},
        ]
        self.assertEqual(ranking(rows), [
            {'rank': 1, 'official_name': '東京大学', 'count': 2},
            {'rank': 2, 'official_name': '京都大学', 'count': 1},
        ])

    def test_percentage_uses_lecture_denominator(self):
        self.assertEqual(pct(1, 3), '33.33%')
        self.assertEqual(pct(1, 0), '0.00%')


@unittest.skipUnless(Path('output/extraction_summary.json').exists(), '生成済みデータがないため実データの照合を省略')
class GeneratedDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import csv
        cls.rows=[]
        for path in Path('output/areas').glob('*.csv'):
            with path.open(encoding='utf-8') as stream:
                cls.rows.extend(csv.DictReader(stream))
        cls.by_id={r['presentation_id']:r for r in cls.rows}
        cls.summary=json.loads(Path('output/extraction_summary.json').read_text())

    def test_area_total_and_no_duplicate_ids(self):
        self.assertEqual(len(self.rows),len(self.by_id))
        self.assertEqual(len(self.rows),self.summary['target_presentations'])
        self.assertEqual(sum(self.summary['area_counts'].values()),len(self.rows))

    def test_aligned_arrays_and_institution_dedup(self):
        for row in self.rows:
            arrays=[json.loads(row[k]) for k in ['presenter_affiliation_raw','affiliation_alias','affiliation_official']]
            self.assertEqual(len({len(a) for a in arrays}),1,row['presentation_id'])
            names=[n for n in arrays[2] if n is not None]
            self.assertEqual(len(names),len(set(names)),row['presentation_id'])

    def test_reviewed_cancellation_and_move(self):
        self.assertNotIn('14pL1225-07',self.by_id)
        self.assertNotIn('14pL1225-10',self.by_id)
        self.assertIn('14pL1225-08',self.by_id)
        self.assertIn('14pL1225-09',self.by_id)
        moved=self.by_id['17aL1214-08']
        self.assertEqual(moved['scheduled_presentation_id'],'16pL1214-14')
        self.assertEqual(moved['area_id'],'area11')

    def test_source_examples_explicit_and_poster(self):
        row=self.by_id['14aE513-07']
        self.assertEqual(row['presenter_detection'],'explicit')
        self.assertEqual(json.loads(row['affiliation_official']),['日本原子力研究開発機構'])
        self.assertEqual(row['area_id'],'nuclear_theory')
        self.assertEqual(self.by_id['14pPS-36']['area_id'],'area3')
        self.assertEqual(self.by_id['14pPS-36']['format'],'poster')


if __name__ == '__main__':
    unittest.main()
