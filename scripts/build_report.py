"""領域別CSVから全体・領域別の機関ランキングを作成する。"""
import csv
import json
from collections import Counter
from pathlib import Path


def area_sort_key(path):
    name = path.stem
    if name.startswith("area") and name[4:].isdigit():
        return (0, int(name[4:]))
    order = {"particle_theory": 20, "particle_experiment": 21,
             "nuclear_theory": 22, "nuclear_experiment": 23,
             "cosmic_physics": 24, "beam_physics": 25,
             "computational_physics": 26, "cross_area": 27}
    return (1, order.get(name, 99), name)


def load_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_json_field(row, key):
    try:
        value = json.loads(row.get(key, "[]"))
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def ranking(rows):
    counts = Counter()
    for row in rows:
        for official in set(x for x in parse_json_field(row, "affiliation_official") if x):
            counts[official] += 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    result, previous, rank = [], None, 0
    for index, (name, count) in enumerate(ordered, 1):
        if count != previous:
            rank, previous = index, count
        result.append({"rank": rank, "official_name": name, "count": count})
    return result


def area_stats(rows):
    detections = Counter(row.get("presenter_detection", "") for row in rows)
    return {
        "presentation_count": len(rows),
        "presenter_detection": dict(detections),
        "resolved_presentations": sum(row.get("status") == "resolved" for row in rows),
        "unresolved_presenters": sum("unresolved_presenter" in row.get("status", "") for row in rows),
        "unresolved_affiliations": sum("unresolved_affiliation" in row.get("status", "") for row in rows),
        "ranking": ranking(rows),
    }


def pct(count, denominator):
    return f"{100 * count / denominator:.2f}%" if denominator else "0.00%"


def add_stats(lines, label, stats):
    lines.extend([f"### {label}", "", f"対象講演数：{stats['presentation_count']}、所属判定済み：{stats['resolved_presentations']}、所属未解決：{stats['unresolved_affiliations']}、登壇者未解決：{stats['unresolved_presenters']}。", "登壇者判定：" + "、".join(f"{key} {stats['presenter_detection'].get(key, 0)}件" for key in ("explicit", "inferred_first_author", "single_author", "unresolved")) + "。", "", "| 順位 | 正式機関名 | 講演件数 | 割合 |", "| ---: | --- | ---: | ---: |"])
    for item in stats["ranking"][:20]:
        lines.append(f"| {item['rank']} | {item['official_name']} | {item['count']} | {pct(item['count'], stats['presentation_count'])} |")
    if not stats["ranking"]:
        lines.append("| - | 該当なし | 0 | 0.00% |")
    lines.append("")


def main():
    paths = sorted(Path("output/areas").glob("*.csv"), key=area_sort_key)
    if not paths:
        raise SystemExit("output/areas/*.csv がありません。先に normalize_affiliations.py を実行してください。")
    area_rows = [(path, load_rows(path)) for path in paths]
    all_rows, seen = [], set()
    for path, rows in area_rows:
        for row in rows:
            pid = row["presentation_id"]
            if pid in seen:
                raise ValueError(f"領域別CSV間で講演が重複しています: {pid}")
            seen.add(pid)
            all_rows.append(row)
    overall = area_stats(all_rows)
    areas = {path.stem: area_stats(rows) for path, rows in area_rows}
    summary_path = Path("output/extraction_summary.json")
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    lines = ["# 第81回日本物理学会年次大会（2026年）登壇者所属ランキング（暫定版）", "", "公開された領域別プログラムHTMLをもとに、登壇者の所属機関を講演単位で集計しました。", "大会WEBプログラム：<https://onsite.gakkai-web.net/jps/jps_search/2026au/index.html>", "領域別プログラム：<https://jps2026a.gakkai-web.net/data/html/program.html>", "", "同じ人が複数講演で登壇する場合は講演ごとに数えています。1講演に複数の所属機関がある場合は各機関に1件ずつ加算するため、機関別件数の合計は講演数を超えることがあります。割合の分母は各範囲の対象講演数です。", "合同講演は重複排除し、先頭掲載領域（主領域）にのみ帰属させています。筆頭著者推定は登壇者確認済みを意味しません。", ""]
    add_stats(lines, "全体", overall)
    for path, rows in area_rows:
        add_stats(lines, rows[0].get("area_name") or path.stem if rows else path.stem, areas[path.stem])
    lines.extend(["## 注意事項", "", f"暫定版の対象講演数は{overall['presentation_count']}件です。所属未解決講演は分母に含め、機関へ割り当てていません。未解決ケースと除外・重複の詳細は監査記録で管理しています。", "", f"抽出サマリー：対象{summary.get('target_presentations', overall['presentation_count'])}講演、所属判定済み{summary.get('fully_resolved', overall['resolved_presentations'])}講演。"])
    Path("output/report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path("output/ranking.json").write_text(json.dumps({"overall": overall, "areas": areas}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"全体{len(all_rows)}講演、{len(areas)}領域のランキングを output/report.md に出力しました。")


if __name__ == "__main__":
    main()
