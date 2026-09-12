"""根拠付きの確定済み対応表だけを適用する。通信・推測による追加はしない。"""
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from parse_program import read_csv, write_csv, verified_sources, presentation_sort_key

FIELDS = ['presentation_id', 'registration_id', 'title', 'area_id', 'area_name', 'joint_areas',
          'format', 'lecture_type', 'presenter', 'presenter_detection', 'presenter_affiliation_raw',
          'affiliation_alias', 'affiliation_official', 'status', 'source_url',
          'scheduled_presentation_id', 'session_area_text', 'source_urls', 'reasons',
          'presenter_affiliation_all_raw']

# 明示的に確認済みの特殊表記。対応表CSVに依存せず、再実行時にも同じ結果にする。
SPECIAL_AFFILIATIONS = {
    '無所属': ('無所属', '無所属'),
    '琉大理': ('琉大理', '琉球大学'),
    '高知大': ('高知大', '高知大学'),
    '高知大データ': ('高知大データ', '高知大学'),
    '高知大教': ('高知大教', '高知大学'),
    '高エネルギー加速器研究機構': ('高エネルギー加速器研究機構', '高エネルギー加速器研究機構'),
    '高エネルギー加速器研究機構素粒子原子核研究所（KEK IPNS）': ('高エネルギー加速器研究機構素粒子原子核研究所（KEK IPNS）', '高エネルギー加速器研究機構'),
    '高エネルギー加速器研究機構（高エ研）': ('高エネルギー加速器研究機構（高エ研）', '高エネルギー加速器研究機構'),
    '高エネルギー加速器研究機構（高エ研)': ('高エネルギー加速器研究機構（高エ研)', '高エネルギー加速器研究機構'),
    '高エネ研・物構研': ('高エネ研・物構研', '高エネルギー加速器研究機構'),
    '高エネ計セ': ('高エネ計セ', '高エネルギー加速器研究機構'),
    'エルライ': ('エルライ', 'エルライ'),
    'キュービットコア': ('キュービットコア', 'キュービットコア'),
    'クオンティニュアム': ('クオンティニュアム', 'クオンティニュアム'),
    'シグマアイ': ('シグマアイ', 'シグマアイ'),
    'シャレンノマド': ('シャレンノマド', 'シャレンノマド'),
    'セイコーエプソン': ('セイコーエプソン', 'セイコーエプソン'),
    'ナノアロイテクノロジー': ('ナノアロイテクノロジー', 'ナノアロイテクノロジー'),
    '新大理': ('新大理', '新潟大学'),
    '新大自': ('新大自', '新潟大学'),
    '名大高等研': ('名大高等研', '名古屋大学'),
    '奈良女子大': ('奈良女子大', '奈良女子大学'),
    '安徽理工大学': ('安徽理工大学', '安徽理工大学'),
    '都市大理工': ('都市大理工', '東京都市大学'),
    '埼玉大理': ('埼玉大理', '埼玉大学'),
    '埼大理': ('埼大理', '埼玉大学'),
    '国士舘大理': ('国士舘大理', '国士舘大学'),
    '高知大理工': ('高知大理工', '高知大学'),
    '新大総': ('新大総', '新潟大学'),
    'ICRR': ('ICRR', '東京大学'),
    'Max Planck Inst. for Chemical Phys. of Solids': ('Max Planck Inst. for Chemical Phys. of Solids', 'Max Planck Institute for Chemical Physics of Solids'),
    'はこだて未来大複雑': ('はこだて未来大複雑', '公立はこだて未来大学'),
    '京女大': ('京女大', '京都女子大学'),
    '京教大物理': ('京教大物理', '京都教育大学'),
    '京都府大生命環境': ('京都府大生命環境', '京都府立大学'),
    '奈良教育大': ('奈良教育大', '奈良教育大学'),
    '富士通': ('富士通', '富士通'),
    '富山県大工': ('富山県大工', '富山県立大学'),
    '富山県立大': ('富山県立大', '富山県立大学'),
    '富山県立大工': ('富山県立大工', '富山県立大学'),
    '成蹊大理工': ('成蹊大理工', '成蹊大学'),
    '摂南大理工': ('摂南大理工', '摂南大学'),
    '東京第一合成': ('東京第一合成', '東京第一合成'),
    '東薬大': ('東薬大', '東京薬科大学'),
    '松江高専': ('松江高専', '松江工業高等専門学校'),
    '滋賀県大院工': ('滋賀県大院工', '滋賀県立大学'),
    '物性研': ('物性研', '東京大学'),
    '琉球大院地域共創': ('琉球大院地域共創', '琉球大学'),
    '神大理': ('神大理', '神戸大学'),
    '諏訪理科大': ('諏訪理科大', '公立諏訪東京理科大学'),
    '豊田中研': ('豊田中研', '豊田中央研究所'),
    '鈴鹿高専': ('鈴鹿高専', '鈴鹿工業高等専門学校'),
    '防衛医大': ('防衛医大', '防衛医科大学校'),
    '順天堂大医': ('順天堂大医', '順天堂大学'),
    '香港科技大': ('香港科技大', '香港科技大学'),
    '高知工科大理工': ('高知工科大理工', '高知工科大学'),
    '佐賀大文化教育': ('佐賀大文化教育', '佐賀大学'),
    '一橋大': ('一橋大', '一橋大学'),
    '一橋大SDS': ('一橋大SDS', '一橋大学'),
    '国士舘大理': ('国士舘大理', '国士舘大学'),
    '国際基督教大': ('国際基督教大', '国際基督教大学'),
    '国際教養大': ('国際教養大', '国際教養大学'),
    '城西大理': ('城西大理', '城西大学'),
    '埼大院理工': ('埼大院理工', '埼玉大学'),
    '埼工大': ('埼工大', '埼玉工業大学'),
    '大公大院理': ('大公大院理', '大阪公立大学'),
    '大分大理工': ('大分大理工', '大分大学'),
    '大分高専': ('大分高専', '大分工業高等専門学校'),
    '大同大': ('大同大', '大同大学'),
    '大島商船高専': ('大島商船高専', '大島商船高等専門学校'),
    '大阪公立大高専': ('大阪公立大高専', '大阪公立大学工業高等専門学校'),
    '奈良女理': ('奈良女理', '奈良女子大学'),
    '奥羽大歯': ('奥羽大歯', '奥羽大学'),
    '宇宙研': ('宇宙研', '宇宙航空研究開発機構宇宙科学研究所'),
    '宇部高専': ('宇部高専', '宇部工業高等専門学校'),
    '宇都宮大': ('宇都宮大', '宇都宮大学'),
    '宇都宮大DSM': ('宇都宮大DSM', '宇都宮大学'),
    '宇都宮大工': ('宇都宮大工', '宇都宮大学'),
    '室工大シス情': ('室工大シス情', '室蘭工業大学'),
    '室工大院工': ('室工大院工', '室蘭工業大学'),
    '宮崎大工': ('宮崎大工', '宮崎大学'),
    '宮崎大教育': ('宮崎大教育', '宮崎大学'),
    '宮教大教育': ('宮教大教育', '宮崎大学'),
    '富大理': ('富大理', '富山大学'),
    '小山高専': ('小山高専', '小山工業高等専門学校'),
    '岐大工': ('岐大工', '岐阜大学'),
    '岐阜大': ('岐阜大', '岐阜大学'),
    '岐阜大医': ('岐阜大医', '岐阜大学'),
    '岐阜大教育': ('岐阜大教育', '岐阜大学'),
    '岐阜高専': ('岐阜高専', '岐阜工業高等専門学校'),
    '岡山商科大': ('岡山商科大', '岡山商科大学'),
    '岡山理科大': ('岡山理科大', '岡山理科大学'),
    '岡山県立大情報工': ('岡山県立大情報工', '岡山県立大学'),
    '崇城大': ('崇城大', '崇城大学'),
    '崇城大情報': ('崇城大情報', '崇城大学'),
    '帯畜大人科': ('帯畜大人科', '帯広畜産大学'),
    '広市大院情報': ('広市大院情報', '広島市立大学'),
    '徳島大': ('徳島大', '徳島大学'),
    '徳島大理工': ('徳島大理工', '徳島大学'),
    '徳島大院': ('徳島大院', '徳島大学'),
    '愛工大': ('愛工大', '愛知工業大学'),
    '愛教大物理': ('愛教大物理', '愛知教育大学'),
    '愛知工科大': ('愛知工科大', '愛知工科大学'),
    '成城大': ('成城大', '成城大学'),
    '成蹊大': ('成蹊大', '成蹊大学'),
    '摂南大理工生命科学': ('摂南大理工生命科学', '摂南大学'),
    '放大': ('放大', '放送大学'),
    '新大': ('新大', '新潟大学'),
    '新大自然': ('新大自然', '新潟大学'),
    '新居浜高専': ('新居浜高専', '新居浜工業高等専門学校'),
    '日医大': ('日医大', '日本医科大学'),
    '日本工大': ('日本工大', '日本工業大学'),
    '日本文理大工': ('日本文理大工', '日本文理大学'),
    '日立研開': ('日立研開', '日立製作所'),
    '早大学院': ('早大学院', '早稲田大学'),
    '早稲田': ('早稲田', '早稲田大学'),
    '早稲田先進理工': ('早稲田先進理工', '早稲田大学'),
    '明星大院理工': ('明星大院理工', '明星大学'),
    '明海大歯': ('明海大歯', '明海大学'),
    '東京医大': ('東京医大', '東京医科大学'),
    '東京学芸大': ('東京学芸大', '東京学芸大学'),
    '東京工科大': ('東京工科大', '東京工科大学'),
    '東京農工大工': ('東京農工大工', '東京農工大学'),
    '東京農工大院工': ('東京農工大院工', '東京農工大学'),
    '東京都市大理工': ('東京都市大理工', '東京都市大学'),
    '東北学院大工': ('東北学院大工', '東北学院大学'),
    '東北院理': ('東北院理', '東北大学'),
    '東女大': ('東女大', '東京女子大学'),
    '東学大': ('東学大', '東京学芸大学'),
    '東学大附高': ('東学大附高', '東京学芸大学附属高等学校'),
    '東科学大': ('東科学大', '東京科学大学'),
    '横市大理': ('横市大理', '横浜市立大学'),
    '横市大院生命ナノ': ('横市大院生命ナノ', '横浜市立大学'),
    '横浜市大': ('横浜市大', '横浜市立大学'),
    '沖縄科学技術大学院大': ('沖縄科学技術大学院大', '沖縄科学技術大学院大学'),
    '沖縄高専': ('沖縄高専', '沖縄工業高等専門学校'),
    '河南大': ('河南大', '河南大学'),
    '法政大': ('法政大', '法政大学'),
    '法政大院理工': ('法政大院理工', '法政大学'),
    '滋賀大DS': ('滋賀大DS', '滋賀大学'),
    '熊保大': ('熊保大', '熊本保健科学大学'),
    '熊本保健科学大': ('熊本保健科学大', '熊本保健科学大学'),
    '熊本学園大': ('熊本学園大', '熊本学園大学'),
    '獨協医科大': ('獨協医科大', '獨協医科大学'),
    '甲南大': ('甲南大', '甲南大学'),
    '石川高専': ('石川高専', '石川工業高等専門学校'),
    '神大院理': ('神大院理', '神戸大学'),
    '神戸常盤': ('神戸常盤', '神戸常盤大学'),
    '福岡大理': ('福岡大理', '福岡大学'),
    '福岡教育大学': ('福岡教育大学', '福岡教育大学'),
    '福岡県立大人社': ('福岡県立大人社', '福岡県立大学'),
    '福島高専': ('福島高専', '福島工業高等専門学校'),
    '秋田高専機械': ('秋田高専機械', '秋田工業高等専門学校'),
    '立教物': ('立教物', '立教大学'),
    '第一工科大': ('第一工科大', '第一工科大学'),
    '統数研': ('統数研', '統計数理研究所'),
    '群大CMD': ('群大CMD', '群馬大学'),
    '群大院理工': ('群大院理工', '群馬大学'),
    '群馬大': ('群馬大', '群馬大学'),
    '芝工大': ('芝工大', '芝浦工業大学'),
    '芝浦工大': ('芝浦工大', '芝浦工業大学'),
    '芝浦工大シス理': ('芝浦工大シス理', '芝浦工業大学'),
    '芝浦工大理工': ('芝浦工大理工', '芝浦工業大学'),
    '芝浦工業大学': ('芝浦工業大学', '芝浦工業大学'),
    '茨城高専': ('茨城高専', '茨城工業高等専門学校'),
    '豊田中央研究所': ('豊田中央研究所', '豊田中央研究所'),
    '追手門学院大理工': ('追手門学院大理工', '追手門学院大学'),
    '都城高専': ('都城高専', '都城工業高等専門学校'),
    '都市大': ('都市大', '東京都市大学'),
    '都市大情デ研': ('都市大情デ研', '東京都市大学'),
    '都立産技高専': ('都立産技高専', '東京都立産業技術高等専門学校'),
    '金大附高': ('金大附高', '金沢大学附属高等学校'),
    '金工大数理工セ': ('金工大数理工セ', '金沢工業大学'),
    '金沢学院大情報工': ('金沢学院大情報工', '金沢学院大学'),
    '金沢工大工': ('金沢工大工', '金沢工業大学'),
    '金沢工大数理工': ('金沢工大数理工', '金沢工業大学'),
    '金沢工大数理工セ': ('金沢工大数理工セ', '金沢工業大学'),
    '金沢院自然': ('金沢院自然', '金沢大学'),
    '長崎大教育': ('長崎大教育', '長崎大学'),
    '関医大': ('関医大', '関西医科大学'),
    '関学大工': ('関学大工', '関西学院大学'),
    '関学大理工': ('関学大理工', '関西学院大学'),
    '関西大': ('関西大', '関西大学'),
    '関西大シス理工': ('関西大シス理工', '関西大学'),
    '関西学院大工': ('関西学院大工', '関西学院大学'),
    '阪公理': ('阪公理', '大阪公立大学'),
    '防大応物': ('防大応物', '防衛大学校'),
    '防衛大': ('防衛大', '防衛大学校'),
    '電大工': ('電大工', '東京電機大学'),
    '静岡県大': ('静岡県大', '静岡県立大学'),
    '韓国崇実大': ('韓国崇実大', '崇実大学校'),
    '順大医': ('順大医', '順天堂大学'),
    '順天堂保医': ('順天堂保医', '順天堂大学'),
    '順天堂大': ('順天堂大', '順天堂大学'),
    '香港科技大物理': ('香港科技大物理', '香港科技大学'),
    '駒澤大': ('駒澤大', '駒澤大学'),
    '高千穂大人科': ('高千穂大人科', '高千穂大学'),
    '高知工大': ('高知工大', '高知工科大学'),
    '鹿児島大理工': ('鹿児島大理工', '鹿児島大学'),
    '鹿大理': ('鹿大理', '鹿児島大学'),
    '鹿大院理工': ('鹿大院理工', '鹿児島大学'),
    '龍谷大経営': ('龍谷大経営', '龍谷大学'),
    'NAT': ('NAT', 'National Academy of Taiwan'),
    'National Chung Hsing University, Dept. Phys.': ('National Chung Hsing University, Dept. Phys.', 'National Chung Hsing University'),
    'National Sun Yat-sen University, Dept. Phys.': ('National Sun Yat-sen University, Dept. Phys.', 'National Sun Yat-sen University'),
    'National Taitung University, Dept. Applied Science': ('National Taitung University, Dept. Applied Science', 'National Taitung University'),
    'National Taiwan University, Dept. Phys.': ('National Taiwan University, Dept. Phys.', 'National Taiwan University'),
    'National Tamkang University, Dept. Phys.': ('National Tamkang University, Dept. Phys.', 'Tamkang University'),
    'National Yang Ming Chiao Tung University, Dept. Electrophysics': ('National Yang Ming Chiao Tung University, Dept. Electrophysics', 'National Yang Ming Chiao Tung University'),
    'Paul Scherrer Institut (PSI)': ('Paul Scherrer Institut (PSI)', 'Paul Scherrer Institute'),
    'QUP': ('QUP', 'KEK QUP'),
    'Shibaura Inst. of Tech., Hokkaido Univ.': ('Shibaura Inst. of Tech., Hokkaido Univ.', '芝浦工業大学'),
    'The Inst. for Solid State Phys., Univ. of Tokyo': ('The Inst. for Solid State Phys., Univ. of Tokyo', '東京大学'),
    'Univ. Electro-Commun., Dept. Eng. Sci.': ('Univ. Electro-Commun., Dept. Eng. Sci.', '電気通信大学'),
    'Univ. Rome, Dept. Phys.': ('Univ. Rome, Dept. Phys.', 'Sapienza University of Rome'),
    'Univ. of Rajshahi Dept. of Phys., Fac. of Sci.': ('Univ. of Rajshahi Dept. of Phys., Fac. of Sci.', 'University of Rajshahi'),
    'WPI, Hiroshima Univ.': ('WPI, Hiroshima Univ.', '広島大学'),
    'Waseda Univ., Dept. Appl. Phys.': ('Waseda Univ., Dept. Appl. Phys.', '早稲田大学'),
    'Yokohama Nat\'l. Univ.': ('Yokohama Nat\'l. Univ.', '横浜国立大学'),
    'マックス・プランク・プラズマ物理学研究所': ('マックス・プランク・プラズマ物理学研究所', 'マックス・プランク・プラズマ物理学研究所'),
    'メトロ': ('メトロ', '東京都立大学'),
    '佐大シンクロ': ('佐大シンクロ', '佐賀大学'),
    '佐賀大シンクロトロン': ('佐賀大シンクロトロン', '佐賀大学'),
    '兵庫医大医物理': ('兵庫医大医物理', '兵庫医科大学'),
    '広島工業大学 環境学部（広工大環境）': ('広島工業大学 環境学部（広工大環境）', '広島工業大学'),
    '情報通信研究機構': ('情報通信研究機構', '情報通信研究機構'),
    '情通機構': ('情通機構', '情報通信研究機構'),
    '情通研': ('情通研', '情報通信研究機構'),
    '同志社大リサーチ・イノベーション推進機構': ('同志社大リサーチ・イノベーション推進機構', '同志社大学'),
    '韓国基礎科学研究院': ('韓国基礎科学研究院', '韓国基礎科学研究院'),
    '高度情報科学技術研究機構': ('高度情報科学技術研究機構', '高度情報科学技術研究機構'),
    'Dept. of Phys., Nagoya Univ.': ('Dept. of Phys., Nagoya Univ.', '名古屋大学'),
    'Dept. Phys., Nagoya Univ.': ('Dept. Phys., Nagoya Univ.', '名古屋大学'),
    'Sch. Sci., Tokai U.': ('Sch. Sci., Tokai U.', '東海大学'),
    'CCS, U. Tsukuba': ('CCS, U. Tsukuba', '筑波大学'),
    'CiDER, U. Osaka': ('CiDER, U. Osaka', '大阪大学'),
    'Dep. Phys, U. Osaka': ('Dep. Phys, U. Osaka', '大阪大学'),
    'Department of Physics, Kyushu University': ('Department of Physics, Kyushu University', '九州大学'),
    'Dept. Phys., Tohoku Univ.': ('Dept. Phys., Tohoku Univ.', '東北大学'),
    'Dept. of Appl. Phys., Univ. of Tokyo': ('Dept. of Appl. Phys., Univ. of Tokyo', '東京大学'),
    'Dept. of Applied Phys., The Univ. of Tokyo': ('Dept. of Applied Phys., The Univ. of Tokyo', '東京大学'),
    'Dept. of Condensed Matter Phys., Hokkaido Univ.': ('Dept. of Condensed Matter Phys., Hokkaido Univ.', '北海道大学'),
    'Dept. of Phys. No. 1, Grad. Sch. of Sci., Kyoto Univ.': ('Dept. of Phys. No. 1, Grad. Sch. of Sci., Kyoto Univ.', '京都大学'),
    'Dept. of Phys., Inst. of Sci. Tokyo': ('Dept. of Phys., Inst. of Sci. Tokyo', '東京科学大学'),
    'Dept. of Phys., Sch. of Sci., Inst. of Sci. Tokyo': ('Dept. of Phys., Sch. of Sci., Inst. of Sci. Tokyo', '東京科学大学'),
    'びわこ学院大短大部': ('びわこ学院大短大部', 'びわこ学院大学'),
    '一関高専': ('一関高専', '一関工業高等専門学校'),
    '三井住友銀行': ('三井住友銀行', '三井住友銀行'),
    '三重大': ('三重大', '三重大学'),
    '中部大天文台': ('中部大天文台', '中部大学'),
    '中部大工': ('中部大工', '中部大学'),
    '九州産業大': ('九州産業大', '九州産業大学'),
    '九産大': ('九産大', '九州産業大学'),
    '九産大理工': ('九産大理工', '九州産業大学'),
    '二松学舎': ('二松学舎', '二松学舎大学'),
    '京府医': ('京府医', '京都府立医科大学'),
    '京都先端': ('京都先端', '京都先端科学大学'),
    '仁科セ': ('仁科セ', '理化学研究所仁科加速器科学研究センター'),
    '住友化学': ('住友化学', '住友化学'),
    '佐賀大院理工': ('佐賀大院理工', '佐賀大学'),
    '兵教大': ('兵教大', '兵庫教育大学'),
    '函館高専': ('函館高専', '函館工業高等専門学校'),
    '函館高専一般系': ('函館高専一般系', '函館工業高等専門学校'),
    '北教大札幌': ('北教大札幌', '北海道教育大学'),
    '北海学園大工': ('北海学園大工', '北海学園大学'),
    '北海道教育大札幌校': ('北海道教育大札幌校', '北海道教育大学'),
    '北科大工': ('北科大工', '北海道科学大学'),
    '北陸先端大': ('北陸先端大', '北陸先端科学技術大学院大学'),
    '北陸先端大マテリアル': ('北陸先端大マテリアル', '北陸先端科学技術大学院大学'),
    '医療創生大': ('医療創生大', '医療創生大学'),
    '千歳科技大理工': ('千歳科技大理工', '公立千歳科学技術大学'),
    '千葉工大': ('千葉工大', '千葉工業大学'),
    '千葉工大院工': ('千葉工大院工', '千葉工業大学'),
    '千葉高': ('千葉高', '千葉県立千葉高等学校'),
    '同大理工': ('同大理工', '同志社大学'),
    '名古屋工大工': ('名古屋工大工', '名古屋工業大学'),
    '名城大': ('名城大', '名城大学'),
    '和大シス工': ('和大シス工', '和歌山大学'),
    '和歌山大': ('和歌山大', '和歌山大学'),
    '和歌山高専': ('和歌山高専', '和歌山工業高等専門学校'),
    '国立台湾大': ('国立台湾大', '国立台湾大学'),
    '国立清華大': ('国立清華大', '国立清華大学'),
    '基礎物理学研究所': ('基礎物理学研究所', '京都大学基礎物理学研究所'),
    '埼玉医大物理': ('埼玉医大物理', '埼玉医科大学'),
    '大公大国際機関教育': ('大公大国際機関教育', '大阪公立大学'),
    '学際研': ('学際研', '学際研究所'),
    '富士通人工知能研': ('富士通人工知能研', '富士通'),
    '富士通研究所': ('富士通研究所', '富士通'),
    '富士通量子研': ('富士通量子研', '富士通'),
    '岩大総合科': ('岩大総合科', '岩手大学'),
    '島大総理': ('島大総理', '島根大学'),
    '徳島大院社会産業理工学': ('徳島大院社会産業理工学', '徳島大学'),
    '明治大先端数理': ('明治大先端数理', '明治大学'),
    '明治学院大情報数理': ('明治学院大情報数理', '明治学院大学'),
    '札学大経済経営': ('札学大経済経営', '札幌学院大学'),
    '杏林大医': ('杏林大医', '杏林大学'),
    '東科大情報工高安研': ('東科大情報工高安研', '東京科学大学'),
    '浙江光電子研究院': ('浙江光電子研究院', '浙江大学'),
    '独立': ('独立', '独立'),
    '理科実験サポートネット': ('理科実験サポートネット', '理科実験サポートネット'),
    '職業大能開基礎': ('職業大能開基礎', '職業能力開発総合大学校'),
    '臺湾成大電漿所': ('臺湾成大電漿所', '国立成功大学'),
    '若狭湾エネ研セ': ('若狭湾エネ研セ', '若狭湾エネルギー研究センター'),
    '近代物理研': ('近代物理研', '近代物理学研究所'),
    '開智学園': ('開智学園', '学校法人開智学園'),
    '開智所沢中等': ('開智所沢中等', '開智所沢中等教育学校'),
    'Div. of Phys. and Astronomy, Grad. Sch. of Sci., Kyoto Univ.': ('Div. of Phys. and Astronomy, Grad. Sch. of Sci., Kyoto Univ.', '京都大学'),
    'Faculty of Arts and Science, Kyushu University': ('Faculty of Arts and Science, Kyushu University', '九州大学'),
    'Fukuoka Inst. Technol., Dept. Elect. Eng.': ('Fukuoka Inst. Technol., Dept. Elect. Eng.', '福岡工業大学'),
    'Grad. Sch. of Arts and Sci., UTokyo': ('Grad. Sch. of Arts and Sci., UTokyo', '東京大学'),
    'ICR, Kyoto Univ.': ('ICR, Kyoto Univ.', '京都大学'),
    'ISSP, Univ. of Tokyo': ('ISSP, Univ. of Tokyo', '東京大学'),
    'ISSP, Univ. of Tokyo, Dept. of Applied Electronics': ('ISSP, Univ. of Tokyo, Dept. of Applied Electronics', '東京大学'),
    'Inst. Shibaura Tech., Coll. Eng.': ('Inst. Shibaura Tech., Coll. Eng.', '芝浦工業大学'),
    'National Central University, Dept. Phys.': ('National Central University, Dept. Phys.', '國立中央大學'),
    'Okayama Univ.': ('Okayama Univ.', '岡山大学'),
    'Okinawa Inst. of Sci. and Tech.': ('Okinawa Inst. of Sci. and Tech.', '沖縄科学技術大学院大学'),
    'School of Science, Institute of Science Tokyo': ('School of Science, Institute of Science Tokyo', '東京科学大学'),
    'The Univ. of Electro-Communications': ('The Univ. of Electro-Communications', '電気通信大学'),
    'The University of Tokyo, GSE': ('The University of Tokyo, GSE', '東京大学'),
    'Tokyo Univ. of Marine Sci. and Tech.': ('Tokyo Univ. of Marine Sci. and Tech.', '東京海洋大学'),
    'Univ. of Toyama': ('Univ. of Toyama', '富山大学'),
    'University of Miyazaki': ('University of Miyazaki', '宮崎大学'),
    'University of Wisconsin': ('University of Wisconsin', 'University of Wisconsin'),
    'Wroclaw University of Science and Technology': ('Wroclaw University of Science and Technology', 'Wrocław University of Science and Technology'),
    'A. Sinica': ('A. Sinica', 'Academia Sinica'),
    'Cornell Univ.': ('Cornell Univ.', 'Cornell University'),
    'ENS Paris': ('ENS Paris', 'École normale supérieure, Paris'),
    'Fudan University': ('Fudan University', 'Fudan University'),
    'ICFO': ('ICFO', 'ICFO'),
    'ICTP': ('ICTP', 'Abdus Salam International Centre for Theoretical Physics'),
    'ILANCE': ('ILANCE', 'ILANCE'),
    'INRiM': ('INRiM', 'Istituto Nazionale di Ricerca Metrologica'),
    'IQM Quantum Computers Finland': ('IQM Quantum Computers Finland', 'IQM Quantum Computers'),
    'JKU Linz': ('JKU Linz', 'Johannes Kepler University Linz'),
    'JST さきがけ': ('JST さきがけ', '科学技術振興機構'),
    'JX金属': ('JX金属', 'JX金属'),
    'KCL': ('KCL', "King's College London"),
    'Kanazawa Inst. of Technology': ('Kanazawa Inst. of Technology', 'Kanazawa Institute of Technology'),
    'Korea University': ('Korea University', 'Korea University'),
    "Kyungpook Nat'l. Univ.": ("Kyungpook Nat'l. Univ.", 'Kyungpook National University'),
    'LENS': ('LENS', 'European Laboratory for Non-Linear Spectroscopy'),
    'LQUOM': ('LQUOM', 'LQUOM'),
    'LQUOM, Inc.': ('LQUOM, Inc.', 'LQUOM'),
    'Max-Planck-Inst. for Micro-Structure-Phys.': ('Max-Planck-Inst. for Micro-Structure-Phys.', 'Max Planck Institute for Microstructure Physics'),
    'Middle East Technical Univ.': ('Middle East Technical Univ.', 'Middle East Technical University'),
    'NCKU': ('NCKU', 'National Cheng Kung University'),
    'NCTS': ('NCTS', 'National Center for Theoretical Sciences'),
    'NSRRC': ('NSRRC', 'National Synchrotron Radiation Research Center'),
    'POSTECH': ('POSTECH', 'Pohang University of Science and Technology'),
    'Pukyong National University': ('Pukyong National University', 'Pukyong National University'),
    'Sejong Univ.': ('Sejong Univ.', 'Sejong University'),
    'Sejong University': ('Sejong University', 'Sejong University'),
    'Shizuoka Univ.': ('Shizuoka Univ.', '静岡大学'),
    'Sorbonne Univ.': ('Sorbonne Univ.', 'Sorbonne University'),
    'TU Dresden': ('TU Dresden', 'Technische Universität Dresden'),
    'Univ. Kentucky': ('Univ. Kentucky', 'University of Kentucky'),
    'Univ. of Hong Kong': ('Univ. of Hong Kong', 'The University of Hong Kong'),
    'University of Napoli': ('University of Napoli', 'University of Naples Federico II'),
    'YITP': ('YITP', '京都大学基礎物理学研究所'),
    'CEMS, RIKEN': ('CEMS, RIKEN', '理化学研究所'),
    'Dept. of Phys. and Astronomy, The Univ. of Manchester, United Kingdom': ('Dept. of Phys. and Astronomy, The Univ. of Manchester, United Kingdom', 'The University of Manchester'),
    'Forschungs Zentrum Jülich(FZJ), Germany': ('Forschungs Zentrum Jülich(FZJ), Germany', 'Forschungszentrum Jülich'),
    'Future Univ. Hakodate, Astronomical Inst., Grad. Sch. of Sci.': ('Future Univ. Hakodate, Astronomical Inst., Grad. Sch. of Sci.', '公立はこだて未来大学'),
    'IBS, CENS, Nuclear Reaction Group': ('IBS, CENS, Nuclear Reaction Group', 'Institute for Basic Science'),
    'IBS, CENS, Nuclear Structure Group': ('IBS, CENS, Nuclear Structure Group', 'Institute for Basic Science'),
    'IBS, IRIS': ('IBS, IRIS', 'Institute for Basic Science'),
    'IBS-CCES': ('IBS-CCES', 'Institute for Basic Science'),
    'IBS-CTPU-CGA': ('IBS-CTPU-CGA', 'Institute for Basic Science'),
    'Inst. of Astroparticle Phys., Karlsruhe Inst. of Tech., Germany': ('Inst. of Astroparticle Phys., Karlsruhe Inst. of Tech., Germany', 'Karlsruhe Institute of Technology'),
    'Inst. of Phys., Academia Sinica, Taiwan': ('Inst. of Phys., Academia Sinica, Taiwan', 'Academia Sinica'),
    'Institute of Physics, Academia Sinica': ('Institute of Physics, Academia Sinica', 'Academia Sinica'),
    'TU Wien, Austria': ('TU Wien, Austria', 'TU Wien'),
    'カブリIPMU': ('カブリIPMU', '東京大学カブリ数物連携宇宙研究機構'),
    'カブリ数物': ('カブリ数物', '東京大学カブリ数物連携宇宙研究機構'),
    'カルテク': ('カルテク', 'California Institute of Technology'),
    'ニューヨーク大 量子科学計算センター': ('ニューヨーク大 量子科学計算センター', 'ニューヨーク大学'),
    'ハーバード大学': ('ハーバード大学', 'ハーバード大学'),
    'パリ高等師範学校': ('パリ高等師範学校', '高等師範学校（パリ）'),
    'ボルドー大': ('ボルドー大', 'ボルドー大学'),
    'マギル大': ('マギル大', 'マギル大学'),
}


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
        if raw in SPECIAL_AFFILIATIONS:
            alias, official = SPECIAL_AFFILIATIONS[raw]
            return alias, official, ''
        if 'KEK' in raw:
            return 'KEK', '高エネルギー加速器研究機構', ''
        # 連名表記は先頭の所属だけを機関集計に採用する。
        first = re.split(r'[,，]', raw, maxsplit=1)[0].strip()
        if first != raw:
            return self.resolve(first)
        if raw in {'所属なし', 'N/A', '自宅'}:
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
                       for (raw, alias, reason), pids in unresolved_affs.items()
                       if raw]
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
未解決には対応表未登録、所属記号の欠落、自宅等の機関名がない表記を含みます。「無所属」は所属として集計しています。
未登録の全表記について公式名称の調査が完了したわけではありません。推測で機関を割り当てていません。

全講演は主領域の [CSV](areas/) に1行ずつ保存しています。正式機関名の重複を畳み、畳む前の原所属は `presenter_affiliation_all_raw` と `presentations.jsonl` に保持しています。
[未解決所属一覧](unresolved_affiliations.csv)、[未解決登壇者一覧](unresolved_presenters.csv)、[監査記録](audit.csv)から根拠を確認できます。
機関名の根拠URLは [対応表](../data/affiliation_aliases.csv) に保存しています。

{summary['coverage_check']} ランキング・最終報告書を生成しました。
'''
    Path('output/extraction_summary.md').write_text(text, encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('inputs','area_counts')},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
