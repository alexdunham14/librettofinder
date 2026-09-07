# Libretto Finder

Where to find an opera libretto with the original and an English translation
side by side. The list is by opera, and the answer for each opera is a link.

Side by side is the whole point: single-language pages are listed too, marked
as the original text or as a translation, because those are the operas where a
side-by-side version still needs to be built.

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
./seed/kareol.py         > seed/out/kareol.json
./seed/librettidopera.py > seed/out/librettidopera.json   # ~335 fetches, Italian only
./seed/opera-arias.py    > seed/out/opera-arias.json      # ~550 fetches, originals + separate English pages
./seed/wikisource-fr.py  > seed/out/wikisource-fr.json    # ~90 fetches, French (mostly Offenbach)
./seed/operaglass.py     > seed/out/operaglass.json       # ~110 Wayback fetches, slow; the site itself is down
./merge seed/out/*.json
```

Scanned bilingual libretti (archive.org, IMSLP, Library of Congress) and
record-label booklets are found by hand, not seeded: archive.org's metadata
mixes libretti with vocal scores and recordings, so each item is checked
before it is added. murashev.com is the same site as librettoarchive.com
(it redirects there) and is not seeded separately.

`merge` is idempotent: entries are keyed by id, so rerunning a seed updates
rather than duplicates. `./merge --prune kareol.es seed/out/kareol.json` also
drops entries of that source the seed no longer produces (after a seed fix).

## Names

Sources spell things their own way: Kareol in Spanish ("Las bodas de Fígaro",
"Piotr Ilich Chaikovski"), opera-guide.ch in German or English. `data.py`
holds three tables that fold them to one form so an opera is one group on the
page: `COMPOSERS` (alias to canonical name), `OPERAS` (per composer, the
source's title to the canonical title; a value can also move a work to the
right composer where Kareol's index misfiles it), and `ORIGINAL` plus
`OPERA_ORIGINAL` (the language the libretto was written in). Every entry gets
`original` (language code or null) and, where the source's title differs,
`listed_as`. Kareol entries list `[original, "es"]`. Seeds and `add` apply the
tables as entries are made; `./normalize` reapplies them to `libretti.json`
after a table change. Idempotent. Ids are built from the names as the source
gives them, so they never change when a table does.

Behind the hand table sits `composer_aliases.json`: every spelling variant
that classicalconcertmap's pipeline (`~/projects/classical-orchestrator`)
knows for a composer already listed here, keyed the way that pipeline keys
them (lower case, accents dropped), pointing at this site's spelling.
`./composers` regenerates it from the pipeline's SQLite database; rerun it
after a merge brings in new composers. Bare surnames are left out so
"Strauss" never picks a Strauss.

## Archiving

Seeds record the Wayback "latest snapshot" link. `./wayback` walks entries
that do not yet have a dated snapshot and asks the Wayback Machine to save
each one, slowly, because archive.org rate-limits saves. Run it in the
background and let it finish on its own. Private local copies go under
`archive/`, which is gitignored.

## Layout

- `libretti.json`: the data. One object per link: opera, composer, languages,
  original, side_by_side, source, url, wayback, added, note, listed_as.
- `index.html`, `styles.css`, `app.js`: the site. No build step.
- `data.py`: shared helpers (load, save, merge, wayback, snapshot).
- `add`, `merge`, `normalize`, `wayback`, `composers`: the five commands.
- `composer_aliases.json`: composer spellings from classicalconcertmap, see Names.
- `seed/`: one script per bulk source.
