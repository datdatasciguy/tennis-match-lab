import argparse
import json
from itertools import combinations
from pathlib import Path

from style_vectors import build_vectors

OVERVIEW_RATES = ("ace_rate", "first_serve_in", "return_points_won")
SHOT_RATES = ("share_with_two_or_fewer_coded_shots", "forehand_return_share")

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

def main():
    parser = argparse.ArgumentParser(description="Compare charted player style rates without hiding sample gaps.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("players", nargs="+")
    parser.add_argument("--tour", choices=("m", "w"), default="m")
    parser.add_argument("--surface", action="append")
    parser.add_argument("--from-date")
    parser.add_argument("--before")
    parser.add_argument("--minimum", type=int, default=30, help="Minimum coded points or returns for a shot rate")
    parser.add_argument("--min-matches", type=int, default=10, help="Flag smaller overview match samples")
    args = parser.parse_args()
    if len(args.players) < 2:
        parser.error("Choose at least two distinct players")
    try:
        vectors = build_vectors(args.folder, args.players, args.tour, args.surface,
                                args.from_date, args.before, args.minimum)
        result = compare_styles(vectors, args.min_matches)
    except (ValueError, OSError) as error:
        parser.exit(2, f"{error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
