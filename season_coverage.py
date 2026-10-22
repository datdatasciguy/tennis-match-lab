import argparse
import json
from collections import defaultdict
from pathlib import Path

from clean import load_data
from compare import filter_matches, normalized_surfaces

def coverage_row(matches, stats):
    counted = [stats[match["match_id"]] for match in matches if match["match_id"] in stats]
    charted = len(matches)
    return {
        "charted_matches": charted,
        "matches_with_stats": len(counted),
        "missing_stats": charted - len(counted),
        "stats_coverage": len(counted) / charted if charted else None,
        "serve_points": sum(int(row["serve_pts"]) for row in counted),
        "return_points": sum(int(row["return_pts"]) for row in counted),
    }

def season_coverage(folder, players, tour="m", surface=None, from_date=None, before=None):
    if tour not in {"m", "w"}:
        raise ValueError("Tour must be m or w")
    if not players or len(set(players)) != len(players):
        raise ValueError("Choose distinct player names")
    matches, rows, audit = load_data(folder, tour)
    matches = filter_matches(matches, surface, from_date, before)
    stats = {(row["match_id"], row["player"]): row for row in rows if row["match_id"] in matches}
    reports = {}
    for player in players:
        selected = [match for match in matches.values()
                    if player in {match["Player 1"], match["Player 2"]}]
        player_stats = {match_id: row for (match_id, name), row in stats.items() if name == player}
        groups = defaultdict(list)
        for match in selected:
            groups[(match["Date"][:4], match["Surface"])].append(match)
        reports[player] = {
            "total": coverage_row(selected, player_stats),
            "seasons": [
                {"season": season, "surface": court, **coverage_row(group, player_stats)}
                for (season, court), group in sorted(groups.items())
            ],
        }
    return {
        "filters": {"tour": tour, "surfaces": sorted(normalized_surfaces(surface)) if surface else None,
                    "from_date": from_date, "before": before},
        "players": reports,
        "audit": audit,
    }

def format_markdown(report):
    lines = [
        "| Player | Season | Surface | Charted | With stats | Missing | Coverage | Serve pts | Return pts |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for player, data in report["players"].items():
        safe_player = player.replace("|", "\\|")
        for row in [*data["seasons"], {"season": "Total", "surface": "All", **data["total"]}]:
            coverage = "n/a" if row["stats_coverage"] is None else f"{row['stats_coverage']:.1%}"
            lines.append(
                f"| {safe_player} | {row['season']} | {row['surface']} | "
                f"{row['charted_matches']} | {row['matches_with_stats']} | {row['missing_stats']} | "
                f"{coverage} | {row['serve_points']:,} | {row['return_points']:,} |"
            )
    lines.append("\nCharted means matches retained after metadata and conflict checks. "
                 "Stats coverage is the share with a usable player overview row.")
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Show charted-match coverage by season and surface.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("players", nargs="+")
    parser.add_argument("--tour", choices=["m", "w"], default="m")
    parser.add_argument("--surface", action="append", help="Repeat to include multiple surfaces")
    parser.add_argument("--from-date", help="Inclusive start date, YYYYMMDD")
    parser.add_argument("--before", help="Exclusive date cutoff, YYYYMMDD")
    parser.add_argument("--markdown", action="store_true", help="Print a readable coverage table")
    args = parser.parse_args()
    try:
        report = season_coverage(args.folder, args.players, args.tour,
                                 args.surface, args.from_date, args.before)
    except ValueError as error:
        parser.exit(2, f"{error}\n")
    print(format_markdown(report) if args.markdown else json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
