#!/usr/bin/env python3
"""librettidopera.it: Italian-only libretti, ~335 operas. The alphabetical title index
(ope_alfatit.html) lists a folder per opera; the opera's own page (folder/folder.html) gives
the properly-cased title in <title> and the composer under "Musica di" (surname in caps,
sometimes several composers). The full text starts at folder/a_01.html (act one; one-act
works use the same name). One fetch for the index, one per opera, politely spaced."""
import html, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data

BASE = "https://www.librettidopera.it/"


def fix_case(name):
    """The site renders surnames in caps; title-case any all-caps word, leave the rest alone."""
    return " ".join(w.capitalize() if w.isupper() and len(w) > 1 else w for w in name.split(" "))


lst, _ = data.fetch(BASE + "ope_alfatit.html")
rows = re.findall(r'<div class="alfa">(.*?)</div>', lst, re.S)
seen_href, folders = set(), []
for r in rows:
    m = re.search(r'<span class="pt"><a href="([a-z0-9_]+)/\1\.html"', r)
    if not m:
        print("no href in row", r[:80], file=sys.stderr)
        continue
    folder = m.group(1)
    if folder not in seen_href:
        seen_href.add(folder)
        folders.append(folder)
print(f"{len(folders)} opera folders", file=sys.stderr)

out = []
for i, folder in enumerate(folders, 1):
    path = f"{folder}/{folder}.html"
    try:
        page, _ = data.fetch(BASE + path)
    except Exception as ex:  # noqa: BLE001
        print("failed", path, ex, file=sys.stderr)
        continue
    tm = re.search(r"<title>(.*?)</title>", page)
    if not tm:
        print("no title", path, file=sys.stderr)
        continue
    title = html.unescape(re.sub(r"\s*\(\d{4}\)\s*$", "", tm.group(1)).strip())
    cm = re.search(r'(?:Musica di|Libretto e musica di)</span></h3>\s*<h2>(.*?)</h2>', page, re.S)
    if not cm:
        print("no composer", path, file=sys.stderr)
        continue
    names = [html.unescape(n).strip().rstrip(",") for n in re.findall(r'<span class="nobr">(.*?)</span>', cm.group(1))]
    composer = " and ".join(fix_case(n) for n in names)
    if "a_01.html" not in page:
        print("no act text found for", path, file=sys.stderr)
        continue
    url = BASE + folder + "/a_01.html"
    out.append(data.entry(title, composer, url, ["it"], False, "librettidopera.it"))
    if i % 25 == 0:
        print(f"{i}/{len(folders)}", file=sys.stderr, flush=True)
    time.sleep(0.5)

# A few operas have two editions on the site (e.g. Simon Boccanegra 1857 and 1881), which would
# collide on id (same composer/opera/source/language); keep whichever came first.
seen = set()
out = [e for e in out if not (e["id"] in seen or seen.add(e["id"]))]

json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} entries", file=sys.stderr)
