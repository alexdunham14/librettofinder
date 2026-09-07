#!/usr/bin/env python3
"""French Wikisource, category "Livrets": ~100 opera and operetta libretti (mostly Offenbach
and other opera-comique, plus a few translated German works), public domain, single language
(everything on fr.wikisource.org is French, including translations of foreign operas). Every
page carries a standard header div with the composer's name (sometimes via an explicit
"Musique de X", sometimes as the header's own byline) and the clean title. Where an opera's own
page is just a table of contents linking each act, the category also lists a "Texte entier"
page with the whole thing on one page; we use that instead. One fetch for the category, one per
opera, politely spaced."""
import html, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data

BASE = "https://fr.wikisource.org"
CATEGORY = "/wiki/Cat%C3%A9gorie:Livrets"


def composer_of(page):
    # Most pages spell out "Musique de X" when the credited author is the librettist.
    m = re.search(r'Musique de <a[^>]*>(?:<span[^>]*>)?([^<]+)', page)
    if m:
        return html.unescape(m.group(1)).strip()
    # Otherwise the author byline (one of two header template variants) is the composer.
    m = re.search(r'(?:id|class)="ws-author"[^>]*>\s*(?:<span[^>]*>)*<a[^>]*>(?:<span[^>]*>)?([^<]+)', page)
    return html.unescape(m.group(1)).strip() if m else None


def title_of(page):
    m = re.search(r'id="ws-title"[^>]*>(?:<a[^>]*>)?([^<]+)', page)
    if m:
        return html.unescape(m.group(1)).strip()
    # The "chapter of a multi-volume work" template's ws-title names the parent work, not this
    # opera, so fall back to the page's own <title>, stripping "/Texte entier" and any trailing
    # parenthetical disambiguator ("La Périchole (1868)" -> "La Périchole").
    m = re.search(r"<title>(.*?)\s*-\s*Wikisource</title>", page)
    if not m:
        return None
    t = html.unescape(m.group(1)).strip()
    t = re.sub(r"/Texte entier$", "", t).strip()
    return re.sub(r"\s*\([^)]*\)$", "", t).strip()


cat, _ = data.fetch(BASE + CATEGORY)
items = re.findall(r'<li><a href="(/wiki/[^"]*)" title="[^"]*">[^<]*</a></li>', cat)
items = [h for h in items if not h.startswith("/wiki/Cat%C3%A9gorie:")]

# Some operas are listed twice: the work's own page (often just a table of contents linking
# each act) and a ".../Texte entier" page with the whole thing on one page. Prefer the latter.
targets = {}
for href in items:
    base = re.sub(r"/Texte_entier$", "", href)
    if href != base or base not in targets:
        targets[base] = href
print(f"{len(targets)} works", file=sys.stderr)

# Pages whose byline is the librettist, not the composer, and pages that are not operas.
# title -> (composer, title) or None to skip.
LIBRETTIST_PAGES = {
    "Gustave III": ("Daniel-François-Esprit Auber", "Gustave III, ou Le Bal masqué"),
    "L’Alcôve": ("Jacques Offenbach", "L’Alcôve"),
    "L’Apollonide": ("Franz Servais", "L’Apollonide"),
    "La Dame blanche": ("François-Adrien Boieldieu", "La Dame blanche"),
    "La Lycéenne": ("Gaston Serpette", "La Lycéenne"),
    "La Princesse de Trébizonde": ("Jacques Offenbach", "La Princesse de Trébizonde"),
    "Le Carnaval des revues": ("Jacques Offenbach", "Le Carnaval des revues"),
    "Les Pêcheurs de perles": ("Georges Bizet", "Les Pêcheurs de perles"),
    "Manon Lescaut": ("Daniel-François-Esprit Auber", "Manon Lescaut"),
    "Robert le Diable": ("Giacomo Meyerbeer", "Robert le Diable"),
    "Le Ballet de la raillerie": None,  # Lully ballet, not an opera
    "Livret de Roméo et Juliette": None,  # Berlioz's symphony, not an opera
}

out = []
for i, (base, href) in enumerate(sorted(targets.items()), 1):
    try:
        page, _ = data.fetch(BASE + href)
    except Exception as ex:  # noqa: BLE001
        print("failed", href, ex, file=sys.stderr)
        continue
    title, composer = title_of(page), composer_of(page)
    if title in LIBRETTIST_PAGES:
        if LIBRETTIST_PAGES[title] is None:
            continue
        composer, title = LIBRETTIST_PAGES[title]
    if not title or not composer:
        print("no title/composer for", href, file=sys.stderr)
        continue
    out.append(data.entry(title, composer, BASE + href, ["fr"], False, "fr.wikisource.org"))
    if i % 25 == 0:
        print(f"{i}/{len(targets)}", file=sys.stderr, flush=True)
    time.sleep(0.5)

# Two different scanned editions of the same opera (e.g. "La Périchole" and its 1868 original)
# can produce the same id; keep the one found first (targets is processed in sorted order, so
# the plain title wins over a "(year)"-suffixed edition).
seen = set()
out = [e for e in out if not (e["id"] in seen or seen.add(e["id"]))]

json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} entries", file=sys.stderr)
