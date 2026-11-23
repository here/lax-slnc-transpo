// Shared top and bottom menu for every page. Include once, at the end of <main>:
//   <script src="nav.js" data-root="./" data-page="home"></script>        (site root)
//   <script src="../nav.js" data-root="../" data-page="311"></script>     (one level down)
// Links are relative, so the site works at its GitHub Pages address and under aviary.herebox.org/slnc/.
(function () {
  const me = document.currentScript, root = me.dataset.root || "./", page = me.dataset.page || "";
  const items = [["home", "", "SLNC data"], ["311", "311/", "311 data"], ["transit", "transit/", "Transit & walking"], ["sunset", "sunset/", "Sunset Blvd"]];
  const style = document.createElement("style");
  style.textContent = `
.sitenav{display:flex;flex-wrap:wrap;align-items:center;gap:4px 18px;padding:10px 0;margin:0 0 14px;border-bottom:1px solid var(--line,#ddd)}
.sitenav.bottom{margin:28px 0 0;border-bottom:0;border-top:1px solid var(--line,#ddd);padding-top:14px}
.sitenav a{color:var(--fg,#1a1a1a);text-decoration:none;padding:4px 0;border-bottom:2px solid transparent;font-weight:500}
.sitenav a:hover{border-bottom-color:var(--line,#ccc)}
.sitenav a[aria-current=page]{border-bottom-color:var(--acc,#0b6bcb);color:var(--acc,#0b6bcb);font-weight:600}
.sitenav .tag{color:var(--mut,#666);font-size:.9em;margin-left:auto}`;
  document.head.appendChild(style);
  const build = (cls, tag) => {
    const n = document.createElement("nav");
    n.className = "sitenav " + cls;
    n.setAttribute("aria-label", cls === "top" ? "Site" : "Site (bottom)");
    n.innerHTML = items.map(([id, href, label]) =>
      `<a href="${root}${href}"${id === page ? ' aria-current="page"' : ""}>${label}</a>`).join("") +
      (tag ? `<span class="tag">${tag}</span>` : "");
    return n;
  };
  const main = me.closest("main") || document.body;
  main.prepend(build("top", ""));
  main.append(build("bottom", "Data supporting Silver Lake Neighborhood Council"));
})();
