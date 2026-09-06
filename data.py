"""Shared helpers for the libretto finder. Standard library only."""
import datetime as dt
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "libretti.json")
ARCHIVE = os.path.join(HERE, "archive")
UA = "Mozilla/5.0 (compatible; librettofinder/1.0)"

LANG_CODES = {
    "italian": "it", "english": "en", "german": "de", "french": "fr", "russian": "ru",
    "czech": "cs", "spanish": "es", "hungarian": "hu", "latin": "la", "polish": "pl",
    "portuguese": "pt", "swedish": "sv", "danish": "da", "dutch": "nl", "finnish": "fi",
}
LANG_NAMES = {v: k.capitalize() for k, v in LANG_CODES.items()}


def today():
    return dt.date.today().isoformat()


def fetch(url, timeout=40, retries=2, encoding=None):
    last = None
    for attempt in range(retries + 1):
        try:
            safe_url = urllib.parse.quote(url, safe=":/?&=+%#~")
            req = urllib.request.Request(safe_url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                charset = encoding or r.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace"), r.geturl()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (attempt + 1))
    raise last


def slug(s):
    s = re.sub(r"['’]", "", s.lower())
    s = re.sub(r"[àáâäã]", "a", s); s = re.sub(r"[èéêë]", "e", s); s = re.sub(r"[ìíîï]", "i", s)
    s = re.sub(r"[òóôöõ]", "o", s); s = re.sub(r"[ùúûü]", "u", s); s = re.sub(r"[ç]", "c", s); s = re.sub(r"[ñ]", "n", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def surname(composer):
    parts = composer.replace(",", "").split()
    return parts[-1] if parts else composer


def make_id(composer, opera, source, languages):
    return "-".join([slug(surname(composer)), slug(opera), slug(source), "-".join(languages)])


def entry(opera, composer, url, languages, side_by_side, source=None, note="", wayback=None):
    if source is None:
        source = re.sub(r"^www\.", "", urllib.request.urlparse(url).netloc)
    return {
        "id": make_id(composer, opera, source, languages),
        "opera": opera,
        "composer": composer,
        "languages": list(languages),
        "side_by_side": bool(side_by_side),
        "source": source,
        "url": url,
        "wayback": wayback or "https://web.archive.org/web/2/" + url,
        "added": today(),
        "note": note,
    }


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def save(entries):
    entries.sort(key=lambda e: (slug(surname(e["composer"])), slug(e["composer"]), slug(e["opera"]), not e["side_by_side"], e["source"]))
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
        f.write("\n")


def merge(entries, new):
    """Insert or update by id. Keeps an existing dated wayback link and 'added' date."""
    by_id = {e["id"]: e for e in entries}
    added = updated = 0
    for n in new:
        old = by_id.get(n["id"])
        if old:
            if "web.archive.org/web/2/" in n["wayback"] and "web.archive.org/web/2/" not in old["wayback"]:
                n["wayback"] = old["wayback"]
            n["added"] = old["added"]
            if n != old:
                old.update(n); updated += 1
        else:
            entries.append(n); by_id[n["id"]] = n; added += 1
    return added, updated


def wayback_save(url):
    """Ask the Wayback Machine to save URL now. Returns a dated snapshot URL, or None."""
    try:
        req = urllib.request.Request("https://web.archive.org/save/" + url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            loc = r.headers.get("Content-Location") or r.geturl()
            if loc.startswith("/"):
                loc = "https://web.archive.org" + loc
            if re.search(r"web\.archive\.org/web/\d{8,}", loc):
                return loc
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"wayback {e.code} for {url}\n")
    except Exception as e:  # noqa: BLE001
        sys.stderr.write(f"wayback failed for {url}: {e}\n")
    return None


def snapshot(e, page=None):
    os.makedirs(ARCHIVE, exist_ok=True)
    path = os.path.join(ARCHIVE, e["id"] + ".html")
    if page is None:
        page, _ = fetch(e["url"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"<!-- saved {today()} from {e['url']} -->\n{page}")
    return path
