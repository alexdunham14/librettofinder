#!/usr/bin/env python3
"""opera-arias.com: an aria/opera reference site that also hosts full librettos, one page per
opera in whatever language it was written in, plus an /english/ (and sometimes /deutsch/)
translation page for many of them. Not side by side. /libretto/ lists every opera that has one;
/composers/all-composers-by-alphabet/ gives proper-cased composer names. The site doesn't label
the base page's language, so we detect it from the text itself (stopword counts; Cyrillic is
its own tell) rather than guess from the composer. One index fetch, one per opera, one more for
operas without an obvious English page already -- up to ~550 fetches, politely spaced."""
import html, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data

BASE = "https://www.opera-arias.com"

STOPWORDS = {
    "it": [" il ", " la ", " di ", " che ", " non ", " un ", " per ", " con ", " del ", " della ", " gli ", " delle "],
    "fr": [" le ", " la ", " de ", " et ", " que ", " un ", " pour ", " des ", " est ", " dans ", " vous ", " je "],
    "de": [" der ", " die ", " und ", " ich ", " das ", " nicht ", " ist ", " ein ", " sie ", " mit ", " dem ", " du "],
    "en": [" the ", " and ", " of ", " to ", " is ", " in ", " you ", " that ", " it ", " for ", " my ", " with "],
    "es": [" el ", " la ", " de ", " que ", " y ", " en ", " un ", " es ", " por ", " con ", " los ", " las "],
}


def libretto_text(page):
    m = re.search(r'<div class="libretto_div">(.*?)</div>\s*<script', page, re.S)
    if not m:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", " ", m.group(1)))


def detect_lang(text):
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    if re.search(r"[а-яё]", low):
        return "ru"
    scores = {lang: sum(low.count(w) for w in words) for lang, words in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 5 else None


def title_of(page):
    m = re.search(r"<title>(.*?)</title>", page)
    if not m:
        return None
    return html.unescape(re.sub(r"\s*\|?\s*Libretto.*$", "", m.group(1))).strip()


# The site spells some names its own way (typos, missing diacritics, extra or dropped middle
# names); these line them up with the spelling already canonical elsewhere on librettofinder
# (data.py's COMPOSERS/ORIGINAL tables), same idea as that file but kept local since it's
# specific to how this one site writes names.
LOCAL_FIXES = {
    "rossini": "Gioachino Rossini", "gluck": "Christoph Willibald Gluck", "handel": "George Frideric Handel",
    "puccini": "Giacomo Puccini", "boieldieu": "François-Adrien Boieldieu", "halevy": "Fromental Halévy",
    "tchaikovsky": "Pyotr Ilyich Tchaikovsky", "dvorak": "Antonín Dvořák", "wolf": "Hugo Wolf",
    "strauss-jr-j": "Johann Strauss II",
}

# composer slug -> "First Last" from the alphabetic composer list ("Surname, First" per row).
cpage, _ = data.fetch(BASE + "/composers/all-composers-by-alphabet/")
composers = {}
for slug, surname, first in re.findall(r'href="/([a-z][a-z-]*)/"[^>]*>([^,<]+),\s*([^<]+)', cpage):
    composers[slug] = html.unescape(f"{first.strip()} {surname.strip()}")
composers.update(LOCAL_FIXES)

lpage, _ = data.fetch(BASE + "/libretto/")
pairs = sorted(set(re.findall(r'href="/([a-z][a-z-]*)/([a-z0-9%().-]+)/libretto/"', lpage)))
print(f"{len(pairs)} operas with a libretto page", file=sys.stderr)

out = []
for i, (cslug, oslug) in enumerate(pairs, 1):
    path = f"/{cslug}/{oslug}/libretto/"
    try:
        page, _ = data.fetch(BASE + path, retries=1)
    except Exception as ex:  # noqa: BLE001
        print("failed", path, ex, file=sys.stderr)
        continue
    title = title_of(page)
    composer = composers.get(cslug, cslug.replace("-", " ").title())
    lang = detect_lang(libretto_text(page))
    if not title or not lang:
        print("skip (no title/lang)", path, file=sys.stderr)
        continue
    out.append(data.entry(title, composer, BASE + path, [lang], False, "opera-arias.com"))
    if lang != "en":
        epath = f"/{cslug}/{oslug}/libretto/english/"
        try:
            epage, _ = data.fetch(BASE + epath, retries=0)
            if "English Translation" in epage:
                out.append(data.entry(title, composer, BASE + epath, ["en"], False, "opera-arias.com",
                                       note="Translation."))
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.4)
    if i % 25 == 0:
        print(f"{i}/{len(pairs)}", file=sys.stderr, flush=True)
    time.sleep(0.4)

json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} entries", file=sys.stderr)
