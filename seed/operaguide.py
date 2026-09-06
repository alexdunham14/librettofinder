#!/usr/bin/env python3
"""opera-guide.ch: 500+ operas, each with single-language libretto pages (usually German,
often English, sometimes the original). Not side by side, so these mark the operas where a
side-by-side still needs building. One fetch per opera, politely spaced."""
import html, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data

BASE = "https://opera-guide.ch"
lst, _ = data.fetch(BASE + "/en/operas/")
# The list is rows of one composer followed by all of that composer's operas.
rows, composer = [], None
for m in re.finditer(r'<a href="/en/composers/\d+/" title="([^"]+)">|<a href="(/en/operas/[^"]+/)" title="([^"]+)">', lst):
    if m.group(1):
        composer = m.group(1)
    elif composer:
        rows.append((composer, m.group(2), m.group(3)))
seen = set()
rows = [r for r in rows if not (r[1] in seen or seen.add(r[1]))]
print(f"{len(rows)} operas listed", file=sys.stderr)
out = []
for i, (composer, path, opera) in enumerate(rows, 1):
    composer, opera = html.unescape(composer), html.unescape(opera)
    try:
        page, _ = data.fetch(BASE + path)
    except Exception as ex:  # noqa: BLE001
        print("failed", path, ex, file=sys.stderr)
        continue
    langs = sorted(set(re.findall(r'href="' + re.escape(path) + r'libretto/([a-z]{2})/"', page)))
    for lang in langs:
        out.append(data.entry(opera, composer, BASE + path + f"libretto/{lang}/", [lang], False, "opera-guide.ch"))
    if i % 25 == 0:
        print(f"{i}/{len(rows)}", file=sys.stderr, flush=True)
    time.sleep(0.4)
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} entries", file=sys.stderr)
