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

def compare(folder, players, tour="m", surface=None, before=None):
    if tour not in {"m", "w"}:
        raise ValueError("Tour must be m or w")
    if before:
        datetime.strptime(before, "%Y%m%d")
    matches, rows, audit = load_data(folder, tour)

    # Filter matches for each player
    selected = {player: [] for player in players}
    for row in rows:
        player = row["player"]
        if player not in selected:
            continue
        match = matches[row["match_id"]]
        if surface and match["Surface"].casefold() != surface.casefold():
            continue
        if before and match["Date"] >= before:
            continue
        selected[player].append(row)
    summaries = {player: summarize(player_rows) for player, player_rows in selected.items()}
    return {"players": summaries, "audit": audit}

def main():
    # Arguments
    parser = argparse.ArgumentParser(description="Compare players in the charted-match sample.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("players", nargs="+")
    parser.add_argument("--tour", choices=["m", "w"], default="m")
    parser.add_argument("--surface")
    parser.add_argument("--before", help="Exclusive date cutoff, YYYYMMDD")
    args = parser.parse_args()
    result = compare(args.folder, args.players, args.tour, args.surface, args.before)
    print(json.dumps(result, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
