import argparse
import json
from datetime import datetime
from pathlib import Path

from clean import load_data

# Columns used for serve and return rates
STAT_COLUMNS = [
    "serve_pts", "aces", "dfs", "first_in", "first_won", "second_won",
    "return_pts", "return_pts_won", "bk_pts", "bp_saved",
]
SURFACES = {name.casefold(): name for name in ("Hard", "Clay", "Grass", "Carpet")}

def checked_date(value, label):
    if value is None:
        return None
    if (not isinstance(value, str) or len(value) != 8
            or not value.isascii() or not value.isdigit()):
        raise ValueError(f"{label} must be a date in YYYYMMDD format")
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as error:
        raise ValueError(f"{label} must be a real date in YYYYMMDD format") from error
    return value

def normalized_surfaces(surface):
    if surface is None:
        return None
    names = [surface] if isinstance(surface, str) else list(surface)
    if not names:
        raise ValueError("Choose at least one surface")
    selected = set()
    for name in names:
        if not isinstance(name, str) or name.casefold() not in SURFACES:
            raise ValueError("Surface must be Hard, Clay, Grass, or Carpet")
        selected.add(SURFACES[name.casefold()])
    return selected

def filter_matches(matches, surface=None, from_date=None, before=None):
    from_date = checked_date(from_date, "From date")
    before = checked_date(before, "Before date")
    if from_date and before and from_date >= before:
        raise ValueError("From date must be earlier than before date")
    surfaces = normalized_surfaces(surface)
    filtered = {}
    for match_id, match in matches.items():
        if surfaces and match["Surface"] not in surfaces:
            continue
        if from_date and match["Date"] < from_date:
            continue
        if before and match["Date"] >= before:
            continue
        filtered[match_id] = match
    return filtered

def rate(numerator, denominator):
    return numerator / denominator if denominator else None

def summarize(rows):
    # Sum points before calculating rates
    totals = {column: sum(int(row[column]) for row in rows) for column in STAT_COLUMNS}
    return {
        "matches": len(rows),
        "serve_points": totals["serve_pts"],
        "return_points": totals["return_pts"],
        "ace_rate": rate(totals["aces"], totals["serve_pts"]),
        "double_fault_rate": rate(totals["dfs"], totals["serve_pts"]),
        "first_serve_in": rate(totals["first_in"], totals["serve_pts"]),
        "first_serve_won": rate(totals["first_won"], totals["first_in"]),
        "second_serve_won": rate(totals["second_won"],
                                 totals["serve_pts"] - totals["first_in"]),
        "return_points_won": rate(totals["return_pts_won"], totals["return_pts"]),
        "break_points_saved": rate(totals["bp_saved"], totals["bk_pts"]),
    }

def compare(folder, players, tour="m", surface=None, before=None, from_date=None):
    if tour not in {"m", "w"}:
        raise ValueError("Tour must be m or w")
    matches, rows, audit = load_data(folder, tour)
    matches = filter_matches(matches, surface, from_date, before)
    surfaces = normalized_surfaces(surface)
    matches_with_stats = {row["match_id"] for row in rows
                          if row["match_id"] in matches}

    # Filter matches for each player
    selected = {player: [] for player in players}
    for row in rows:
        player = row["player"]
        if player not in selected:
            continue
        if row["match_id"] not in matches:
            continue
        selected[player].append(row)
    summaries = {player: summarize(player_rows) for player, player_rows in selected.items()}
    return {
        "filters": {"tour": tour, "surfaces": sorted(surfaces) if surfaces else None,
                    "from_date": from_date, "before": before},
        "sample": {"metadata_matches": len(matches),
                   "matches_with_stats": len(matches_with_stats)},
        "players": summaries,
        "audit": audit,
    }

def main():
    # Arguments
    parser = argparse.ArgumentParser(description="Compare players in the charted-match sample.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("players", nargs="+")
    parser.add_argument("--tour", choices=["m", "w"], default="m")
    parser.add_argument("--surface", action="append", help="Repeat to include multiple surfaces")
    parser.add_argument("--from-date", help="Inclusive start date, YYYYMMDD")
    parser.add_argument("--before", help="Exclusive date cutoff, YYYYMMDD")
    args = parser.parse_args()
    try:
        result = compare(args.folder, args.players, args.tour, args.surface,
                         args.before, args.from_date)
    except ValueError as error:
        parser.exit(2, f"{error}\n")
    print(json.dumps(result, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
