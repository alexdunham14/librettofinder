#!/usr/bin/env python3
"""rwagner.net is dead (the domain now redirects to spam). Its German/English side-by-side
libretti for ten Wagner operas survive in the Wayback Machine. We list the archived
English index page per opera, using the CDX API to find the snapshot timestamps."""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data

OPERAS = {
    "hollander": ("Der fliegende Holländer", "e-holl-00.html"),
    "tannhauser": ("Tannhäuser", "e-tannh-00.html"),
    "lohengrin": ("Lohengrin", "e-lohen-00.html"),
    "tristan": ("Tristan und Isolde", "e-tristan-00.html"),
    "meisters": ("Die Meistersinger von Nürnberg", "e-meisters-00.html"),
    "rheingold": ("Das Rheingold", "e-rhein-00.html"),
    "walkure": ("Die Walküre", "e-walk-00.html"),
    "siegfried": ("Siegfried", "e-sieg-00.html"),
    "gotterd": ("Götterdämmerung", "e-gott-00.html"),
    "parsifal": ("Parsifal", "e-pars-00.html"),
}
cdx, _ = data.fetch("http://web.archive.org/cdx/search/cdx?url=rwagner.net/libretti/*&output=txt&fl=original,timestamp&filter=statuscode:200&collapse=urlkey", timeout=120, retries=4)
stamps = {}
for line in cdx.splitlines():
    parts = line.split()
    if len(parts) == 2:
        stamps[re.sub(r":80", "", parts[0])] = parts[1]

out = []
for d, (title, index) in OPERAS.items():
    original = f"http://www.rwagner.net/libretti/{d}/{index}"
    ts = stamps.get(original)
    if not ts:
        print("no snapshot for", original, file=sys.stderr)
        continue
    archived = f"https://web.archive.org/web/{ts}/{original}"
    e = data.entry(title, "Richard Wagner", archived, ["de", "en"], True, "rwagner.net (archived)",
                   note="Site is gone; this is the Wayback Machine copy. Scene pages link onward inside the archive.",
                   wayback=archived)
    out.append(e)
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} entries", file=sys.stderr)
