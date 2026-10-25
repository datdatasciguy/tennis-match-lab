import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from clean import load_data
from compare import filter_matches, normalized_surfaces, summarize
from point_features import point_features

FOREHAND_RETURNS = {"forehand", "forehand_slice", "forehand_lob"}
BACKHAND_RETURNS = {"backhand", "backhand_slice", "backhand_lob"}

def rate(numerator, denominator, minimum):
    return numerator / denominator if denominator >= minimum else None

def point_samples(folder, tour, matches, players):
    samples = {player: Counter() for player in players}
    audit = Counter()
    paths = sorted(Path(folder).glob(f"charting-{tour}-points-*.csv"))
    if not paths:
        raise FileNotFoundError("No point files for this tour; download with --include-points")
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                match = matches.get(row["match_id"])
                if match is None:
                    continue
                selected = [name for name in (match["Player 1"], match["Player 2"])
                            if name in samples]
                if not selected:
                    continue
                audit["selected_point_rows"] += 1
                for name in selected:
                    samples[name]["charted_point_rows"] += 1
                try:
                    feature = point_features(row)
                except (KeyError, TypeError, ValueError):
                    feature = None
                if (feature is None or feature["server"] not in {1, 2}
                        or feature["winner"] not in {1, 2}):
                    audit["unparsed_point_rows"] += 1
                    for name in selected:
                        samples[name]["unparsed_point_rows"] += 1
                    continue
                if feature["unclassified_codes"]:
                    audit["unclassified_point_rows"] += 1
                    for name in selected:
                        samples[name]["unclassified_point_rows"] += 1
                    continue
                returner = match[f"Player {3 - feature['server']}"]
                for name in selected:
                    sample = samples[name]
                    sample["coded_points"] += 1
                    sample["coded_shots"] += feature["coded_shots"]
                    sample["short_points"] += feature["coded_shots"] <= 2
                if returner in samples and feature["return_shot"]:
                    sample = samples[returner]
                    sample["charted_returns"] += 1
                    sample["forehand_returns"] += feature["return_shot"] in FOREHAND_RETURNS
                    sample["backhand_returns"] += feature["return_shot"] in BACKHAND_RETURNS
                audit["usable_point_rows"] += 1
    return samples, dict(audit)

def build_vectors(folder, players, tour="m", surface=None, from_date=None,
                  before=None, minimum=30):
    if tour not in {"m", "w"}:
        raise ValueError("Tour must be m or w")
    if minimum < 1:
        raise ValueError("Minimum must be positive")
    if not players or len(players) != len(set(players)):
        raise ValueError("Choose distinct player names")
    matches, overview, source_audit = load_data(folder, tour)
    matches = filter_matches(matches, surface, from_date, before)
    selected = set(players)
    rows = {name: [] for name in players}
    for row in overview:
        if row["match_id"] in matches and row["player"] in selected:
            rows[row["player"]].append(row)
    samples, point_audit = point_samples(folder, tour, matches, players)
    vectors = {}
    for name in players:
        overview_stats = summarize(rows[name]) if rows[name] else None
        sample = samples[name]
        coded = sample["coded_points"]
        returns = sample["charted_returns"]
        vectors[name] = {
            "overview_matches": len(rows[name]),
            "overview_serve_points": overview_stats["serve_points"] if overview_stats else 0,
            "overview_return_points": overview_stats["return_points"] if overview_stats else 0,
            "ace_rate": overview_stats["ace_rate"] if overview_stats else None,
            "first_serve_in": overview_stats["first_serve_in"] if overview_stats else None,
            "return_points_won": overview_stats["return_points_won"] if overview_stats else None,
            "charted_point_rows": sample["charted_point_rows"],
            "coded_points": coded,
            "unparsed_point_rows": sample["unparsed_point_rows"],
            "unclassified_point_rows": sample["unclassified_point_rows"],
            "charted_returns": returns,
            "mean_coded_shots_after_serve": rate(sample["coded_shots"], coded, minimum),
            "share_with_two_or_fewer_coded_shots": rate(sample["short_points"], coded, minimum),
            "forehand_return_share": rate(sample["forehand_returns"], returns, minimum),
            "backhand_return_share": rate(sample["backhand_returns"], returns, minimum),
            "missing": (["no_overview_stats"] if not overview_stats else [])
                       + (["too_few_coded_points"] if coded < minimum else [])
                       + (["too_few_charted_returns"] if returns < minimum else []),
        }
    return {
        "filters": {"tour": tour,
                    "surfaces": sorted(normalized_surfaces(surface)) if surface else None,
                    "from_date": from_date, "before": before},
        "minimum": minimum,
        "metadata_matches": len(matches),
        "players": vectors,
        "point_audit": point_audit,
        "source_audit": source_audit,
    }

def main():
    parser = argparse.ArgumentParser(description="Build sample-aware player style vectors.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("players", nargs="+")
    parser.add_argument("--tour", choices=("m", "w"), default="m")
    parser.add_argument("--surface", action="append")
    parser.add_argument("--from-date")
    parser.add_argument("--before")
    parser.add_argument("--minimum", type=int, default=30)
    args = parser.parse_args()
    result = build_vectors(args.folder, args.players, args.tour, args.surface,
                           args.from_date, args.before, args.minimum)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
