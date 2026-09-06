#!/usr/bin/env python3
"""LibrettoArchive (DM's Opera Series).
/Operas lists every opera page. Each opera page links its composer and its single-language
libretti ({Opera}_libretto_English). The side-by-side pages ({Opera}_libretto_Italian_English)
are linked only from the single-language pages, so we fetch one of those per opera too.
About two fetches per opera, roughly 200 in all."""
import html, json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data

BASE = "https://www.librettoarchive.com/"
link_re = r'<a href="https://www\.librettoarchive\.com/([A-Za-z0-9_%.\-]+)"[^>]*>([^<]+)</a>'
skip = {"Operas", "Composers", "Libretti", "History", "Blog", "About", "Links"}
composers_page, _ = data.fetch(BASE + "Composers")
composer_names = {s: html.unescape(n).strip() for s, n in re.findall(link_re, composers_page) if s not in skip and not s.startswith("auth")}

page, _ = data.fetch(BASE + "Operas")
operas = {}
for slug, name in re.findall(link_re, page):
    if slug in skip or slug.startswith("auth") or "_libretto_" in slug or slug in composer_names:
        continue
    operas.setdefault(slug, html.unescape(name).strip())
print(f"{len(operas)} operas", file=sys.stderr)

def codes(s):
    return [data.LANG_CODES.get(l.lower(), l.lower()) for l in s.split("_")]

out = []
for i, (slug, opera) in enumerate(operas.items(), 1):
    try:
        op, _ = data.fetch(BASE + slug)
    except Exception as ex:  # noqa: BLE001
        print("failed", slug, ex, file=sys.stderr); continue
    m = re.search(r"by <a href=\"https://www\.librettoarchive\.com/[^\"]+\">([^<]+)</a>", op)
    comp = html.unescape(m.group(1)).strip() if m else None
    if not comp:
        print("no composer for", slug, file=sys.stderr); continue
    lib_re = r'href="https://www\.librettoarchive\.com/(' + re.escape(slug) + r'_libretto_[A-Za-z_]+)"'
    links = set(re.findall(lib_re, op))
    singles = sorted(l for l in links if l.count("_") == slug.count("_") + 2)
    if singles:
        pick = next((l for l in singles if l.endswith("_English")), singles[0])
        try:
            sp, _ = data.fetch(BASE + pick)
            links |= set(re.findall(lib_re, sp))
        except Exception as ex:  # noqa: BLE001
            print("failed", pick, ex, file=sys.stderr)
        time.sleep(0.3)
    for l in sorted(links):
        langs = codes(l.split("_libretto_", 1)[1])
        out.append(data.entry(opera, comp, BASE + l, langs, len(langs) > 1, "librettoarchive.com"))
    if i % 20 == 0:
        print(f"{i}/{len(operas)}", file=sys.stderr, flush=True)
    time.sleep(0.3)

seen = set()
out = [e for e in out if not (e["id"] in seen or seen.add(e["id"]))]
json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
print(f"{len(out)} entries, {sum(e['side_by_side'] for e in out)} side by side", file=sys.stderr)
