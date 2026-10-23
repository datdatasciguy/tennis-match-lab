import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Common shot codes in the Match Charting Project quick-start guide.
SHOT_CODES = set("fbsrvlom")
OTHER_CODES = set("ndwxyu")
SHOT_NAMES = {
    "f": "forehand", "b": "backhand", "s": "backhand_slice",
    "r": "forehand_slice", "v": "volley", "l": "forehand_lob",
    "m": "backhand_lob", "o": "overhead",
}
SERVE_PREFIX = re.compile(r"^[A-Za-z]*[456]")

def point_features(row):
    first = row["1st"].strip()
    second = row["2nd"].strip()
    sequence = second or first
    prefix = SERVE_PREFIX.match(sequence)
    if not prefix:
        return None
    coded = sequence[prefix.end():]
    shots = [symbol for symbol in coded if symbol in SHOT_CODES]
    unclassified = sorted({symbol for symbol in coded if symbol.isalpha()
                           and symbol not in SHOT_CODES | OTHER_CODES})
    return {
        "match_id": row["match_id"],
        "point": int(row["Pt"]),
        "server": int(row["Svr"]),
        "winner": int(row["PtWinner"]),
        "serve_number": 2 if second else 1,
        "serve_direction": sequence[prefix.end() - 1],
        "coded_shots": len(shots),
        "return_shot": SHOT_NAMES[shots[0]] if shots else None,
        "forehands": sum(shot in {"f", "r", "l"} for shot in shots),
        "backhands": sum(shot in {"b", "s", "m"} for shot in shots),
        "other_shots": sum(shot in {"v", "o"} for shot in shots),
        "unclassified_codes": unclassified,
        "ending": next((kind for mark, kind in (("*", "winner"),
                       ("#", "forced_error"), ("@", "unforced_error"))
                       if mark in coded), None),
    }

def extract(folder, tour, match_id=None, max_points=None, output=None):
    if tour not in {"m", "w"}:
        raise ValueError("Tour must be m or w")
    if max_points is not None and max_points < 1:
        raise ValueError("Max points must be positive")
    paths = sorted(Path(folder).glob(f"charting-{tour}-points-*.csv"))
    if not paths:
        raise FileNotFoundError("No point files for this tour")
    audit = Counter()
    stream = open(output, "x", encoding="utf-8") if output else sys.stdout
    try:
        for path in paths:
            with path.open(encoding="utf-8-sig", newline="") as source:
                for row in csv.DictReader(source):
                    if match_id and row["match_id"] != match_id:
                        continue
                    audit["selected_rows"] += 1
                    try:
                        feature = point_features(row)
                    except (KeyError, TypeError, ValueError):
                        feature = None
                    if (feature is None or feature["server"] not in {1, 2}
                            or feature["winner"] not in {1, 2}):
                        audit["unparsed_rows"] += 1
                        continue
                    stream.write(json.dumps(feature) + "\n")
                    audit["written_rows"] += 1
                    if feature["unclassified_codes"]:
                        audit["rows_with_unclassified_codes"] += 1
                    if max_points and audit["written_rows"] >= max_points:
                        return dict(audit)
    finally:
        if output:
            stream.close()
    return dict(audit)

def main():
    parser = argparse.ArgumentParser(description="Stream coded point features as JSON Lines.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--tour", choices=("m", "w"), default="m")
    parser.add_argument("--match-id")
    parser.add_argument("--max-points", type=int)
    parser.add_argument("--output", type=Path, help="New JSONL file; never overwrites")
    args = parser.parse_args()
    audit = extract(args.folder, args.tour, args.match_id, args.max_points, args.output)
    print(json.dumps({"audit": audit}), file=sys.stderr)

if __name__ == "__main__":
    main()
