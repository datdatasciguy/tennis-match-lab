import argparse
import json
from datetime import datetime
from html import escape
from pathlib import Path
from random import Random

from clean import load_data

# Columns used for serve and return rates
STAT_COLUMNS = [
    "serve_pts", "aces", "dfs", "first_in", "first_won", "second_won",
    "return_pts", "return_pts_won", "bk_pts", "bp_saved",
]
RATE_COLUMNS = (
    "ace_rate", "double_fault_rate", "first_serve_in", "first_serve_won",
    "second_serve_won", "return_points_won", "break_points_saved",
)
RATE_LABELS = {
    "ace_rate": "Aces", "double_fault_rate": "Double faults",
    "first_serve_in": "First serves in", "first_serve_won": "First serves won",
    "second_serve_won": "Second serves won",
    "return_points_won": "Return points won",
    "break_points_saved": "Break points saved",
}
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


def percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    weight = position - lower
    if lower == len(ordered) - 1:
        return ordered[lower]
    return ordered[lower] * (1 - weight) + ordered[lower + 1] * weight


def bootstrap_intervals(rows, draws=2000, confidence=0.95, seed=42):
    if draws < 100:
        raise ValueError("Bootstrap draws must be at least 100")
    if not 0 < confidence < 1:
        raise ValueError("Confidence must be between 0 and 1")
    result = {"method": "match bootstrap percentile", "confidence": confidence,
              "draws": draws, "seed": seed, "matches": len(rows), "rates": {}}
    if len(rows) < 5:
        result["note"] = "Fewer than five charted matches; intervals withheld"
        result["rates"] = {name: None for name in RATE_COLUMNS}
        return result

    rng = Random(seed)
    estimates = {name: [] for name in RATE_COLUMNS}
    for _ in range(draws):
        sample = rng.choices(rows, k=len(rows))
        summary = summarize(sample)
        for name in RATE_COLUMNS:
            if summary[name] is not None:
                estimates[name].append(summary[name])

    tail = (1 - confidence) / 2
    for name, values in estimates.items():
        result["rates"][name] = (
            {"low": percentile(values, tail),
             "high": percentile(values, 1 - tail),
             "valid_draws": len(values)} if values else None
        )
    return result


def compare(folder, players, tour="m", surface=None, before=None, from_date=None,
            bootstrap=0, confidence=0.95, seed=42):
    if tour not in {"m", "w"}:
        raise ValueError("Tour must be m or w")
    if bootstrap and bootstrap < 100:
        raise ValueError("Bootstrap draws must be at least 100")
    if bootstrap and not 0 < confidence < 1:
        raise ValueError("Confidence must be between 0 and 1")
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
    if bootstrap:
        for player, player_rows in selected.items():
            summaries[player]["intervals"] = bootstrap_intervals(
                player_rows, bootstrap, confidence, seed)
    return {
        "filters": {"tour": tour, "surfaces": sorted(surfaces) if surfaces else None,
                    "from_date": from_date, "before": before},
        "sample": {"metadata_matches": len(matches),
                   "matches_with_stats": len(matches_with_stats)},
        "players": summaries,
        "audit": audit,
    }

def format_markdown(result):
    # Keep the sample size beside every displayed rate
    players = result["players"]
    headings = []
    for player, values in players.items():
        safe_name = player.replace("|", "\\|")
        headings.append(
            f"{safe_name}<br>{values['matches']} matches, "
            f"{values['serve_points']:,} serve pts, "
            f"{values['return_points']:,} return pts"
        )
    lines = ["| Rate | " + " | ".join(headings) + " |",
             "| --- | " + " | ".join("---" for _ in players) + " |"]
    for name in RATE_COLUMNS:
        cells = []
        for values in players.values():
            point = values[name]
            if point is None:
                cells.append("n/a")
                continue
            cell = f"{point:.1%}"
            intervals = values.get("intervals")
            if intervals:
                bounds = intervals["rates"][name]
                if bounds:
                    cell += f" ({bounds['low']:.1%}–{bounds['high']:.1%})"
                    if bounds["valid_draws"] != intervals["draws"]:
                        cell += f" [{bounds['valid_draws']}/{intervals['draws']} draws]"
                else:
                    cell += " (interval unavailable)"
            cells.append(cell)
        lines.append("| " + RATE_LABELS[name] + " | " + " | ".join(cells) + " |")
    if any("intervals" in values for values in players.values()):
        confidence = next(values["intervals"]["confidence"] for values in players.values()
                          if "intervals" in values)
        lines.append(f"\nParentheses show {confidence:.0%} match-bootstrap intervals.")
    return "\n".join(lines)


def format_html(result, snapshot):
    players = result["players"]
    filters = result["filters"]
    surfaces = ", ".join(filters["surfaces"]) if filters["surfaces"] else "All surfaces"
    dates = f"{filters['from_date'] or 'earliest'} to before {filters['before'] or 'latest'}"
    selection = f"{filters['tour'].upper()} tour · {surfaces} · {dates}"
    headings = ["<th scope='col'>Rate</th>"]
    for player, values in players.items():
        headings.append(
            f"<th scope='col'>{escape(player)}<small>{values['matches']:,} matches · "
            f"{values['serve_points']:,} serve pts · {values['return_points']:,} return pts</small></th>"
        )
    rows = []
    for name in RATE_COLUMNS:
        cells = [f"<th scope='row'>{escape(RATE_LABELS[name])}</th>"]
        for values in players.values():
            point = values[name]
            if point is None:
                cells.append("<td>n/a</td>")
                continue
            cell = f"<strong>{point:.1%}</strong>"
            intervals = values.get("intervals")
            if intervals:
                bounds = intervals["rates"][name]
                if bounds:
                    cell += f"<small>{bounds['low']:.1%}–{bounds['high']:.1%} interval</small>"
                    if bounds["valid_draws"] != intervals["draws"]:
                        cell += f"<small>{bounds['valid_draws']}/{intervals['draws']} usable draws</small>"
                else:
                    cell += "<small>Interval unavailable</small>"
            cells.append(f"<td>{cell}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    interval_note = ""
    if any("intervals" in values for values in players.values()):
        confidence = next(values["intervals"]["confidence"] for values in players.values()
                          if "intervals" in values)
        interval_note = f"<p>Intervals use {confidence:.0%} match-level bootstrap resampling.</p>"
    sample = result["sample"]
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tennis Match Lab · Player comparison</title>
<style>
body {{ margin: 0; background: #f5f7f4; color: #172b24; font: 16px/1.5 system-ui, sans-serif; }}
main {{ max-width: 1040px; margin: 0 auto; padding: 36px 20px 64px; }}
h1 {{ margin-bottom: 4px; font-size: clamp(28px, 5vw, 42px); }}
.intro {{ color: #40584e; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 24px 0; }}
.meta span {{ padding: 10px 14px; border: 1px solid #cbd9ce; border-radius: 8px; background: white; }}
.table-wrap {{ overflow-x: auto; border: 1px solid #cbd9ce; border-radius: 10px; background: white; }}
table {{ width: 100%; border-collapse: collapse; text-align: left; }}
th, td {{ min-width: 130px; padding: 14px; border-bottom: 1px solid #e1e9e2; vertical-align: top; }}
thead th {{ background: #e4eee6; }}
tbody tr:last-child th, tbody tr:last-child td {{ border-bottom: 0; }}
small {{ display: block; color: #4c6557; font-size: 12px; font-weight: normal; }}
.note {{ max-width: 760px; color: #40584e; }}
a {{ color: #145e42; }}
</style>
</head>
<body>
<main>
<h1>Player comparison</h1>
<p class="intro">{escape(selection)}</p>
<div class="meta"><span>Snapshot: {escape(snapshot)}</span><span>{sample['metadata_matches']:,} charted matches in filter</span><span>{sample['matches_with_stats']:,} with usable player stats</span></div>
<div class="table-wrap"><table><thead><tr>{''.join(headings)}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<div class="note">{interval_note}<p>Rates pool points from each player’s charted matches against all opponents. This is not a head-to-head comparison or a ranking. Volunteer charting coverage varies by player and filter.</p>
<p>Data: <a href="https://github.com/JeffSackmann/tennis_MatchChartingProject">Match Charting Project</a> (CC BY-NC-SA 4.0).</p></div>
</main>
</body>
</html>
"""


def main():
    # Arguments
    parser = argparse.ArgumentParser(description="Compare players in the charted-match sample.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("players", nargs="+")
    parser.add_argument("--tour", choices=["m", "w"], default="m")
    parser.add_argument("--surface", action="append", help="Repeat to include multiple surfaces")
    parser.add_argument("--from-date", help="Inclusive start date, YYYYMMDD")
    parser.add_argument("--before", help="Exclusive date cutoff, YYYYMMDD")
    parser.add_argument("--bootstrap", type=int, default=0,
                        help="Match-level resamples for pooled-rate intervals (at least 100)")
    parser.add_argument("--confidence", type=float, default=0.95,
                        help="Interval level when bootstrapping (default: 0.95)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for repeatable intervals (default: 42)")
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument("--markdown", action="store_true",
                              help="Print a comparison table instead of JSON")
    format_group.add_argument("--html", type=Path,
                              help="Save a local HTML comparison to this path")
    args = parser.parse_args()
    try:
        result = compare(args.folder, args.players, args.tour, args.surface,
                         args.before, args.from_date, args.bootstrap,
                         args.confidence, args.seed)
    except ValueError as error:
        parser.exit(2, f"{error}\n")
    if args.html:
        try:
            args.html.parent.mkdir(parents=True, exist_ok=True)
            args.html.write_text(format_html(result, args.folder.name), encoding="utf-8")
        except OSError as error:
            parser.exit(2, f"Could not save HTML: {error}\n")
        print(args.html)
    elif args.markdown:
        print(format_markdown(result))
    else:
        print(json.dumps(result, indent=2, allow_nan=False))

if __name__ == "__main__":
    main()
