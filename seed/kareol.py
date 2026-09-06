#!/usr/bin/env python3
"""Kareol (kareol.es): original text plus Spanish translation side by side for ~450 operas.
Its composer index (autor.htm) is a flat page: <strong>SURNAME, Given</strong> then the works.
Spanish titles, with the original title in parentheses when it differs. One fetch."""
import html, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data

BASE = "http://www.kareol.es/"
page, _ = data.fetch(BASE + "autor.htm", encoding="latin-1")
page = html.unescape(page)
page = re.sub(r"</?font[^>]*>|&nbsp;", " ", page, flags=re.I)
# Headings are <strong> or <b>, sometimes split across several tags ("<strong>FIBICH, </strong><b>Zdenek</b>").
page = re.sub(r"</?b>", lambda m: m.group(0).replace("b", "strong"), page, flags=re.I)
page = re.sub(r"<strong>(?:\s|<br>)*</strong>", " ", page, flags=re.I)
strip = lambda s: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()
cap = lambda s: " ".join(w[:1].upper() + w[1:].lower() for w in s.split())

out = []
composer, heading = None, ""
for m in re.finditer(r'<strong>((?:[^<]|<br>)+)</strong>|<a\s+href="(obras/[^"]+)"[^>]*>(.*?)</a>(.{0,200}?)(?=<a\s+href|<strong>|$)', page, re.S | re.I):
    if m.group(1):
        frag = strip(m.group(1))
        if all(len(w) == 1 for w in frag.split()):  # the A–Z index anchors, not a composer
            continue
        heading = (heading + " " + frag).strip()  # fragments accumulate until the next work link
        continue
    if heading:
        raw = re.sub(r"\s+", " ", heading)
        if "," in raw:
            last, first = [x.strip() for x in raw.split(",", 1)]
            composer = f"{first} {cap(last)}".strip()
        elif raw == raw.upper() and len(raw) > 2:
            composer = cap(raw)
        heading = ""
    if not composer:
        continue
    href, title, tail = m.group(2), strip(m.group(3)), strip(m.group(4))
    if not title or title.lower().startswith("composiciones varias"):
        continue
    orig = re.search(r"\(([^()]{2,80})\)", tail)
    opera = orig.group(1).strip() if orig else title
    note = "Original + Spanish. " + (f"Listed as “{title}”." if orig and orig.group(1).strip() != title else "")
    out.append(data.entry(opera, composer, BASE + href, ["es"], True, "kareol.es", note=note.strip()))

seen = set()
out = [e for e in out if not (e["id"] in seen or seen.add(e["id"]))]
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} entries, {len({e['composer'] for e in out})} composers", file=sys.stderr)
