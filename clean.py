import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def valid_metadata(row):
    if None in row or any(value is None for value in row.values()):
        return False
    try:
        datetime.strptime(row["Date"], "%Y%m%d")
    except ValueError:
        return False
    return (len(row["Date"]) == 8 and row["Date"] == row["match_id"][:8]
            and row["Surface"] in {"Hard", "Clay", "Grass", "Carpet"}
            and len(row["Player 1"]) > 1 and len(row["Player 2"]) > 1)


def unique_rows(rows, key, audit, label):
    grouped = defaultdict(list)
    for row in rows:
        grouped[key(row)].append(row)
    accepted, conflicts = {}, set()
    for identity, group in grouped.items():
        if any(row != group[0] for row in group[1:]):
            conflicts.add(identity)
        else:
            accepted[identity] = group[0]
            audit[label + "_identical_duplicates_removed"] += len(group) - 1
    audit[label + "_conflicting_keys"] = len(conflicts)
    return accepted, conflicts


def load_data(folder, tour):
    folder = Path(folder)
    audit = Counter()
    raw = read_csv(folder / f"charting-{tour}-matches.csv")
    audit["metadata_rows"] = len(raw)
    valid = [row for row in raw if valid_metadata(row)]
    audit["invalid_metadata_rows"] = len(raw) - len(valid)
    matches, conflicts = unique_rows(valid, lambda r: r["match_id"], audit, "metadata")
    totals = [row for row in read_csv(folder / f"charting-{tour}-stats-Overview.csv")
              if row["set"] == "Total"]
    audit["overview_total_rows"] = len(totals)
    stats, stat_conflicts = unique_rows(
        totals, lambda r: (r["match_id"], r["player"]), audit, "overview")
    excluded = set(conflicts) | {key[0] for key in stat_conflicts}
    for match_id in excluded:
        matches.pop(match_id, None)
    usable = []
    for (match_id, player), row in stats.items():
        if match_id not in matches:
            audit["overview_rows_without_usable_metadata"] += 1
        elif player not in {matches[match_id]["Player 1"], matches[match_id]["Player 2"]}:
            audit["overview_player_mismatches"] += 1
        else:
            usable.append(row)
    audit["usable_metadata_matches"] = len(matches)
    audit["usable_overview_rows"] = len(usable)
    return matches, usable, dict(audit)
