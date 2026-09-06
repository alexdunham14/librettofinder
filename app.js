(async function () {
  const list = document.getElementById("list"), q = document.getElementById("q"),
        sbs = document.getElementById("sbs"), lang = document.getElementById("lang"), count = document.getElementById("count");
  const NAMES = { it: "Italian", en: "English", de: "German", fr: "French", ru: "Russian", cs: "Czech", es: "Spanish", hu: "Hungarian", la: "Latin", pl: "Polish", da: "Danish", hy: "Armenian", no: "Norwegian", hr: "Croatian" };
  const name = l => NAMES[l] || l;
  let rows = [];
  try { rows = await (await fetch("libretti.json", { cache: "no-cache" })).json(); }
  catch (e) { list.textContent = "Could not load libretti.json."; return; }

  // A translation is any language on the page that is not the opera's own.
  const translations = r => r.languages.filter(l => l !== r.original);
  const langs = new Set(rows.flatMap(translations));
  for (const l of [...langs].sort((a, b) => name(a).localeCompare(name(b)))) if (l !== "en") lang.insertAdjacentHTML("beforeend", `<option value="${l}">${name(l)}</option>`);

  const p = new URLSearchParams(location.search);
  q.value = p.get("q") || ""; if (p.has("all")) sbs.checked = false; if (p.has("lang")) lang.value = p.get("lang");

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const surname = c => c.trim().split(/\s+/).pop();
  const fold = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  // "Italian + English, side by side" / "Italian original" / "English translation"
  function label(r) {
    if (r.side_by_side) {
      const ls = r.original && r.languages.includes(r.original) ? [r.original, ...r.languages.filter(l => l !== r.original)] : r.languages;
      return (ls.length > 1 ? ls.map(name).join(" + ") : "original + " + name(ls[0])) + ", side by side";
    }
    const l = r.languages[0];
    return name(l) + (l === r.original ? " original" : r.original ? " translation" : " only");
  }

  function render() {
    const needle = fold(q.value.trim());
    const shown = rows.filter(r =>
      (!sbs.checked || r.side_by_side) &&
      (!lang.value || translations(r).includes(lang.value)) &&
      (!needle || needle.split(/\s+/).every(w => fold(r.opera + " " + r.composer + " " + (r.listed_as || "")).includes(w))));
    const u = new URL(location.href);
    needle ? u.searchParams.set("q", q.value.trim()) : u.searchParams.delete("q");
    sbs.checked ? u.searchParams.delete("all") : u.searchParams.set("all", "");
    lang.value === "en" ? u.searchParams.delete("lang") : u.searchParams.set("lang", lang.value);
    history.replaceState(null, "", u);

    const byComposer = new Map();
    for (const r of shown) {
      if (!byComposer.has(r.composer)) byComposer.set(r.composer, new Map());
      const ops = byComposer.get(r.composer);
      if (!ops.has(r.opera)) ops.set(r.opera, []);
      ops.get(r.opera).push(r);
    }
    const composers = [...byComposer.keys()].sort((a, b) => fold(surname(a)).localeCompare(fold(surname(b))));
    list.innerHTML = composers.length ? composers.map(c => `
      <h2>${esc(c)} <small>${byComposer.get(c).size}</small></h2>
      <dl>${[...byComposer.get(c).keys()].sort((a, b) => fold(a).localeCompare(fold(b))).map(o => `
        <dt>${esc(o)}</dt>
        ${byComposer.get(c).get(o).sort((a, b) => b.side_by_side - a.side_by_side || a.source.localeCompare(b.source)).map(r => `
        <dd><a href="${esc(r.url)}" rel="noopener">${esc(label(r))}</a>
          <small>${esc(r.source)}${r.url === r.wayback ? "" : ` · <a href="${esc(r.wayback)}" rel="noopener">archived</a>`}${r.listed_as ? ` · listed as “${esc(r.listed_as)}”` : ""}${r.note ? " · " + esc(r.note) : ""}</small></dd>`).join("")}`).join("")}
      </dl>`).join("")
      : '<p class="none">Nothing matches. Untick "side by side only" to see single-language pages, or set translation to "any".</p>';
    const operas = new Set(rows.filter(r => r.side_by_side).map(r => r.composer + "|" + r.opera)).size;
    const english = new Set(rows.filter(r => r.side_by_side && r.languages.includes("en")).map(r => r.composer + "|" + r.opera)).size;
    const shownOperas = new Set(shown.map(r => r.composer + "|" + r.opera)).size;
    count.textContent = `${operas} operas with a side-by-side text, ${english} of them with English · ${rows.length} links in all · showing ${shownOperas} opera${shownOperas === 1 ? "" : "s"}, ${shown.length} link${shown.length === 1 ? "" : "s"}.`;
  }
  q.addEventListener("input", render); sbs.addEventListener("change", render); lang.addEventListener("change", render);
  render();
})();
