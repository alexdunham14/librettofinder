(async function () {
  const list = document.getElementById("list"), q = document.getElementById("q"),
        sbs = document.getElementById("sbs"), lang = document.getElementById("lang"), count = document.getElementById("count");
  const NAMES = { it: "Italian", en: "English", de: "German", fr: "French", ru: "Russian", cs: "Czech", es: "Spanish", hu: "Hungarian", la: "Latin", pl: "Polish" };
  let rows = [];
  try { rows = await (await fetch("libretti.json", { cache: "no-cache" })).json(); }
  catch (e) { list.textContent = "Could not load libretti.json."; return; }

  // translation-language options from the data, English first
  const langs = new Set(rows.flatMap(r => r.languages));
  for (const l of [...langs].sort()) if (l !== "en") lang.insertAdjacentHTML("beforeend", `<option value="${l}">${NAMES[l] || l}</option>`);

  const p = new URLSearchParams(location.search);
  q.value = p.get("q") || ""; if (p.has("all")) sbs.checked = false; if (p.has("lang")) lang.value = p.get("lang");

  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const surname = c => c.trim().split(/\s+/).pop();
  const fold = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  function render() {
    const needle = fold(q.value.trim());
    const shown = rows.filter(r =>
      (!sbs.checked || r.side_by_side) &&
      (!lang.value || r.languages.includes(lang.value)) &&
      (!needle || needle.split(/\s+/).every(w => fold(r.opera + " " + r.composer).includes(w))));
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
      <h2>${esc(c)}</h2>
      <dl>${[...byComposer.get(c).keys()].sort((a, b) => fold(a).localeCompare(fold(b))).map(o => `
        <dt>${esc(o)}</dt>
        ${byComposer.get(c).get(o).sort((a, b) => b.side_by_side - a.side_by_side).map(r => `
        <dd><a href="${esc(r.url)}" rel="noopener">${r.languages.map(l => NAMES[l] || l).join(" + ")}${r.side_by_side ? ", side by side" : ", translation only"}</a>
          <small>${esc(r.source)}${r.url === r.wayback ? "" : ` · <a href="${esc(r.wayback)}" rel="noopener">archived</a>`}${r.note ? " · " + esc(r.note) : ""}</small></dd>`).join("")}`).join("")}
      </dl>`).join("")
      : '<p class="none">Nothing matches. Untick "side by side only" to see translation-only pages.</p>';
    const operas = new Set(rows.filter(r => r.side_by_side).map(r => r.composer + "|" + r.opera)).size;
    count.textContent = `${rows.length} links, ${operas} operas with a side-by-side text. Showing ${shown.length}.`;
  }
  q.addEventListener("input", render); sbs.addEventListener("change", render); lang.addEventListener("change", render);
  render();
})();
