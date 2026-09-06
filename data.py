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
    e = {
        "id": make_id(composer, opera, source, languages),  # from the names as the source gives them, so ids are stable
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
    canonicalize(e)
    return e


def load():
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)


def save(entries):
    entries.sort(key=lambda e: (slug(surname(e["composer"])), slug(e["composer"]), slug(e["opera"]), not e["side_by_side"], e["source"]))
    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
        f.write("\n")


def merge(entries, new, prune=None):
    """Insert or update by id. Keeps an existing dated wayback link and 'added' date.
    With prune=<source>, entries of that source whose id the seed no longer produces are dropped
    (a dated snapshot carries over to the entry that now holds the same url)."""
    by_id = {e["id"]: e for e in entries}
    by_url = {e["url"]: e for e in entries}
    added = updated = 0
    for n in new:
        old = by_id.get(n["id"]) or (by_url.get(n["url"]) if prune else None)
        if old and "web.archive.org/web/2/" in n["wayback"] and "web.archive.org/web/2/" not in old["wayback"]:
            n["wayback"] = old["wayback"]
        old = by_id.get(n["id"])
        if old:
            n["added"] = old["added"]
            if n != old:
                old.update(n); updated += 1
        else:
            entries.append(n); by_id[n["id"]] = n; added += 1
    if prune:
        keep = {n["id"] for n in new}
        entries[:] = [e for e in entries if e["source"] != prune or e["id"] in keep]
    normalize(entries)
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


# ------------------------------------------------------------------ names
# Sources spell composers and operas their own way (Kareol in Spanish, opera-guide.ch in
# German or English). These tables fold them to one form so an opera is one group on the page.
# Keys are as the source writes them; values are the canonical form used on the page.

COMPOSERS = {
    "Gioacchino Rossini": "Gioachino Rossini",
    "Wolfgang Gottlieb Mozart": "Wolfgang Amadeus Mozart",
    "Georg Friedrich Haendel": "George Frideric Handel", "Georg Friedrich Händel": "George Frideric Handel",
    "Héctor Berlioz": "Hector Berlioz",
    "Piotr Ilich Chaikovski": "Pyotr Ilyich Tchaikovsky", "Peter Tschaikowski": "Pyotr Ilyich Tchaikovsky",
    "Nicolai Andreievich Rimsky-korsakov": "Nikolai Rimsky-Korsakov", "Nikolai Rimski-Korsakow": "Nikolai Rimsky-Korsakov",
    "Leos Janácek": "Leoš Janáček",
    "John Coolidge Adams": "John Adams",
    "Daniel Francois Esprit Auber": "Daniel-François-Esprit Auber",
    "Béla Bártok": "Béla Bartók",
    "Francois Boïeldieu": "François-Adrien Boieldieu", "François Adrien Boïeldieu": "François-Adrien Boieldieu",
    "Leo Delibes": "Léo Delibes",
    "Antonín Dvorak": "Antonín Dvořák", "Antonin Dvorák": "Antonín Dvořák",
    "Jacques Fromental Halévy": "Fromental Halévy", "Jacques Halévy": "Fromental Halévy",
    "Franz Joseph Haydn": "Joseph Haydn",
    "Ruggiero Leoncavallo": "Ruggero Leoncavallo",
    "Hans Erich Pfitzner": "Hans Pfitzner",
    "Jean Philippe Rameau": "Jean-Philippe Rameau",
    "Albert Reimann": "Aribert Reimann",
    "Camille Saint-saëns": "Camille Saint-Saëns",
    "Robert Alexander Schumann": "Robert Schumann",
    "Johann II Strauss": "Johann Strauss II", "Johann Strauss": "Johann Strauss II",
    "Louis Ambroise Thomas": "Ambroise Thomas",
    "Karl Maria von Weber": "Carl Maria von Weber",
    "Ermanno Wolf-ferrari": "Ermanno Wolf-Ferrari",
    "Bern Alois Zimmermann": "Bernd Alois Zimmermann",
    "Igor Strawinsky": "Igor Stravinsky",
    "Dmitri Schostakowitsch": "Dmitri Shostakovich", "Dimitri Shostakóvich": "Dmitri Shostakovich",
    "Sergej Rachmaninow": "Sergei Rachmaninoff", "Sergei Rachmaninov": "Sergei Rachmaninoff", "Sergei Rajmáninov": "Sergei Rachmaninoff",
    "Sergej Prokofjew": "Sergei Prokofiev",
    "Modest Mussorgski": "Modest Mussorgsky", "Modest Petrovich Mussorgsky": "Modest Mussorgsky",
    "Arnold Schönberg": "Arnold Schoenberg",
    "Engelbert Humperdink": "Engelbert Humperdinck",
    "Eugen d' Albert": "Eugen d'Albert", "Eugène D'albert": "Eugen d'Albert",
    "Carl Otto Nikolai": "Otto Nicolai",
    "Mijaíl Glinka": "Mikhail Glinka",
    "Bohuslav Martinu": "Bohuslav Martinů",
    "Bedrich Smetana": "Bedřich Smetana",
    "Jean- Baptiste Lully": "Jean-Baptiste Lully",
    "Fibich": "Zdeněk Fibich", "Zdenek Fibich": "Zdeněk Fibich",
    "Anónimo": "Anonymous",
    "Antón Rubinstein": "Anton Rubinstein",
    "Vicent Martín I Soler": "Vicente Martín y Soler",
    "Per": "Per Nørgård", "Per Nørgård": "Per Nørgård",
    "Ernst Theodor Amadeus Hoffmann": "E. T. A. Hoffmann",
    "Luigi y Federico Ricci": "Luigi and Federico Ricci",
    "Tomás Torrejón Y Velasco": "Tomás de Torrejón y Velasco",
    "Philippe II de Orleans": "Philippe II, Duke of Orléans",
    "Jean Jacques Rousseau": "Jean-Jacques Rousseau",
    "Étienne Nicolas Méhul": "Étienne Méhul",
    "Edouard Lalo": "Édouard Lalo",
    "Károly Goldmark": "Karl Goldmark",
    "Ivo Josipovic": "Ivo Josipović",
    "Stanislav Moniuszko": "Stanisław Moniuszko",
    "George Enescu": "George Enescu", "Peter Eötvös": "Péter Eötvös",
    "Jesús Guridi": "Jesús Guridi", "Franco Alfano": "Franco Alfano",
}

# Original language of the libretto, by composer, with per-opera exceptions below.
ORIGINAL = {
    "it": ["Giuseppe Verdi", "Giacomo Puccini", "Gaetano Donizetti", "Gioachino Rossini", "Vincenzo Bellini",
           "Pietro Mascagni", "Ruggero Leoncavallo", "Umberto Giordano", "Francesco Cilea", "Amilcare Ponchielli",
           "Arrigo Boito", "Alfredo Catalani", "Claudio Monteverdi", "Giovanni Battista Pergolesi", "Giovanni Paisiello",
           "Domenico Cimarosa", "Antonio Salieri", "Saverio Mercadante", "Gaspare Spontini", "Leonardo Vinci",
           "Riccardo Zandonai", "Ermanno Wolf-Ferrari", "Italo Montemezzi", "Ildebrando Pizzetti", "Ottorino Respighi",
           "Luigi Dallapiccola", "Luigi Nono", "Luciano Berio", "Gian Francesco Malipiero", "Nino Rota", "Errico Petrella",
           "Filippo Marchetti", "Carlo Pedrotti", "Giuseppe Mosca", "Antonio Smareglia", "Alberto Franchetti", "Carlo Coccia",
           "Giuseppe Gazzaniga", "Antonio Caldara", "Francesco Cavalli", "Stefano Landi", "Jacopo Peri", "Ferdinando Bertoni",
           "Niccolò Piccinni", "Antonio Carlos Gomes", "Wolfgang Amadeus Mozart", "George Frideric Handel",
           "Christoph Willibald Gluck", "Joseph Haydn", "Vicente Martín y Soler", "Luigi and Federico Ricci",
           "Gian Carlo Menotti", "Luigi Cherubini", "Giacomo Meyerbeer", "Reinhard Keiser", "Georg Philipp Telemann",
           "Antonio Vivaldi", "Franco Alfano", "Melesio Morales"],
    "de": ["Richard Wagner", "Richard Strauss", "Johann Strauss II", "Ludwig van Beethoven", "Carl Maria von Weber",
           "Engelbert Humperdinck", "Albert Lortzing", "Friedrich von Flotow", "Peter Cornelius", "Otto Nicolai",
           "Heinrich Marschner", "Franz Lehár", "Emmerich Kálmán", "Karl Millöcker", "Carl Zeller", "Franz von Suppé",
           "Richard Heuberger", "Heinrich Berté", "Paul Hindemith", "Carl Orff", "Hans Werner Henze", "Ernst Krenek",
           "Alexander von Zemlinsky", "Alban Berg", "Arnold Schoenberg", "Franz Schreker", "Erich Wolfgang Korngold",
           "Hans Pfitzner", "Franz Schubert", "Robert Schumann", "Wilhelm Kienzl", "Victor Ernst Nessler", "Karl Goldmark",
           "Giselher Klebe", "Wolfgang Fortner", "Werner Egk", "Boris Blacher", "Paul Dessau", "Gottfried von Einem",
           "Aribert Reimann", "Wolfgang Rihm", "Bernd Alois Zimmermann", "Udo Zimmermann", "Karl Amadeus Hartmann",
           "Friedrich Cerha", "Beat Furrer", "Hans-Jürgen von Bose", "Heinz Holliger", "Walter Braunfels", "Othmar Schoeck",
           "Hugo Wolf", "Berthold Goldschmidt", "Viktor Ullmann", "Mauricio Kagel", "Karlheinz Stockhausen",
           "E. T. A. Hoffmann", "Georg Benda", "Adriana Hoelszky", "Isang Yun", "Siegfried Wagner", "Kurt Weill",
           "Ferruccio Busoni", "Eugen d'Albert", "György Ligeti", "Krzysztof Penderecki", "Alfred Schnittke"],
    "fr": ["Georges Bizet", "Charles Gounod", "Jules Massenet", "Hector Berlioz", "Jacques Offenbach", "Fromental Halévy",
           "Daniel-François-Esprit Auber", "Adolphe Adam", "François-Adrien Boieldieu", "Léo Delibes", "Ambroise Thomas",
           "Camille Saint-Saëns", "Claude Debussy", "Maurice Ravel", "Francis Poulenc", "Jean-Philippe Rameau",
           "Jean-Baptiste Lully", "Gustave Charpentier", "Ernest Chausson", "Paul Dukas", "Gabriel Fauré", "Jacques Ibert",
           "Édouard Lalo", "Étienne Méhul", "Ernest Reyer", "Albert Roussel", "Marcel Landowski", "Olivier Messiaen",
           "Darius Milhaud", "Arthur Honegger", "Jean-Jacques Rousseau", "Joseph Bodin Boismortier",
           "Philippe II, Duke of Orléans", "Kaija Saariaho"],
    "ru": ["Pyotr Ilyich Tchaikovsky", "Modest Mussorgsky", "Nikolai Rimsky-Korsakov", "Mikhail Glinka", "Alexander Borodin",
           "Sergei Prokofiev", "Sergei Rachmaninoff", "Dmitri Shostakovich", "Igor Stravinsky", "Anton Rubinstein",
           "Rodion Shchedrin"],
    "en": ["Henry Purcell", "Benjamin Britten", "John Adams", "Philip Glass", "Samuel Barber", "Leonard Bernstein",
           "John Corigliano", "Michael Daugherty", "Jonathan Dove", "George Gershwin", "Scott Joplin", "Michael Tippett",
           "Gustav Holst", "Thomas Adès", "John Blow", "Vincent Youmans", "John Cage", "Steve Reich", "Lorin Maazel",
           "Edward Rushton"],
    "cs": ["Leoš Janáček", "Bedřich Smetana", "Antonín Dvořák", "Bohuslav Martinů", "Zdeněk Fibich", "Jaromír Weinberger"],
    "es": ["Manuel de Falla", "Enrique Granados", "Tomás Bretón", "Emilio Arrieta", "José Pablo Moncayo", "Felipe Boero",
           "Alberto Ginastera", "José María Usandiaga", "Tomás de Torrejón y Velasco", "Antonio Literes", "Daniel Catán",
           "Osvaldo Golijov", "Astor Piazzolla", "Jesús Guridi", "María Suárez", "Reveriano Soutullo", "Amadeo Vives",
           "Ruperto Chapí", "Federico Chueca", "Pablo Sorozábal", "Federico Moreno Torroba", "Jacinto Guerrero", "José Serrano",
           "Francisco Asenjo Barbieri", "Gerónimo Giménez", "Manuel Penella", "Pablo Luna", "Joaquín Gaztambide", "Tomás Bretón"],
    "hu": ["Béla Bartók", "Zoltán Kodály", "Péter Eötvös"],
    "pl": ["Karol Szymanowski", "Stanisław Moniuszko"],
    "da": ["Carl Nielsen", "Per Nørgård"],
    "hy": ["Armen Tigranian"],
    "no": ["Antonio Bibalo"],
    "hr": ["Ivo Josipović"],
}
ORIGINAL = {c: code for code, cs in ORIGINAL.items() for c in cs}

# (composer, canonical opera) -> language, where an opera departs from its composer's usual language.
OPERA_ORIGINAL = {
    ("Wolfgang Amadeus Mozart", "Die Zauberflöte"): "de", ("Wolfgang Amadeus Mozart", "Die Entführung aus dem Serail"): "de",
    ("Wolfgang Amadeus Mozart", "Der Schauspieldirektor"): "de", ("Wolfgang Amadeus Mozart", "Bastien und Bastienne"): "de",
    ("Wolfgang Amadeus Mozart", "Zaide"): "de", ("Wolfgang Amadeus Mozart", "Thamos, König in Ägypten"): "de",
    ("Wolfgang Amadeus Mozart", "Die Schuldigkeit des ersten Gebots"): "de", ("Wolfgang Amadeus Mozart", "Apollo et Hyacinthus"): "la",
    ("George Frideric Handel", "Acis and Galatea"): "en", ("George Frideric Handel", "Semele"): "en", ("George Frideric Handel", "Belshazzar"): "en",
    ("Christoph Willibald Gluck", "Iphigénie en Aulide"): "fr", ("Christoph Willibald Gluck", "Iphigénie en Tauride"): "fr",
    ("Christoph Willibald Gluck", "Armide"): "fr", ("Christoph Willibald Gluck", "Echo et Narcisse"): "fr",
    ("Gioachino Rossini", "Guillaume Tell"): "fr", ("Gioachino Rossini", "Le comte Ory"): "fr",
    ("Gioachino Rossini", "Le siège de Corinthe"): "fr", ("Gioachino Rossini", "Moïse et Pharaon"): "fr",
    ("Gaetano Donizetti", "La favorite"): "fr", ("Gaetano Donizetti", "La fille du régiment"): "fr",
    ("Gaetano Donizetti", "Dom Sébastien"): "fr", ("Gaetano Donizetti", "Le duc d'Albe"): "fr",
    ("Giuseppe Verdi", "Don Carlos"): "fr", ("Giuseppe Verdi", "Les vêpres siciliennes"): "fr", ("Giuseppe Verdi", "Jérusalem"): "fr",
    ("Luigi Cherubini", "Medea"): "fr",
    ("Antonio Salieri", "Tarare"): "fr",
    ("Gaspare Spontini", "La vestale"): "fr", ("Gaspare Spontini", "Fernand Cortez"): "fr", ("Gaspare Spontini", "Agnes von Hohenstaufen"): "de",
    ("Gian Carlo Menotti", "Amelia al ballo"): "it",
    ("Carl Orff", "Carmina Burana"): "la", ("Carl Orff", "Catulli Carmina"): "la", ("Carl Orff", "Trionfo di Afrodite"): "la",
    ("Hans Werner Henze", "The English Cat"): "en", ("Hans Werner Henze", "We Come to the River"): "en",
    ("Kurt Weill", "Street Scene"): "en",
    ("Igor Stravinsky", "The Rake's Progress"): "en", ("Igor Stravinsky", "Oedipus Rex"): "la",
    ("Sergei Prokofiev", "The Love for Three Oranges"): "fr",
    ("Bohuslav Martinů", "Juliette"): "fr", ("Bohuslav Martinů", "The Greek Passion"): "en",
    ("Ferruccio Busoni", "Turandot"): "de", ("Ferruccio Busoni", "Arlecchino"): "de",
    ("Philip Glass", "La Belle et la Bête"): "fr",
    ("Isaac Albéniz", "Merlin"): "en", ("Isaac Albéniz", "Henry Clifford"): "en",
    ("Franco Alfano", "Cyrano de Bergerac"): "fr",
    ("George Enescu", "Œdipe"): "fr", ("Sergei Rachmaninoff", "Francesca da Rimini"): "ru",
    ("Péter Eötvös", "Lady Sarashina"): "en",
    ("Hans-Jürgen von Bose", "63: Dream Palace"): "en",
    ("Antonio Bibalo", "Macbeth"): "en", ("Antonio Bibalo", "The Smile at the Foot of the Ladder"): "en",
    ("Arthur Honegger", "Antigone"): "fr",
    ("Jean-Baptiste Lully", "Armide"): "fr",
    ("Giacomo Meyerbeer", "Le prophète"): "fr", ("Giacomo Meyerbeer", "L'Africaine"): "fr", ("Giacomo Meyerbeer", "Les Huguenots"): "fr",
    ("Giacomo Meyerbeer", "Robert le diable"): "fr", ("Giacomo Meyerbeer", "Dinorah"): "fr",
    ("Mikhail Glinka", "A Life for the Tsar"): "ru",
}
OPERA_ORIGINAL = {(c, slug(o)): lang for (c, o), lang in OPERA_ORIGINAL.items()}

# canonical composer -> { slug(title as a source writes it): canonical title }.
# A value may be (title, composer) when Kareol's index filed the work under the previous composer.
OPERAS = {
    "Wolfgang Amadeus Mozart": {
        "ascanio-en-alba": "Ascanio in Alba", "asi-hacen-todas": "Così fan tutte", "bastian-y-bastiana": "Bastien und Bastienne",
        "el-sueno-de-escipion": "Il sogno di Scipione", "idomeneo-rey-de-creta": "Idomeneo, re di Creta",
        "idomeneo-re-di-creta": "Idomeneo, re di Creta", "la-clemencia-de-tito": "La clemenza di Tito",
        "la-oca-del-cairo": "L'oca del Cairo", "lucio-sila": "Lucio Silla", "mitridates-rey-del-ponto": "Mitridate, re di Ponto",
        "mitridate-re-di-ponto": "Mitridate, re di Ponto", "the-magic-flute": "Die Zauberflöte", "zaida": "Zaide",
        "le-nozze-di-figaro": "Le nozze di Figaro", "il-re-pastore": "Il re pastore", "la-finta-giardiniera": "La finta giardiniera",
        "la-finta-semplice": "La finta semplice", "lo-sposo-deluso": "Lo sposo deluso"},
    "Giuseppe Verdi": {
        "atila": "Attila", "don-carlos-don-carlo": "Don Carlos", "el-corsario": "Il corsaro", "el-trovador": "Il trovatore",
        "i-lombardi-alla-prima-crociata": "I Lombardi alla prima crociata", "i-vespri-siciliani": "Les vêpres siciliennes",
        "juana-de-arco": "Giovanna d'Arco", "la-batalla-de-legnano": "La battaglia di Legnano", "la-extraviada": "La traviata",
        "la-fuerza-del-destino": "La forza del destino", "la-forza-del-destino": "La forza del destino",
        "oberto-conde-de-san-bonifacio": "Oberto, conte di San Bonifacio", "oberto-conte-di-san-bonifacio": "Oberto, conte di San Bonifacio",
        "otelo": "Otello", "un-ballo-in-maschera": "Un ballo in maschera", "un-giorno-di-regno": "Un giorno di regno",
        "un-giorno-di-regno-il-finto-stanislao": "Un giorno di regno", "il-trovatore": "Il trovatore", "la-traviata": "La traviata",
        "i-masnadieri": "I masnadieri"},
    "Giacomo Puccini": {"el-tabardo": "Il tabarro", "il-tabarro": "Il tabarro", "la-boheme": "La bohème", "sor-angelica": "Suor Angelica",
        "la-fanciulla-del-west": "La fanciulla del West", "la-rondine": "La rondine"},
    "Richard Wagner": {"der-fliegende-hollander": "Der fliegende Holländer", "rienzi-der-letzte-der-tribunen": "Rienzi",
        "sigfrido": "Siegfried", "tristan-e-isolda": "Tristan und Isolde"},
    "Gioachino Rossini": {
        "el-asedio-de-corinto": "Le siège de Corinthe", "el-barbero-de-sevilla": "Il barbiere di Siviglia", "el-conde-ory": "Le comte Ory",
        "le-comte-ory": "Le comte Ory", "el-senor-bruschino": "Il signor Bruschino", "el-turco-en-italia": "Il turco in Italia",
        "il-turco-in-italia": "Il turco in Italia", "el-viaje-a-reims": "Il viaggio a Reims",
        "elisabetta-regina-dinghilterrra": "Elisabetta, regina d'Inghilterra", "guillermo-tell": "Guillaume Tell",
        "linganno-felice": "L'inganno felice", "litaliana-in-algeri": "L'italiana in Algeri", "la-italiana-en-argel": "L'italiana in Algeri",
        "loccasione-fa-il-ladro": "L'occasione fa il ladro", "la-cenerentola-ossia-la-bonta-in-trionfo": "La Cenerentola",
        "la-gazza-ladra": "La gazza ladra", "la-letra-de-cambio-matrimonial": "La cambiale di matrimonio",
        "la-piedra-del-parangon": "La pietra del paragone", "la-scala-di-seta": "La scala di seta",
        "moises-y-el-faraon": "Moïse et Pharaon", "otelo": "Otello", "otello-ossia-il-moro-di-venezia": "Otello",
        "semiramis": "Semiramide", "tancredo": "Tancredi", "blanca-y-falliero": "Bianca e Falliero", "ciro-en-babilonia": "Ciro in Babilonia",
        "demetrio-y-polibio": "Demetrio e Polibio", "eduardo-y-cristina": "Eduardo e Cristina", "ricardo-y-zoraida": "Ricciardo e Zoraide",
        "torvaldo-y-dorliska": "Torvaldo e Dorliska", "matilde-de-shabran": "Matilde di Shabran",
        "matilde-de-shabran-version-napoles": "Matilde di Shabran"},
    "Gaetano Donizetti": {
        "alahor-en-granada": "Alahor in Granata", "alfredo-el-grande": "Alfredo il grande", "alina-reina-de-golconda": "Alina, regina di Golconda",
        "ana-bolena": "Anna Bolena", "don-sebastian-rey-de-portugal": "Dom Sébastien", "el-asedio-de-calais": "L'assedio di Calais",
        "el-castillo-de-kenilworth": "Il castello di Kenilworth", "el-duque-de-alba": "Le duc d'Albe", "el-elixir-de-amor": "L'elisir d'amore",
        "lelisir-damore": "L'elisir d'amore", "el-paria": "Il paria", "emilia-de-liverpool": "Emilia di Liverpool",
        "gabriela-de-vergy": "Gabriella di Vergy", "gemma-de-vergy": "Gemma di Vergy", "il-campanello-di-notte": "Il campanello",
        "la-favorita": "La favorite", "la-favorite": "La favorite", "la-fille-du-regiment": "La fille du régiment",
        "linda-de-chamonix": "Linda di Chamounix", "lucia-de-lammermoor": "Lucia di Lammermoor", "lucrecia-borgia": "Lucrezia Borgia",
        "maria-de-rohan": "Maria di Rohan", "maria-estuardo": "Maria Stuarda", "pia-de-tolomei": "Pia de' Tolomei",
        "rosmonda-de-inglaterra": "Rosmonda d'Inghilterra", "sancha-de-castilla": "Sancia di Castiglia", "zoraida-de-granada": "Zoraida di Granata"},
    "Vincenzo Bellini": {"beatriz-de-tenda": "Beatrice di Tenda", "el-pirata": "Il pirata", "i-capuleti-e-i-montecchi": "I Capuleti e i Montecchi",
        "la-extranjera": "La straniera", "la-sonambula": "La sonnambula", "la-sonnambula": "La sonnambula"},
    "Richard Strauss": {"ariadna-en-naxos": "Ariadne auf Naxos", "dafne": "Daphne", "el-amor-de-danae": "Die Liebe der Danae",
        "electra": "Elektra", "salome": "Salome"},
    "Georges Bizet": {"ivan-iv": "Ivan IV", "les-pecheurs-de-perles-i-pescatori-di-perle": "Les pêcheurs de perles"},
    "Charles Gounod": {"faust-margarethe": "Faust", "fausto": "Faust", "mirella": "Mireille", "romeo-y-julieta": "Roméo et Juliette"},
    "Jules Massenet": {"amadis": "Amadis", "cleopatra": "Cléopâtre", "el-cid": "Le Cid", "el-juglar-de-nuestra-senora": "Le jongleur de Notre-Dame",
        "el-rey-de-lahore": "Le roi de Lahore", "manon": "Manon", "safo": "Sapho", "teresa": "Thérèse", "thais": "Thaïs"},
    "George Frideric Handel": {"acis-y-galatea": "Acis and Galatea", "admeto-rey-de-tesalia": "Admeto", "agripina": "Agrippina",
        "jerjes": "Serse", "julio-cesar-en-egipto": "Giulio Cesare", "giulio-cesare-in-egitto": "Giulio Cesare", "poro-rey-de-la-india": "Poro",
        "ricardo-primero-rey-de-inglaterra": "Riccardo Primo", "semele": "Semele", "tamerlan": "Tamerlano"},
    "Christoph Willibald Gluck": {"aecio": "Ezio", "alcestes": "Alceste", "eco-y-narciso": "Echo et Narcisse", "armida": "Armide",
        "ifigenia-en-aulide": "Iphigénie en Aulide", "ifigenia-en-tauride": "Iphigénie en Tauride", "orfeo-y-euridice": "Orfeo ed Euridice",
        "paris-y-elena": "Paride ed Elena"},
    "Pyotr Ilyich Tchaikovsky": {"eugenio-oneguin": "Eugene Onegin", "eugen-onegin": "Eugene Onegin", "la-dama-de-picas": "The Queen of Spades",
        "pique-dame": "The Queen of Spades", "mazepa": "Mazeppa", "orlenaskaya-deva": "The Maid of Orleans", "yolanda": "Iolanta"},
    "Leoš Janáček": {"aus-einem-totenhaus": "From the House of the Dead", "desde-la-casa-de-los-muertos": "From the House of the Dead",
        "el-caso-makropulos": "The Makropulos Affair", "vec-makropulos": "The Makropulos Affair", "jenufa": "Jenůfa",
        "katia-kabanova": "Káťa Kabanová", "katja-kabanova": "Káťa Kabanová", "sarka": "Šárka", "the-cunnig-little-vixen": "The Cunning Little Vixen"},
    "Modest Mussorgsky": {"boris-godunow": "Boris Godunov", "chowanschtschina": "Khovanshchina", "jovanshchina": "Khovanshchina"},
    "Jacques Offenbach": {"los-cuentos-de-hoffmann": "Les contes d'Hoffmann", "les-contes-dhoffmann": "Les contes d'Hoffmann"},
    "Claudio Monteverdi": {"el-regreso-de-ulises-a-la-patria": "Il ritorno d'Ulisse in patria", "lincoronazione-di-poppea": "L'incoronazione di Poppea",
        "la-favola-dorfeo": "L'Orfeo"},
    "Henry Purcell": {"dido-y-eneas": "Dido and Aeneas", "aleko": ("Aleko", "Sergei Rachmaninoff"),
        "francesca-de-rimini": ("Francesca da Rimini", "Sergei Rachmaninoff")},
    "Sergei Rachmaninoff": {"skupoi-rytsar": "The Miserly Knight", "francesca-de-rimini": "Francesca da Rimini", "el-caballero-avaro": "The Miserly Knight"},
    "George Enescu": {"edipo": "Œdipe"},
    "Franco Alfano": {"la-leyenda-de-sakuntala": "La leggenda di Sakùntala"},
    "Stanisław Moniuszko": {"straszny-dwor": "The Haunted Manor"},
    "Benjamin Britten": {"muerte-en-venecia": "Death in Venice"},
    "Pietro Mascagni": {"caballerosidad-rustica": "Cavalleria rusticana", "cavalleria-rusticana": "Cavalleria rusticana",
        "el-amigo-fritz": "L'amico Fritz", "el-pequeno-marat": "Il piccolo Marat", "guillermo-ratcliff": "Guglielmo Ratcliff", "neron": "Nerone"},
    "Ruggero Leoncavallo": {"i-pagliacci": "Pagliacci", "edipo-rey": "Edipo re", "zaza": "Zazà"},
    "Bedřich Smetana": {"prodana-nevesta": "The Bartered Bride", "certova-stena": "The Devil's Wall", "hubicka": "The Kiss", "libuse": "Libuše"},
    "Antonín Dvořák": {"cert-a-kaca": "The Devil and Kate", "edipo": ("Œdipe", "George Enescu"), "lady-sarashina": ("Lady Sarashina", "Péter Eötvös")},
    "Hector Berlioz": {"beatriz-y-benedicto": "Béatrice et Bénédict", "los-troyanos": "Les Troyens"},
    "Alexander Borodin": {"el-principe-igor": "Prince Igor", "knjas-igor": "Prince Igor"},
    "Mikhail Glinka": {"ruslan-y-liudmila": "Ruslan and Lyudmila", "una-vida-por-el-zar-o-ivan-susanin": "A Life for the Tsar"},
    "Nikolai Rimsky-Korsakov": {"kashchey-el-inmortal": "Kashchey the Immortal",
        "la-leyenda-de-la-ciudad-invisible-de-kitezh-y-la-doncella-fevroniya": "The Legend of the Invisible City of Kitezh",
        "la-novia-del-zar-tsarskaya-nevesta-the-tsar-s-bride-mlada": "The Tsar's Bride", "zarskaja-newesta": "The Tsar's Bride",
        "maiskaia-notsh": "May Night", "mozart-y-salieri": "Mozart and Salieri", "sneguroshka": "The Snow Maiden"},
    "Sergei Prokofiev": {"betrothal-in-a-monastery-or-the-duenna": "Betrothal in a Monastery", "the-duenna-or-betrothal-in-a-monastery": "Betrothal in a Monastery",
        "lyubov-k-tryom-apelsinam": "The Love for Three Oranges", "die-liebe-zu-den-drei-orangen": "The Love for Three Oranges",
        "the-gambler": "The Gambler", "vajna-i-mir": "War and Peace"},
    "Dmitri Shostakovich": {"ledi-macbet-mzenskowo-ujesda": "Lady Macbeth of Mtsensk", "ladi-makbet-mzenskogo-ujesda": "Lady Macbeth of Mtsensk",
        "nos": "The Nose", "the-big-lightning": "The Big Lightning"},
    "Igor Stravinsky": {"edipo-rey": "Oedipus Rex", "le-rossignol": "Le Rossignol"},
    "Claude Debussy": {"pelleas-y-melisenda": "Pelléas et Mélisande"},
    "Camille Saint-Saëns": {"enrique-viii": "Henry VIII", "sanson-y-dalila": "Samson et Dalila"},
    "Fromental Halévy": {"la-judia": "La Juive"},
    "Daniel-François-Esprit Auber": {"el-domino-negro": "Le domino noir", "le-domino-noir": "Le domino noir",
        "fra-diavolo-ou-lhotellerie-de-terracine": "Fra Diavolo", "manon-lescaut": "Manon Lescaut"},
    "Arrigo Boito": {"mefistofeles": "Mefistofele"},
    "Domenico Cimarosa": {"el-maestro-de-capilla": "Il maestro di cappella", "el-matrimonio-secreto": "Il matrimonio segreto"},
    "Francesco Cilea": {"la-arlesiana": "L'arlesiana"},
    "Joseph Haydn": {"el-mundo-de-la-luna": "Il mondo della luna"},
    "Giovanni Battista Pergolesi": {"adriano-en-siria": "Adriano in Siria", "livietta-y-tracollo": "Livietta e Tracollo", "la-serva-padrona": "La serva padrona"},
    "Giovanni Paisiello": {"nina": "Nina, o sia La pazza per amore", "nina-ossia-la-pazza-per-amore": "Nina, o sia La pazza per amore"},
    "Amilcare Ponchielli": {"los-lituanos": "I Lituani"},
    "Giacomo Meyerbeer": {"el-profeta": "Le prophète", "la-africana": "L'Africaine", "los-hugonotes": "Les Huguenots",
        "roberto-el-diablo": "Robert le diable", "semiramis": "Semiramide"},
    "Gian Carlo Menotti": {"amahl-y-los-visitantes-de-la-noche": "Amahl and the Night Visitors", "amelia-all-ballo": "Amelia al ballo",
        "el-consul": "The Consul", "el-telefono": "The Telephone", "the-telephone-ou-lamour-a-trois": "The Telephone", "golovin": "Maria Golovin",
        "la-medium": "The Medium", "the-old-maid-and-the-thief": "The Old Maid and the Thief", "the-saint-of-de-bleecker-street": "The Saint of Bleecker Street"},
    "Philip Glass": {"akhenaton": "Akhnaten", "akhnaton": "Akhnaten", "la-bella-y-la-bestia": "La Belle et la Bête"},
    "Paul Hindemith": {"mathis-der-maler": "Mathis der Maler", "asesino-esperanza-de-las-mujeres": "Mörder, Hoffnung der Frauen", "nusch-nuschi": "Das Nusch-Nuschi", "santa-susana": "Sancta Susanna"},
    "Ernst Krenek": {"el-dictador": "Der Diktator", "jonny-spielt-auf": "Jonny spielt auf"},
    "Albert Lortzing": {"der-wildschutz-oder-die-stimme-der-natur": "Der Wildschütz", "zar-und-zimmermann-oder-die-zwei-peter": "Zar und Zimmermann"},
    "Bohuslav Martinů": {"la-pasion-griega": "The Greek Passion", "tri-prani": "The Three Wishes"},
    "Carl Maria von Weber": {"abu-hassan": "Abu Hassan", "oberon": "Oberon"},
    "Friedrich von Flotow": {"marta": "Martha", "martha-oder-der-markt-zu-richmond": "Martha"},
    "Béla Bartók": {"a-kekzsakallu-herceg-vara": "Bluebeard's Castle", "herzog-blaubarts-burg": "Bluebeard's Castle"},
    "Franz Schubert": {"alfonso-y-estrella": "Alfonso und Estrella", "fierrabras": "Fierrabras"},
    "Karol Szymanowski": {"rey-roger": "King Roger"},
    "Francis Poulenc": {"dialogos-de-carmelitas": "Dialogues des Carmélites", "les-dialogues-des-carmelites": "Dialogues des Carmélites",
        "la-voz-humana": "La voix humaine", "les-mamelles-de-tiresias": "Les mamelles de Tirésias"},
    "Maurice Ravel": {"lheure-spagnole": "L'heure espagnole"},
    "Antonio Salieri": {"tarare": "Tarare"},
    "Alban Berg": {"lulu": "Lulu"},
    "Arnold Schoenberg": {"moises-y-aaron": "Moses und Aron"},
    "Luigi Dallapiccola": {"el-prisionero": "Il prigioniero", "volo-di-notte": "Volo di notte"},
    "Luigi Nono": {"intolerancia-1960": "Intolleranza 1960"},
    "Luciano Berio": {"un-re-in-ascolta": "Un re in ascolto"},
    "Samuel Barber": {"vanesa": "Vanessa"},
    "George Gershwin": {"porgy-y-bess": "Porgy and Bess"},
    "John Adams": {"dr-atomico": "Doctor Atomic", "nixon-en-china": "Nixon in China"},
    "Gustave Charpentier": {"luisa": "Louise"},
    "György Ligeti": {"el-gran-macabro": "Le Grand Macabre"},
    "Heinrich Marschner": {"el-vampiro": "Der Vampyr"},
    "Viktor Ullmann": {"el-emperador-de-la-atlantida": "Der Kaiser von Atlantis", "der-kaiser-von-atlantis-oder-der-tod-dankt-ab": "Der Kaiser von Atlantis"},
    "Ermanno Wolf-Ferrari": {"el-secreto-de-susana": "Il segreto di Susanna", "i-quatro-rusteghi": "I quattro rusteghi"},
    "Ferruccio Busoni": {"arlequin": "Arlecchino"},
    "Engelbert Humperdinck": {"hansel-y-gretel": "Hänsel und Gretel"},
    "Riccardo Zandonai": {"francesca-de-rimini": "Francesca da Rimini"},
    "Otto Nicolai": {"el-templario": "Il templario"},
    "Ernest Chausson": {"el-rey-arturo": "Le roi Arthus"},
    "Édouard Lalo": {"el-rey-de-ys": "Le roi d'Ys"},
    "Étienne Méhul": {"jose-en-egipto": "Joseph"},
    "Paul Dukas": {"ariadna-y-barbazul": "Ariane et Barbe-bleue"},
    "Gabriel Fauré": {"penelope": "Pénélope"},
    "Jean-Jacques Rousseau": {"el-adivino-de-la-aldea": "Le devin du village"},
    "Jean-Baptiste Lully": {"armida": "Armide", "cadmo-y-harmonia": "Cadmus et Hermione"},
    "Stefano Landi": {"la-muerte-de-orfeo": "La morte d'Orfeo", "san-alessio": "Il Sant'Alessio"},
    "Jacopo Peri": {"euridice": "Euridice"},
    "Carl Nielsen": {"mascarada": "Maskarade"},
    "Karl Goldmark": {"die-konigin-von-saba": "Die Königin von Saba"},
    "Antonio Carlos Gomes": {"el-guarani": "Il Guarany"},
    "Gian Francesco Malipiero": {"el-capitan-spavento": "Il capitan Spavento"},
    "Isaac Albéniz": {"merlin": "Merlin", "cyrano-de-bergerac": ("Cyrano de Bergerac", "Franco Alfano"),
        "la-leyenda-de-sakuntala": ("La leggenda di Sakùntala", "Franco Alfano")},
    "Edvard Grieg": {"amaya": ("Amaya", "Jesús Guridi")},
    "José Pablo Moncayo": {"halka": ("Halka", "Stanisław Moniuszko"), "straszny-dwor": ("The Haunted Manor", "Stanisław Moniuszko")},
    "Anton Rubinstein": {"demon": "The Demon"},
    "Rodion Shchedrin": {"the-enchanted-wanderer": "The Enchanted Wanderer"},
    "Alfred Schnittke": {"schisn-s-idiotom": "Life with an Idiot"},
    "Jaromír Weinberger": {"svanda-dudak": "Švanda dudák"},
    "Zdeněk Fibich": {"sarka": "Šárka"},
    "Thomas Adès": {"powder-her-face": "Powder Her Face"},
    "Nino Rota": {"il-capello-di-paglia-di-firenze": "Il cappello di paglia di Firenze"},
    "Jean-Philippe Rameau": {"castor-y-polux": "Castor et Pollux", "hipolitp-y-aricia": "Hippolyte et Aricie",
        "las-indias-galantes": "Les Indes galantes", "pigmalion": "Pygmalion"},
    "Antonio Vivaldi": {"arsilda-reina-del-ponto": "Arsilda, regina di Ponto", "hercules-en-el-termodonte": "Ercole su'l Termodonte",
        "la-olimpiada": "L'Olimpiade", "moctezuma": "Motezuma"},
    "Saverio Mercadante": {"el-juramento": "Il giuramento", "francesca-de-rimini": "Francesca da Rimini",
        "horacios-y-curiacios": "Orazi e Curiazi", "los-dos-figaros": "I due Figaro"},
    "Gaspare Spontini": {"agnese-de-hohenstaufen": "Agnes von Hohenstaufen", "fernando-cortes": "Fernand Cortez", "la-vestal": "La vestale"},
}


def canonicalize(e):
    """Fold a source's spelling of composer and opera to the canonical form, keeping the source's title in listed_as."""
    composer = COMPOSERS.get(e["composer"], e["composer"])
    table = OPERAS.get(composer, {})
    hit = table.get(slug(e["opera"])) or (table.get(slug(e["listed_as"])) if e.get("listed_as") else None)
    if isinstance(hit, tuple):
        opera, composer = hit
    else:
        opera = hit or e["opera"]
    if slug(opera) != slug(e["opera"]) and "listed_as" not in e:
        e["listed_as"] = e["opera"]
    if e.get("listed_as") and slug(e["listed_as"]) == slug(opera):  # only case or accents differ: not worth a note
        del e["listed_as"]
    e["composer"] = composer
    e["opera"] = opera
    e["original"] = OPERA_ORIGINAL.get((composer, slug(opera)), ORIGINAL.get(composer))
    if e["source"] == "kareol.es":
        # Kareol pages are the original text beside a Spanish translation.
        e["languages"] = [e["original"], "es"] if e["original"] and e["original"] != "es" else ["es"]
        m = re.search(r"Listed as “(.+?)”", e.get("note", ""))
        if m and "listed_as" not in e:
            e["listed_as"] = m.group(1)
        e["note"] = re.sub(r"^Original \+ Spanish\.\s*(Listed as “.+?”\.\s*)?", "", e.get("note", "")).strip()
    return e


def normalize(entries):
    """Canonical names for every entry, then one spelling per (composer, opera) where only case differs."""
    for e in entries:
        canonicalize(e)
    forms = {}
    for e in entries:
        k = (e["composer"], slug(e["opera"]))
        forms.setdefault(k, {}).setdefault(e["opera"], 0)
        forms[k][e["opera"]] += 1 if e["source"] != "kareol.es" else 0.5
    for e in entries:
        e["opera"] = max(forms[(e["composer"], slug(e["opera"]))].items(), key=lambda kv: (kv[1], kv[0]))[0]
    return entries
