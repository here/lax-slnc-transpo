// Shared top and bottom menu for every page. Include once, at the end of <main>:
//   <script src="nav.js" data-root="./" data-page="home"></script>        (site root)
//   <script src="../nav.js" data-root="../" data-page="311"></script>     (one level down)
// Links are relative, so the site works at its GitHub Pages address and under aviary.herebox.org/slnc/.
// Social links mirror the ones on aviary.herebox.org (header icons; footer icons with labels).
(function () {
  const me = document.currentScript, root = me.dataset.root || "./", page = me.dataset.page || "";
  const items = [["home", "", "SLNC data"], ["311", "311/", "311 data"], ["transit", "transit/", "Transit & walking"], ["sunset", "sunset/", "Sunset Blvd East"]];
  const SOCIAL = [{"href": "https://github.com/here/lax-slnc-transpo", "rel": "noopener", "viewBox": "0 0 16 16", "d": "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z", "label": "Code and documentation on GitHub", "header": true}, {"href": "https://mikewaggoner.com", "rel": "noopener", "viewBox": "0 0 24 24", "d": "M12 2a10 10 0 100 20 10 10 0 000-20zm6.93 6h-2.95a15.7 15.7 0 00-1.38-3.56A8.03 8.03 0 0118.93 8zM12 4.04c.83 1.2 1.48 2.53 1.91 3.96h-3.82c.43-1.43 1.08-2.76 1.91-3.96zM4.26 14a8.2 8.2 0 010-4h3.38a16.5 16.5 0 000 4H4.26zm.81 2h2.95c.32 1.25.78 2.45 1.38 3.56A7.99 7.99 0 015.07 16zm2.95-8H5.07a7.99 7.99 0 014.33-3.56A15.7 15.7 0 008.02 8zM12 19.96c-.83-1.2-1.48-2.53-1.91-3.96h3.82c-.43 1.43-1.08 2.76-1.91 3.96zM14.34 14H9.66a14.7 14.7 0 010-4h4.68a14.7 14.7 0 010 4zm.25 5.56c.6-1.11 1.06-2.31 1.38-3.56h2.95a8.03 8.03 0 01-4.33 3.56zM16.36 14a16.5 16.5 0 000-4h3.38a8.2 8.2 0 010 4h-3.38z", "label": "Maintained by Mike Waggoner", "header": false}, {"href": "https://www.linkedin.com/in/mikehere", "rel": "noopener", "viewBox": "0 0 24 24", "d": "M20.45 20.45h-3.56v-5.57c0-1.33-.02-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 110-4.13 2.06 2.06 0 010 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z", "label": "LinkedIn", "header": true}, {"href": "https://bsky.app/profile/herebox.org", "rel": "noopener", "viewBox": "0 0 24 24", "d": "M5.2 2.6C7.95 4.67 10.9 8.86 12 11.13c1.1-2.27 4.05-6.46 6.8-8.53 1.98-1.49 5.2-2.65 5.2 1.03 0 .73-.42 6.16-.67 7.04-.86 3.06-3.98 3.84-6.76 3.37 4.86.83 6.1 3.57 3.43 6.31-5.07 5.2-7.29-1.31-7.86-2.97-.1-.31-.15-.45-.15-.33 0-.12-.05.02-.15.33-.57 1.66-2.79 8.17-7.86 2.97-2.67-2.74-1.43-5.48 3.43-6.31-2.78.47-5.9-.31-6.76-3.37C.42 9.79 0 4.36 0 3.63 0-.05 3.22 1.11 5.2 2.6z", "label": "Bluesky @herebox.org", "header": true}, {"href": "https://social.coop/@herebox", "rel": "noopener me", "viewBox": "0 0 24 24", "d": "M23.27 5.31C22.92 2.7 20.63.65 17.92.25 17.46.18 15.72 0 11.7 0h-.03C7.64 0 6.78.18 6.32.25 3.68.64 1.27 2.49.69 5.13.4 6.43.37 7.87.43 9.19c.08 1.89.1 3.78.27 5.66.12 1.25.33 2.49.63 3.71.56 2.25 2.81 4.12 5.02 4.89 2.36.8 4.9.94 7.34.38.27-.06.53-.13.8-.22.6-.19 1.29-.4 1.8-.76a.06.06 0 00.02-.05v-1.82a.05.05 0 00-.06-.05c-1.56.37-3.15.55-4.75.55-2.75 0-3.49-1.3-3.7-1.84a5.6 5.6 0 01-.32-1.45.05.05 0 01.07-.05c1.53.37 3.1.55 4.68.55.38 0 .76 0 1.14-.01 1.58-.04 3.25-.12 4.81-.43l.11-.02c2.46-.47 4.8-1.94 5.04-5.67.01-.15.03-1.54.03-1.7 0-.52.17-3.73-.03-5.7zm-3.79 9.27h-2.59V8.29c0-1.32-.56-2-1.68-2-1.24 0-1.86.8-1.86 2.38v3.45h-2.57V8.67c0-1.58-.62-2.38-1.86-2.38-1.12 0-1.68.68-1.68 2v6.29H4.65V8.1c0-1.32.34-2.37 1.01-3.15.7-.78 1.61-1.18 2.74-1.18 1.31 0 2.3.5 2.95 1.51l.64 1.07.64-1.07c.65-1.01 1.64-1.51 2.95-1.51 1.13 0 2.04.4 2.74 1.18.67.78 1.01 1.83 1.01 3.15v6.48z", "label": "Mastodon @herebox@social.coop", "header": true}];
  const SEE_ALSO = { href: "https://aviary.herebox.org/", label: "Los Angeles - Safe Streets Data Insights" };
  const style = document.createElement("style");
  style.textContent = `
.sitenav{display:flex;flex-wrap:wrap;align-items:center;gap:4px 18px;padding:10px 0;margin:0 0 14px;border-bottom:1px solid var(--line,#ddd)}
.sitenav a.pg{color:var(--fg,#1a1a1a);text-decoration:none;padding:4px 0;border-bottom:2px solid transparent;font-weight:500}
.sitenav a.pg:hover{border-bottom-color:var(--line,#ccc)}
.sitenav a.pg[aria-current=page]{border-bottom-color:var(--acc,#0b6bcb);color:var(--acc,#0b6bcb);font-weight:600}
.sitenav .social{display:flex;gap:6px;margin-left:auto}
.sitenav .social a{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:8px;border:1px solid var(--line,#ddd);color:var(--mut,#666)}
.sitenav .social a:hover{color:var(--fg,#1a1a1a);border-color:var(--mut,#999)}
.sitenav svg{width:16px;height:16px;fill:currentColor;flex:none}
.sitefoot{margin:28px 0 0;padding-top:14px;border-top:1px solid var(--line,#ddd);color:var(--mut,#666);font-size:.92em}
.sitefoot .pages{display:flex;flex-wrap:wrap;gap:4px 18px;margin-bottom:10px}
.sitefoot .pages a{color:var(--fg,#1a1a1a);text-decoration:none;font-weight:500}
.sitefoot .pages a[aria-current=page]{color:var(--acc,#0b6bcb);font-weight:600}
.sitefoot p{margin:4px 0}
.sitefoot .links{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin-top:10px}
.sitefoot .links a{display:inline-flex;align-items:center;gap:6px;color:var(--mut,#666);text-decoration:none}
.sitefoot .links a:hover{color:var(--fg,#1a1a1a)}
.sitefoot .links .sep{opacity:.6}
.sitefoot svg{width:14px;height:14px;fill:currentColor;flex:none}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}`;
  document.head.appendChild(style);
  const icon = s => `<svg viewBox="${s.viewBox}" aria-hidden="true"><path d="${s.d}"/></svg>`;
  const ext = s => `href="${s.href}" target="_blank" rel="${s.rel}"`;
  const pages = items.map(([id, href, label]) =>
    `<a class="pg" href="${root}${href}"${id === page ? ' aria-current="page"' : ""}>${label}</a>`).join("");
  const top = document.createElement("nav");
  top.className = "sitenav"; top.setAttribute("aria-label", "Site");
  top.innerHTML = pages + `<span class="social">` +
    SOCIAL.filter(s => s.header).map(s => `<a ${ext(s)} title="${s.label}">${icon(s)}<span class="vh">${s.label}</span></a>`).join("") + `</span>`;
  const foot = document.createElement("footer");
  foot.className = "sitefoot";
  foot.innerHTML = `<nav class="pages" aria-label="Site (bottom)">${pages.replace(/ class="pg"/g, "")}</nav>` +
    `<p>Data supporting Silver Lake Neighborhood Council</p>` +
    `<p>See also <a href="${SEE_ALSO.href}">${SEE_ALSO.label}</a></p>` +
    `<div class="links">` + SOCIAL.map(s => `<a ${ext(s)}>${icon(s)}<span>${s.label}</span></a>`).join(`<span class="sep" aria-hidden="true">·</span>`) + `</div>`;
  const main = me.closest("main") || document.body;
  main.prepend(top);
  main.append(foot);
})();
