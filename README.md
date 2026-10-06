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

The [player comparison notebook](notebooks/player_comparison.ipynb) has a Federer
and Nadal example. To get the same data it used:

```bash
python download.py --commit 1813a1309b7ed7ebf1c7e884b32bf675d00e4edf
```

Install Jupyter if you'd like to run the notebook. `verify.py` can check a
download if something looks off.

## A couple of details

The rates come from total points, rather than averaging match percentages.
You'll see the match and point counts alongside them. The loader also handles
duplicate records so a match doesn't accidentally count twice.

These are volunteer-charted matches, not every match a player has played. The
Federer/Nadal example compares their grass matches against all opponents, not
just against each other. It's a starting point for exploring, not a ranking of
who's better.

Next I'd like to look at playing styles, uncertainty in the numbers, and some
simple matchup models.

## Data

Thanks to [Jeff Sackmann and the Match Charting Project](https://github.com/JeffSackmann/tennis_MatchChartingProject)
for the data. It's licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/),
which also applies to the data-derived notebook results. Downloads stay in the
ignored `data/` folder. The Python code is MIT licensed.
