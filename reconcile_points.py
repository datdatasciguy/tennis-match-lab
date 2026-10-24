import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from clean import load_data

FIELDS = ("serve_pts", "return_pts", "return_pts_won")

def point_totals(folder, tour, matches, match_id=None, exclude_single_letter=False):
    totals = defaultdict(Counter)
    audit = Counter()
    paths = sorted(Path(folder).glob(f"charting-{tour}-points-*.csv"))
    if not paths:
        raise FileNotFoundError("No point files for this tour; download with --include-points")
    for path in paths:
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                audit["point_rows"] += 1
                if match_id and row["match_id"] != match_id:
                    audit["points_outside_selection"] += 1
                    continue
                match = matches.get(row["match_id"])
                if match is None:
                    audit["points_without_usable_metadata"] += 1
                    continue
                sequence = row["2nd"].strip() or row["1st"].strip()
                if sequence in {"S", "R"}:
                    audit["single_letter_S_R_rows"] += 1
                    if exclude_single_letter:
                        audit["excluded_single_letter_S_R_rows"] += 1
                        continue
                if row["Svr"] not in {"1", "2"} or row["PtWinner"] not in {"1", "2"}:
                    audit["invalid_server_or_winner"] += 1
                    continue
                server = int(row["Svr"])
                winner = int(row["PtWinner"])
                players = (match["Player 1"], match["Player 2"])
                serving_player = players[server - 1]
                returning_player = players[2 - server]
                totals[(row["match_id"], serving_player)]["serve_pts"] += 1
                totals[(row["match_id"], returning_player)]["return_pts"] += 1
                if winner != server:
                    totals[(row["match_id"], returning_player)]["return_pts_won"] += 1
                audit["usable_point_rows"] += 1
    return totals, dict(audit)

def reconcile(folder, tour="m", match_id=None, max_examples=8,
              exclude_single_letter=False):
    if tour not in {"m", "w"}:
        raise ValueError("Tour must be m or w")
    if max_examples < 0:
        raise ValueError("Max examples cannot be negative")
    matches, overview, metadata_audit = load_data(folder, tour)
    if match_id:
        matches = {match_id: matches[match_id]} if match_id in matches else {}
        overview = [row for row in overview if row["match_id"] == match_id]
    totals, point_audit = point_totals(folder, tour, matches, match_id,
                                      exclude_single_letter)
    summary = Counter()
    field_mismatches = Counter()
    field_directions = Counter()
    largest_differences = Counter()
    mismatched_matches = set()
    examples = []
    for row in overview:
        key = row["match_id"], row["player"]
        summary["overview_rows"] += 1
        if key not in totals:
            summary["rows_without_points"] += 1
            continue
        difference = {field: totals[key][field] - int(row[field]) for field in FIELDS}
        if any(difference.values()):
            summary["mismatched_rows"] += 1
            mismatched_matches.add(key[0])
            for field, value in difference.items():
                if value:
                    field_mismatches[field] += 1
                    direction = "points_higher" if value > 0 else "overview_higher"
                    field_directions[f"{field}_{direction}"] += 1
                    largest_differences[field] = max(largest_differences[field], abs(value))
            if len(examples) < max_examples:
                examples.append({"match_id": key[0], "player": key[1],
                                 "point_minus_overview": difference})
        else:
            summary["matching_rows"] += 1
    summary["mismatched_matches"] = len(mismatched_matches)
    return {"tour": tour, "match_id": match_id,
            "exclude_single_letter_S_R": exclude_single_letter,
            "summary": dict(summary),
            "field_mismatches": dict(field_mismatches),
            "field_directions": dict(field_directions),
            "largest_absolute_differences": dict(largest_differences),
            "examples": examples,
            "point_audit": point_audit, "metadata_audit": metadata_audit}

def main():
    parser = argparse.ArgumentParser(
        description="Compare raw point counts with overview totals.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--tour", choices=("m", "w"), default="m")
    parser.add_argument("--match-id")
    parser.add_argument("--max-examples", type=int, default=8)
    parser.add_argument("--exclude-single-letter", action="store_true",
                        help="Compare without point rows coded only S or R")
    args = parser.parse_args()
    print(json.dumps(reconcile(args.folder, args.tour, args.match_id,
                               args.max_examples, args.exclude_single_letter), indent=2))

if __name__ == "__main__":
    main()
