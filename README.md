# Tennis Match Lab

Some tools for comparing tennis players and poking around in match data.

The first thing I wanted to look at was serve and return numbers. Who gets more
free points? Who wins more on return? How does that change on grass versus clay?
Nothing settles a tennis debate, but this at least gives us something to look at.

## Try a comparison

Python 3.11+. No extra packages needed for the scripts.

```bash
python download.py
python compare.py data/raw/<source-commit> "Roger Federer" "Rafael Nadal" --surface Grass
```

The download prints the folder to use in place of `<source-commit>`. Add
`--include-points` if you also want the point-by-point files; the full snapshot
used here is about 494 MB.

You can use `--tour w` for the women's data. For a 2010s grass-and-clay sample:

```bash
python compare.py data/raw/<source-commit> "Roger Federer" "Rafael Nadal" --surface Grass --surface Clay --from-date 20100101 --before 20200101
```

Repeat `--surface` to include more than one. `--from-date` includes its date;
`--before` stops just short of its date. The output shows how many charted matches
passed the filters, how many have player stats, and each player's match and point
counts. These samples can be uneven, so check the counts before comparing rates.

For a feel for how much the pooled rates move when matches are resampled:

```bash
python compare.py data/raw/<source-commit> "Roger Federer" "Rafael Nadal" --surface Grass --bootstrap 2000 --seed 42 --markdown
```

The table puts each player's match and point counts beside all seven rates and
their 95% intervals. Leave off `--markdown` for JSON output, where the optional
`intervals` field also gives the number of usable draws. The calculation
resamples whole charted matches, then recalculates each pooled point rate.
Fewer than five matches get no interval. This shows variation within the
selected charted sample; it does not fix uneven opponent or match coverage
or describe a player's full career.

For a compact local browser view of the same numbers:

```bash
python compare.py data/raw/<source-commit> "Roger Federer" "Rafael Nadal" --surface Grass --from-date 20100101 --before 20200101 --html data/grass-comparison.html
```

Open the saved HTML file in a browser. It keeps each player's sample size beside
the rates and shows the selected snapshot and filters. The file stays under the
ignored `data/` folder; no raw match rows are written into it.

## Check the sample coverage

Before reading a rate comparison, see where the charted matches and usable stats
actually fall:

```bash
python season_coverage.py data/raw/<source-commit> "Roger Federer" "Rafael Nadal" --surface Grass --markdown
```

The table groups matches by season and surface. It shows missing player stats
and serve/return point counts, so a sparse year does not disappear inside a
pooled rate. These are matches in the charting snapshot, not all matches those
players played. A missing season means no charted match passed your filters.

The [player comparison notebook](notebooks/player_comparison.ipynb) has a Federer
and Nadal example. To get the same data it used:

```bash
python download.py --commit 1813a1309b7ed7ebf1c7e884b32bf675d00e4edf
```

Install Jupyter if you'd like to run the notebook. `verify.py` can check a
download if something looks off.

## Explore charted points

If you downloaded with `--include-points`, stream point features from the raw
shot codes without loading the full snapshot into memory:

```bash
python point_features.py data/raw/<source-commit> --match-id 20191124-M-Davis_Cup_Finals-F-Rafael_Nadal-Denis_Shapovalov --max-points 5
python point_features.py data/raw/<source-commit> --output data/point-features.jsonl
```

The first command prints five point rows; the second writes the full men's
snapshot to a new ignored JSONL file. Add `--tour w` for the women's files.
Each row includes serve number and direction, coded shot counts and types,
the return shot, and the point ending where marked. `coded_shots` counts only
the common shot symbols in the [source's charting guide](https://www.tennisabstract.com/blog/2015/09/23/the-match-charting-project-quick-start-guide/); check
`unclassified_codes` before treating it as a complete rally length. The script
prints skipped and partial-parse counts to stderr and never overwrites an
existing output file. Keep the derived point rows local under `data/`.

To check whether those point rows agree with the source's match summaries:

```bash
python reconcile_points.py data/raw/<source-commit>
python reconcile_points.py data/raw/<source-commit> --exclude-single-letter
```

The report compares serve points, return points, and return points won for each
player, with a few example gaps. The second command leaves out points coded
only `S` or `R` to show how much those rows affect agreement. It is a diagnostic
view, not a correction to the source. Add `--tour w` or `--match-id` to narrow
the check. The pinned snapshot still has differences after that exclusion, so
check the report before using match-level point features as exact totals.

## First style view

The style view combines pooled overview rates with a few features from points
whose shot codes the extractor recognizes:

```bash
python style_vectors.py data/raw/<source-commit> "Roger Federer" "Rafael Nadal" --surface Grass --from-date 20100101 --before 20200101
```

It shows each player's overview matches and point counts separately from the
usable shot-coded point sample. The shot view includes average coded shots after
the serve, the share of short coded points, and forehand/backhand return mix.
Unparsed and unfamiliar-code rows stay visible as counts. A rate is `null`
when its own denominator is below 30; change that display cutoff with
`--minimum`. These are descriptive charted-sample features, not complete rally
lengths or a rating of player ability. Run the reconciliation above before
assuming point rows and match summaries agree for a particular sample.

## A couple of details

The rates come from total points, rather than averaging match percentages.
You'll see the match and point counts alongside them. The loader also handles
duplicate records so a match doesn't accidentally count twice.

These are volunteer-charted matches, not every match a player has played. The
Federer/Nadal example compares their grass matches against all opponents, not
just against each other. It's a starting point for exploring, not a ranking of
who's better.

Next I'd like to look at playing styles and some simple matchup models.

## Data

Thanks to [Jeff Sackmann and the Match Charting Project](https://github.com/JeffSackmann/tennis_MatchChartingProject)
for the data. It's licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/),
which also applies to the data-derived notebook results. Downloads stay in the
ignored `data/` folder. The Python code is MIT licensed.
