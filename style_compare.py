import argparse
import json
from html import escape
from itertools import combinations
from pathlib import Path

from style_vectors import build_vectors

OVERVIEW_RATES = ("ace_rate", "first_serve_in", "return_points_won")
SHOT_RATES = ("share_with_two_or_fewer_coded_shots", "forehand_return_share")
RATE_LABELS = {
    "ace_rate": "Ace rate",
    "first_serve_in": "First serves in",
    "return_points_won": "Return points won",
    "share_with_two_or_fewer_coded_shots": "Points with at most two coded shots",
    "forehand_return_share": "Forehand share of coded returns",
}

def rate_gaps(left, right, names):
    gaps = []
    missing = []
    for name in names:
        a, b = left[name], right[name]
        if a is None or b is None:
            missing.append(name)
        else:
            gaps.append({"feature": name, "left": a, "right": b,
                         "gap": abs(a - b)})
    return gaps, missing

def compare_styles(vectors, min_matches=10):
    if min_matches < 1:
        raise ValueError("Minimum matches must be positive")
    pairs = []
    for left_name, right_name in combinations(vectors["players"], 2):
        left, right = vectors["players"][left_name], vectors["players"][right_name]
        overview, missing_overview = rate_gaps(left, right, OVERVIEW_RATES)
        shots, missing_shots = rate_gaps(left, right, SHOT_RATES)
        pairs.append({
            "left": left_name, "right": right_name,
            "overview_gap": sum(row["gap"] for row in overview) / len(overview)
                            if len(overview) == len(OVERVIEW_RATES) else None,
            "charted_shot_gap": sum(row["gap"] for row in shots) / len(shots)
                                if len(shots) == len(SHOT_RATES) else None,
            "rate_gaps": sorted(overview + shots, key=lambda row: row["gap"], reverse=True),
            "missing_rates": missing_overview + missing_shots,
            "samples": {
                left_name: {"overview_matches": left["overview_matches"],
                            "coded_points": left["coded_points"],
                            "charted_returns": left["charted_returns"],
                            "flags": left["missing"] + (["few_overview_matches"]
                                                       if left["overview_matches"] < min_matches else [])},
                right_name: {"overview_matches": right["overview_matches"],
                             "coded_points": right["coded_points"],
                             "charted_returns": right["charted_returns"],
                             "flags": right["missing"] + (["few_overview_matches"]
                                                        if right["overview_matches"] < min_matches else [])},
            },
        })
    return {"filters": vectors["filters"], "point_minimum": vectors["minimum"],
            "match_minimum": min_matches, "pairs": pairs,
            "source_audit": vectors["source_audit"], "point_audit": vectors["point_audit"]}

def format_html(result):
    filters = result["filters"]
    surfaces = ", ".join(filters["surfaces"] or []) or "all surfaces"
    period = f"{filters['from_date'] or 'first available'} to {filters['before'] or 'latest available'} (end exclusive)"
    cards = []
    for pair in result["pairs"]:
        names = (pair["left"], pair["right"])
        samples = []
        for name in names:
            counts = pair["samples"][name]
            flags = ", ".join(counts["flags"]) or "none"
            samples.append(f"<li><strong>{escape(name)}</strong>: {counts['overview_matches']:,} overview matches, "
                           f"{counts['coded_points']:,} coded points, {counts['charted_returns']:,} coded returns. "
                           f"Flags: {escape(flags)}</li>")
        rows = []
        for group, features in (("Overview", OVERVIEW_RATES), ("Charted shots", SHOT_RATES)):
            for feature in features:
                rate = next((row for row in pair["rate_gaps"] if row["feature"] == feature), None)
                if rate is None:
                    cells = "<td colspan='3'>Missing rate for at least one player</td>"
                else:
                    gap = rate["gap"] * 100
                    cells = (f"<td>{rate['left']:.1%}</td><td>{rate['right']:.1%}</td>"
                             f"<td>{gap:.1f} pp <span class='bar' style='width:{min(gap, 100):.1f}%'></span></td>")
                rows.append(f"<tr><th scope='row'>{escape(RATE_LABELS[feature])}<small>{group}</small></th>{cells}</tr>")
        overview = "missing" if pair["overview_gap"] is None else f"{pair['overview_gap'] * 100:.1f} pp"
        shots = "missing" if pair["charted_shot_gap"] is None else f"{pair['charted_shot_gap'] * 100:.1f} pp"
        cards.append(f"<section><h2>{escape(names[0])} / {escape(names[1])}</h2>"
                     f"<ul class='samples'>{''.join(samples)}</ul>"
                     f"<p>Average absolute gap: overview <strong>{overview}</strong>; charted shots <strong>{shots}</strong>.</p>"
                     f"<div class='scroll'><table><thead><tr><th>Rate</th><th>{escape(names[0])}</th>"
                     f"<th>{escape(names[1])}</th><th>Absolute gap</th></tr></thead><tbody>"
                     f"{''.join(rows)}</tbody></table></div></section>")
    scope = ("head-to-head matches only" if filters.get("head_to_head")
             else "matches against all opponents")
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Charted tennis style comparison</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:auto;padding:24px;color:#18232d;background:#f6f8f8}}
section{{background:white;padding:20px;margin:24px 0;border:1px solid #d6dfe2;border-radius:10px}}
h1,h2{{line-height:1.2}}.intro{{max-width:75ch}}.samples{{padding-left:22px}}
.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:680px;text-align:left}}
th,td{{border-bottom:1px solid #d6dfe2;padding:10px;vertical-align:top}}td{{min-width:100px}}
th small{{display:block;color:#536572;font-weight:normal}}.bar{{display:block;background:#3d85a4;height:7px;min-width:2px;margin-top:5px}}
</style>
<h1>Charted tennis style comparison</h1>
<p class="intro">{escape(filters['tour'].upper())} tour · {escape(surfaces)} · {escape(period)} · {scope}. Gaps are absolute percentage-point differences in this volunteer-charted sample. Overview and shot-code coverage differ; these numbers do not rank player ability.</p>
<p>Shot rates require at least {result['point_minimum']} coded points or returns; overview samples below {result['match_minimum']} matches are flagged. An average is missing if any rate in that block is unavailable.</p>
{''.join(cards)}
</html>"""

def main():
    parser = argparse.ArgumentParser(description="Compare charted player style rates without hiding sample gaps.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("players", nargs="+")
    parser.add_argument("--tour", choices=("m", "w"), default="m")
    parser.add_argument("--surface", action="append")
    parser.add_argument("--from-date")
    parser.add_argument("--before")
    parser.add_argument("--head-to-head", action="store_true",
                        help="Use only charted matches between exactly two named players")
    parser.add_argument("--minimum", type=int, default=30, help="Minimum coded points or returns for a shot rate")
    parser.add_argument("--min-matches", type=int, default=10, help="Flag smaller overview match samples")
    parser.add_argument("--html", type=Path, help="Save a local HTML report under ignored data/ or outputs/")
    args = parser.parse_args()
    if len(args.players) < 2:
        parser.error("Choose at least two distinct players")
    if args.head_to_head and len(args.players) != 2:
        parser.error("Head-to-head needs exactly two player names")
    try:
        vectors = build_vectors(args.folder, args.players, args.tour, args.surface,
                                args.from_date, args.before, args.minimum, args.head_to_head)
        result = compare_styles(vectors, args.min_matches)
        if args.html:
            output = args.html.resolve()
            repo = Path(__file__).resolve().parent
            if output.is_relative_to(repo) and not any(output.is_relative_to(repo / name)
                                                       for name in ("data", "outputs")):
                raise ValueError("Save HTML under ignored data/ or outputs/, or outside this repo")
            if output.exists():
                raise ValueError("Choose a new HTML path to preserve earlier reports")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(format_html(result), encoding="utf-8")
    except (ValueError, OSError) as error:
        parser.exit(2, f"{error}\n")
    print(args.html if args.html else json.dumps(result, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
