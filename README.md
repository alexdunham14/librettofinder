# Libretto Finder

Where to find an opera libretto with the original and an English translation
side by side. The list is by opera, and the answer for each opera is a link.

Side by side is the whole point: a translation on its own is listed too, but
marked as such, because those are the operas where a side-by-side version
still needs to be built.

## Definition of done

- A static page listing every known libretto link, grouped by composer and
  opera, with a search box, a "side by side only" filter that is on by default,
  and a translation-language filter.
- Every link paired with a Wayback Machine snapshot. Sites that host libretti
  die: rwagner.net is already gone and survives only in the archive.
- Seed scripts that rebuild the bulk entries from the big sources in one
  command each. Hand-found links are added with one command or a GitHub
  issue form.

Not in scope: building new side-by-side texts. That is a separate, per-opera
job and only possible with public-domain translations.

## Adding a link by hand

```
./add URL --opera "Les Troyens" --composer "Hector Berlioz" --languages fr,en --side-by-side --note "scanned vocal score with facing translation"
```

From a phone: open a new issue using the "Add a libretto link" template.

## Seeds

```
./seed/librettoarchive.py > seed/out/librettoarchive.json
./seed/rwagner.py        > seed/out/rwagner.json
./seed/operaguide.py     > seed/out/operaguide.json   # ~515 polite fetches, a few minutes
./merge seed/out/*.json
```

`merge` is idempotent: entries are keyed by id, so rerunning a seed updates
rather than duplicates.

## Archiving

Seeds record the Wayback "latest snapshot" link. `./wayback` walks entries
that do not yet have a dated snapshot and asks the Wayback Machine to save
each one, slowly, because archive.org rate-limits saves. Run it in the
background and let it finish on its own. Private local copies go under
`archive/`, which is gitignored.

## Layout

- `libretti.json`: the data. One object per link.
- `index.html`, `styles.css`, `app.js`: the site. No build step.
- `data.py`: shared helpers (load, save, merge, wayback, snapshot).
- `add`, `merge`, `wayback`: the three commands.
- `seed/`: one script per bulk source.
