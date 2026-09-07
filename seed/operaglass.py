#!/usr/bin/env python3
"""OperaGlass (opera.stanford.edu, Rick Bogart, 1995 to about 2014) has been unreachable since
2026: the name still resolves but nothing answers. Its libretti survive in the Wayback Machine:
about a hundred pages for some ninety operas, a third of them genuine two-column texts
(Italian/English, Italian/German, Italian/French). We list the archived copy of each page.
The site's own opera pages are hand-written and irregular, so we go by the libretto pages
themselves: the CDX index gives the paths, each page's <title> carries a language marker such
as "(I/E)" where it is bilingual, and otherwise the text's stopwords say what language it is."""
import concurrent.futures, html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data

SOURCE = "opera.stanford.edu (archived)"
NOTE = "opera.stanford.edu has been unreachable since 2026; this is the Wayback Machine copy."
COMPOSERS = {
    "bellini": "Vincenzo Bellini", "bizet": "Georges Bizet", "boito": "Arrigo Boito", "busoni": "Ferruccio Busoni",
    "cadman": "Charles Wakefield Cadman", "charpentier": "Gustave Charpentier", "delibes": "Léo Delibes",
    "donizetti": "Gaetano Donizetti", "franckenstein": "Clemens von Franckenstein", "giordano": "Umberto Giordano",
    "gounod": "Charles Gounod", "halevy": "Fromental Halévy", "leoncavallo": "Ruggero Leoncavallo", "leoni": "Franco Leoni",
    "mancinelli": "Luigi Mancinelli", "marschner": "Heinrich Marschner", "mascagni": "Pietro Mascagni",
    "massenet": "Jules Massenet", "mozart": "Wolfgang Amadeus Mozart", "offenbach": "Jacques Offenbach", "peri": "Jacopo Peri",
    "puccini": "Giacomo Puccini", "purcell": "Henry Purcell", "rossini": "Gioachino Rossini", "soliva": "Carlo Evasio Soliva",
    "strauss": "Richard Strauss", "verdi": "Giuseppe Verdi", "wagner": "Richard Wagner", "weber": "Carl Maria von Weber",
}
TITLES = {  # pages whose <title> is not the opera's name
    "cavalleria": "Cavalleria rusticana", "edipore": "Edipo re", "italiana": "L'italiana in Algeri",
    "entfuhrung": "Die Entführung aus dem Serail", "lakme": "Lakmé", "guillaumetell": "Guglielmo Tell",
    "shanewis": "Shanewis", "fritz": "L'amico Fritz", "lindadichamounix": "Linda di Chamounix",
    "jongleur": "Le jongleur de Notre-Dame", "hoffmann": "Les contes d'Hoffmann", "boheme": "La bohème",
    "levilli": "Le Villi", "maometto": "L'assedio di Corinto",
}
LANGS = {  # pages the stopword count gets wrong: Latin reads as French, a French version as its Italian original
    "lucie/libretto.html": ["fr"], "apollo/libretto.html": ["la"], "schauspieldirektor/libretto.html": ["de"],
    "butterfly/libretto_a.html": ["it"],
}
LETTERS = {"i": "it", "e": "en", "f": "fr", "d": "de", "g": "de", "s": "es", "l": "la", "p": "pt", "r": "ru", "c": "cs"}
WORDS = {"italiano": "it", "italian": "it", "english": "en", "français": "fr", "francais": "fr", "french": "fr",
         "deutsch": "de", "german": "de", "español": "es"}
STOPWORDS = {
    "it": [" il ", " la ", " di ", " che ", " non ", " un ", " per ", " con ", " del ", " della ", " gli ", " delle "],
    "fr": [" le ", " la ", " de ", " et ", " que ", " un ", " pour ", " des ", " est ", " dans ", " vous ", " je "],
    "de": [" der ", " die ", " und ", " ich ", " das ", " nicht ", " ist ", " ein ", " sie ", " mit ", " dem ", " du "],
    "en": [" the ", " and ", " of ", " to ", " is ", " in ", " you ", " that ", " it ", " for ", " my ", " with "],
    "es": [" el ", " la ", " de ", " que ", " y ", " en ", " un ", " es ", " por ", " con ", " los ", " las "],
}


def detect_lang(text):
    low = " " + re.sub(r"\s+", " ", text.lower()) + " "
    scores = {lang: sum(low.count(w) for w in words) for lang, words in STOPWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 5 else None


def decode(latin1_page):
    m = re.search(r'charset\s*=\s*"?([\w-]+)', latin1_page, re.I)
    try:
        return latin1_page.encode("latin-1").decode(m.group(1) if m else "iso-8859-15", errors="replace")
    except LookupError:
        return latin1_page


def languages_of(title, filename, text):
    """Two languages when the title says so ("(I/E)") or the filename does (libretto_ie.html)."""
    m = re.search(r"\(\s*([A-Za-z])\s*/\s*([A-Za-z])\s*\)", title)
    if m and m.group(1).lower() in LETTERS and m.group(2).lower() in LETTERS:
        return [LETTERS[m.group(1).lower()], LETTERS[m.group(2).lower()]], True
    suffix = re.sub(r"^libretto_?|\.html$", "", filename)
    if len(suffix) == 2 and suffix[0] in LETTERS and suffix[1] in LETTERS and suffix[0] != suffix[1]:
        return [LETTERS[suffix[0]], LETTERS[suffix[1]]], True
    for word, code in WORDS.items():
        if re.search(r"\(\s*" + word, title, re.I):
            return [code], False
    m = re.search(r"\(\s*([A-Za-z])\s*\)", title)
    if m and m.group(1).lower() in LETTERS:
        return [LETTERS[m.group(1).lower()]], False
    lang = detect_lang(text)
    if len(suffix) == 1 and suffix in LETTERS and (lang is None or lang == LETTERS[suffix]):
        return [LETTERS[suffix]], False
    return ([lang] if lang else []), False


cdx, _ = data.fetch("http://web.archive.org/cdx/search/cdx?url=opera.stanford.edu/*&output=txt"
                    "&fl=original,statuscode&filter=statuscode:200&collapse=urlkey", timeout=180, retries=4)
pages = {}
for line in cdx.splitlines():
    original = line.split()[0]
    path = re.sub(r"^https?://opera\.stanford\.edu(:80)?", "", original).split("?")[0]
    if re.fullmatch(r"/[A-Za-z]+/[A-Za-z0-9_-]+/libretto[a-z_]*\.html", path):
        pages.setdefault(path.lower(), original)
print(f"{len(pages)} libretto pages in the index", file=sys.stderr)

def one(item):
    key, original = item
    composer_dir, opera_dir, filename = key.strip("/").split("/")
    composer = COMPOSERS.get(composer_dir)
    if not composer:
        return ("unknown composer dir " + composer_dir, None)
    try:
        ts, _ = data.fetch("http://web.archive.org/cdx/search/cdx?url=" + original + "&fl=timestamp&filter=statuscode:200&limit=-1",
                           timeout=90, retries=3)
        ts = ts.strip().splitlines()[-1]
        page, final = data.fetch(f"https://web.archive.org/web/{ts}id_/" + original, encoding="latin-1", timeout=90, retries=3)
    except Exception as ex:  # noqa: BLE001
        return (f"failed {original} {ex}", None)
    page = decode(page)
    m = re.search(r"<title>(.*?)</title>", page, re.I | re.S)
    title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else ""
    parts = [p.strip() for p in re.split(r"\s*[:|]\s*|\s+-\s+", title)]
    parts = [re.sub(r"\s*\bLibretto\b.*$", "", p).strip() for p in parts]
    parts = [p for p in parts if p and p.lower() not in ("operaglass", composer_dir, data.surname(composer).lower())]
    opera = TITLES.get(opera_dir) or (parts[0] if parts else opera_dir)
    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", " ", page)))
    langs, sbs = languages_of(title, filename, text)
    if f"{opera_dir}/{filename}" in LANGS:
        langs, sbs = LANGS[f"{opera_dir}/{filename}"], False
    note = NOTE
    original_lang = data.OPERA_ORIGINAL.get((composer, data.slug(opera)), data.ORIGINAL.get(composer))
    if filename == "libretto.html" and original_lang and len(text) < 6000 and (not langs or langs != [original_lang]):
        langs = [original_lang]  # an index of act pages: too few words to detect, or English navigation; the opera's own language
    if len(text) < 1500:
        note += " This page is the index of the act pages."
    if not langs or len(text) < 300:
        return (f"skipped {key} {title!r} {langs} {len(text)}", None)
    archived = re.sub(r"/web/(\d+)id_/", r"/web/\1/", final)
    return (None, data.entry(opera, composer, archived, langs, sbs, SOURCE, note=note, wayback=archived))


out, seen = [], {}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:  # archive.org is slow and 503s under load
    results = list(pool.map(one, sorted(pages.items())))
for i, (err, e) in enumerate(results, 1):
    if err:
        print(err, file=sys.stderr)
        continue
    if e["id"] in seen:  # several versions of the same libretto (Butterfly has four): keep the first, count the rest
        seen[e["id"]]["note"] = NOTE + " The site has more than one version of this libretto; this is one of them."
        print("duplicate id", e["url"], file=sys.stderr)
        continue
    seen[e["id"]] = e
    out.append(e)
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} entries, {sum(e['side_by_side'] for e in out)} side by side", file=sys.stderr)
