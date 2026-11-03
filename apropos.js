/* Page À propos : lit data/meta.json et data/site.json (écrits par le scraper à chaque
   passage) et en fait une démonstration vivante. Aucune bibliothèque, aucun chiffre
   écrit à la main : si un fichier manque, les zones concernées restent simplement vides. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var SITE = "https://lotent.fr";
  var meta = null, site = null, months = null;

  /* ── Langue et thème : mêmes clés que l'application (paf_lang, paf_theme) ── */
  function lang() { return document.documentElement.lang === "en" ? "en" : "fr"; }
  function L(fr, en) { return lang() === "en" ? en : fr; }
  function fmt(n) { return new Intl.NumberFormat(lang() === "en" ? "en-GB" : "fr-FR").format(n); }
  function readLang() {
    var v = "fr";
    try { var raw = localStorage.getItem("paf_lang"); v = raw ? JSON.parse(raw) : "fr"; }
    catch (e) { try { v = localStorage.getItem("paf_lang") || "fr"; } catch (e2) {} }
    document.documentElement.lang = v === "en" ? "en" : "fr";
    $("#lang-btn").textContent = lang() === "en" ? "FR" : "EN";
    $("#lang-btn").setAttribute("aria-label", L("Switch to English", "Passer en français"));
    document.title = L("À propos — Lotent", "About — Lotent");
  }
  function isDark() {
    var t = document.documentElement.dataset.theme;
    return t === "dark" || (!t && matchMedia("(prefers-color-scheme: dark)").matches);
  }
  function paintThemeIcon() {
    var moon = "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z";
    var sun = "M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z";
    $("#theme-icon").innerHTML = '<path d="' + (isDark() ? sun : moon) + '"/>';
  }
  function cssvar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function hsl(name, a) { return "hsl(" + cssvar(name) + (a === undefined ? "" : " / " + a) + ")"; }

  /* ── Chiffres du haut de page ─────────────────────────────────────────── */
  function renderFigures() {
    var s = meta && meta.stats;
    if (!s) return;
    $("#f-total").textContent = fmt(s.total);
    $("#f-upcoming").textContent = fmt(site ? site.events.upcoming : s.upcoming);
    $("#f-orgs").textContent = fmt(s.institutions);
    if (s.since) {
      $("#f-since").textContent = new Date(s.since + "T12:00:00").toLocaleDateString(lang() === "en" ? "en-GB" : "fr-FR", { month: "short", year: "numeric" });
    }
    if (meta.last_workflow_run) {
      var mins = Math.round((Date.now() - new Date(meta.last_workflow_run)) / 60000);
      var rtf = new Intl.RelativeTimeFormat(lang(), { numeric: "auto" });
      var txt = mins < 90 ? rtf.format(-mins, "minute") : mins < 2880 ? rtf.format(-Math.round(mins / 60), "hour") : rtf.format(-Math.round(mins / 1440), "day");
      $("#fresh").textContent = L("Dernière mise à jour automatique : ", "Last automatic update: ") + txt + ".";
    }
  }

  /* ── Valeurs insérées dans le texte (data-fill) ───────────────────────── */
  function fillValues() {
    if (!site) return;
    var p = site.pages, e = site.events, w = site.weights || {};
    var v = {
      "organisers": e.organisers, "geocoded": e.geocoded_places, "located": e.located,
      "p-events": p.events, "p-redirects": p.redirects, "p-organisers": p.organisers, "p-disciplines": p.disciplines,
      "p-selections": p.selections, "p-speakers": p.speakers, "ics": site.calendars.length + 1,
      "js-kb": w["app.js"] && w["app.js"].kb, "js-gz": w["app.js"] && w["app.js"].gz,
      "free": e.free, "online": e.online, "english": e.english, "images": e.with_image,
      "tests": site.tests.cases, "workflows": site.workflows.length, "months-n": months ? months.length : ""
    };
    $$("[data-fill]").forEach(function (el) {
      var k = el.getAttribute("data-fill");
      if (v[k] !== undefined && v[k] !== "") el.textContent = fmt(v[k]);
    });
    var t = $("#tree");
    if (t) {
      var rows = [
        ["e/", p.events, L("pages événement", "event pages") + (p.redirects ? " (+ " + fmt(p.redirects) + L(" redirections", " redirects") + ")" : "")],
        ["i/", p.organisers, L("pages organisateur", "organiser pages")],
        ["d/", p.disciplines, L("pages discipline", "discipline pages")],
        ["s/", p.selections, L("sélections", "selections")],
        ["p/", p.speakers, L("pages intervenant", "speaker pages")],
        ["data/cal/", site.calendars.length, L("calendriers .ics", ".ics calendars")]
      ];
      if (months) rows.push(["data/m/", months.length, L("mois d’agenda en JSON", "agenda months as JSON")]);
      var w1 = Math.max.apply(null, rows.map(function (r) { return r[0].length; }));
      var w2 = Math.max.apply(null, rows.map(function (r) { return fmt(r[1]).length; }));
      t.textContent = rows.map(function (r) {
        return r[0] + new Array(w1 - r[0].length + 3).join(" ") + new Array(w2 - fmt(r[1]).length + 1).join(" ") + fmt(r[1]) + "   " + r[2];
      }).join("\n");
    }
  }

  /* ── Pipeline : cinq étapes, onglets accessibles (sans JavaScript, tout est lisible) ── */
  function initSteps() {
    var tabs = $$(".step"), panels = $$(".panel");
    function show(i, focus) {
      tabs.forEach(function (t, j) { t.setAttribute("aria-selected", j === i ? "true" : "false"); t.tabIndex = j === i ? 0 : -1; });
      panels.forEach(function (p, j) { p.hidden = j !== i; });
      if (focus) tabs[i].focus();
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { show(i); });
      t.addEventListener("keydown", function (ev) {
        var k = ev.key, n = tabs.length;
        if (k === "ArrowRight" || k === "ArrowDown") { ev.preventDefault(); show((i + 1) % n, true); }
        else if (k === "ArrowLeft" || k === "ArrowUp") { ev.preventDefault(); show((i - 1 + n) % n, true); }
        else if (k === "Home") { ev.preventDefault(); show(0, true); }
        else if (k === "End") { ev.preventDefault(); show(n - 1, true); }
      });
    });
    show(0);
  }

  /* ── Carte : un point par lieu, sa taille = nombre d'événements ───────── */
  var mapState = { hidden: {}, hover: -1, pts: [], drawn: [] };
  var LANDMARKS = [["Notre-Dame", 48.8530, 2.3499], ["Tour Eiffel", 48.8584, 2.2945], ["Gare du Nord", 48.8809, 2.3553],
                   ["Place d’Italie", 48.8312, 2.3555]];
  function drawMap() {
    var cv = $("#map"); if (!cv || !site) return;
    var dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    var c = cv.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, w, h);
    var B = { n: 48.915, s: 48.805, w: 2.225, e: 2.47 }, kx = Math.cos(48.86 * Math.PI / 180);
    var W = (B.e - B.w) * kx, H = B.n - B.s, sc = Math.min(w / W, h / H) * 0.96;
    var ox = (w - W * sc) / 2, oy = (h - H * sc) / 2;
    function X(lng) { return ox + (lng - B.w) * kx * sc; }
    function Y(lat) { return oy + (B.n - lat) * sc; }
    // repères
    c.font = "12px " + cssvar("--sans").replace(/"/g, "'");
    c.fillStyle = hsl("--muted-foreground"); c.strokeStyle = hsl("--control");
    LANDMARKS.forEach(function (m) {
      var x = X(m[2]), y = Y(m[1]);
      c.beginPath(); c.moveTo(x - 4, y); c.lineTo(x + 4, y); c.moveTo(x, y - 4); c.lineTo(x, y + 4); c.stroke();
      c.fillText(m[0], x + 7, y + 4);
    });
    // points : les gros d'abord, pour ne pas cacher les petits
    var pts = site.points.map(function (p, i) { return { i: i, lat: p[0], lng: p[1], d: p[2], n: p[3], name: p[4] }; });
    var inside = pts.filter(function (p) { return p.lat >= B.s && p.lat <= B.n && p.lng >= B.w && p.lng <= B.e; });
    mapState.pts = inside; mapState.drawn = [];
    inside.slice().sort(function (a, b) { return b.n - a.n; }).forEach(function (p) {
      if (mapState.hidden[p.d]) return;
      var r = Math.min(16, 3 + Math.sqrt(p.n) * 1.5), x = X(p.lng), y = Y(p.lat);
      c.globalAlpha = 0.78; c.fillStyle = site.disciplines[p.d].color;
      c.beginPath(); c.arc(x, y, r, 0, 6.2832); c.fill();
      c.globalAlpha = 1; c.lineWidth = p.i === mapState.hover ? 2.5 : 1; c.strokeStyle = p.i === mapState.hover ? hsl("--foreground") : hsl("--background");
      c.stroke();
      mapState.drawn.push({ p: p, x: x, y: y, r: r });
    });
    var out = pts.length - inside.length, outN = pts.reduce(function (s, p) { return s + ((p.lat >= B.s && p.lat <= B.n && p.lng >= B.w && p.lng <= B.e) ? 0 : p.n); }, 0);
    $("#map-note").textContent = outN ? L(fmt(outN) + " événements dans " + fmt(out) + " lieux hors du cadre (Saclay, Nanterre, Marne-la-Vallée…).",
                                          fmt(outN) + " events in " + fmt(out) + " places outside the frame (Saclay, Nanterre, Marne-la-Vallée…).") : "";
  }
  function initMap() {
    var cv = $("#map"), tip = $("#tip"); if (!cv) return;
    var lg = $("#legend");
    lg.innerHTML = "";
    var tot = {};
    site.points.forEach(function (p) { tot[p[2]] = (tot[p[2]] || 0) + p[3]; });
    site.disciplines.forEach(function (d, i) {
      if (!tot[i]) return;
      var b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.setAttribute("aria-pressed", "true"); b.style.setProperty("--dc", d.color);
      b.innerHTML = "<i></i>" + (lang() === "en" ? DISC_EN[d.name] || d.name : d.name) + ' <span class="n">' + fmt(tot[i]) + "</span>";
      b.addEventListener("click", function () {
        mapState.hidden[i] = !mapState.hidden[i]; b.setAttribute("aria-pressed", mapState.hidden[i] ? "false" : "true"); drawMap();
      });
      lg.appendChild(b);
    });
    if (mapState.bound) { drawMap(); return; }
    mapState.bound = true;
    function pick(ev) {
      var r = cv.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top, best = null, bd = 1e9;
      mapState.drawn.forEach(function (d) {
        var dd = Math.hypot(d.x - x, d.y - y);
        if (dd <= d.r + 5 && dd < bd) { bd = dd; best = d; }
      });
      return best ? { d: best, x: x, y: y } : null;
    }
    cv.addEventListener("pointermove", function (ev) {
      var hit = pick(ev), id = hit ? hit.d.p.i : -1;
      if (id !== mapState.hover) { mapState.hover = id; drawMap(); }
      if (!hit) { tip.hidden = true; return; }
      var p = hit.d.p, dn = site.disciplines[p.d].name;
      tip.textContent = (p.name || L("Lieu", "Place")) + " — " + fmt(p.n) + " " + (p.n > 1 ? L("événements", "events") : L("événement", "event")) + " · " + (lang() === "en" ? DISC_EN[dn] || dn : dn);
      tip.hidden = false;
      tip.style.left = Math.min(hit.x + 14, cv.clientWidth - 200) + "px"; tip.style.top = Math.max(hit.y - 12, 4) + "px";
    });
    cv.addEventListener("pointerleave", function () { mapState.hover = -1; tip.hidden = true; drawMap(); });
    drawMap();
    var rt; window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(drawMap, 120); });
  }
  var DISC_EN = { "Mathématiques": "Mathematics", "Économie": "Economics", "Histoire": "History", "Philosophie": "Philosophy", "Littérature": "Literature",
                  "Sociologie & Anthropologie": "Sociology & Anthropology", "Droit & Sciences politiques": "Law & Political science", "Autre": "Other" };

  /* ── Barres : disciplines, organisateurs ──────────────────────────────── */
  function bars(el, rows) {
    var max = Math.max.apply(null, rows.map(function (r) { return r.n; })) || 1;
    el.innerHTML = rows.map(function (r) {
      var label = r.href ? '<a href="' + r.href + '">' + esc(r.label) + "</a>" : '<span class="l">' + esc(r.label) + "</span>";
      return '<li style="--dc:' + (r.color || "hsl(var(--foreground))") + '">' + label + '<span class="t"><i style="width:' + Math.max(1.5, r.n / max * 100).toFixed(1) + '%"></i></span><span class="n">' + fmt(r.n) + "</span></li>";
    }).join("");
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function renderBars() {
    bars($("#bars-disc"), site.disciplines.filter(function (d) { return d.n; }).sort(function (a, b) { return b.n - a.n; }).map(function (d) {
      return { label: lang() === "en" ? DISC_EN[d.name] || d.name : d.name, n: d.n, color: d.color, href: d.slug ? "d/" + d.slug + ".html" : "" };
    }));
    bars($("#bars-org"), site.organisers.map(function (o) { return { label: o.name, n: o.n, href: o.slug ? "i/" + o.slug + ".html" : "" }; }));
  }

  /* ── Événements par mois : l'historique conservé et l'agenda à venir ──── */
  function renderMonths() {
    var data = site.months.filter(function (m) { return m[0] >= "2026-03"; }), el = $("#months");
    if (!el || !data.length) return;
    var now = new Date().toISOString().slice(0, 7), W = 640, H = 200, padB = 24, padT = 8, bw = W / data.length;
    var max = Math.max.apply(null, data.map(function (m) { return m[1]; })), top = Math.ceil(max / 500) * 500 || 500;
    var g = "", i, y;
    for (i = 0; i <= 4; i++) { y = padT + (H - padB - padT) * (1 - i / 4); g += '<line class="gridline" x1="0" x2="' + W + '" y1="' + y + '" y2="' + y + '"/><text x="0" y="' + (y - 3) + '">' + fmt(Math.round(top * i / 4)) + "</text>"; }
    data.forEach(function (m, k) {
      var hgt = (H - padB - padT) * m[1] / top, x = k * bw + bw * 0.14, cls = m[0] < now ? "past" : "future";
      var d = new Date(m[0] + "-15T12:00:00"), lab = d.toLocaleDateString(lang() === "en" ? "en-GB" : "fr-FR", { month: "short" }).replace(".", "");
      g += '<g class="m"><title>' + d.toLocaleDateString(lang() === "en" ? "en-GB" : "fr-FR", { month: "long", year: "numeric" }) + " : " + fmt(m[1]) + "</title>" +
           '<rect class="' + cls + '" x="' + x.toFixed(1) + '" y="' + (H - padB - hgt).toFixed(1) + '" width="' + (bw * 0.72).toFixed(1) + '" height="' + hgt.toFixed(1) + '" rx="2"/>' +
           (k % 2 === 0 || data.length < 10 ? '<text x="' + (x + bw * 0.36).toFixed(1) + '" y="' + (H - 8) + '" text-anchor="middle">' + lab + (m[0].slice(5) === "01" ? " " + m[0].slice(2, 4) : "") + "</text>" : "") + "</g>";
    });
    el.setAttribute("viewBox", "0 0 " + W + " " + H);
    el.innerHTML = g;
  }

  /* ── Générateur d'abonnement : une vraie URL de calendrier ────────────── */
  function initGenerator() {
    var kind = $("#gen-kind"), item = $("#gen-item"), out = $("#gen-out"), toast = $("#gen-toast");
    function items() {
      var k = kind.value;
      if (k === "all") { item.innerHTML = ""; item.disabled = true; return; }
      item.disabled = false;
      var list = site.calendars.filter(function (c) { return c.kind === k; }).sort(function (a, b) { return b.n - a.n || a.name.localeCompare(b.name); });
      item.innerHTML = list.map(function (c) {
        var nm = k === "disc" && lang() === "en" ? DISC_EN[c.name] || c.name : c.name;
        return '<option value="' + esc(c.slug) + '" data-n="' + c.n + '">' + esc(nm) + " — " + fmt(c.n) + "</option>";
      }).join("");
    }
    function update() {
      var all = kind.value === "all", slug = item.value;
      var url = SITE + (all ? "/data/calendar.ics" : "/data/cal/" + slug + ".ics"), webcal = url.replace(/^https:/, "webcal:");
      var n = all ? (site ? site.events.upcoming : 0) : +(item.selectedOptions[0] && item.selectedOptions[0].getAttribute("data-n") || 0);
      out.textContent = url;
      $("#gen-apple").href = webcal;
      $("#gen-google").href = "https://calendar.google.com/calendar/render?cid=" + encodeURIComponent(webcal);
      $("#gen-file").href = url;
      $("#gen-n").textContent = n ? L(fmt(n) + " événements à venir dans ce calendrier.", fmt(n) + " upcoming events in this calendar.") : "";
    }
    function labelKinds() {
      kind.options[0].textContent = L("Tout l’agenda", "The whole agenda");
      kind.options[1].textContent = L("Un organisateur", "One organiser");
      kind.options[2].textContent = L("Une discipline", "One discipline");
    }
    kind.addEventListener("change", function () { items(); update(); });
    item.addEventListener("change", update);
    $("#gen-copy").addEventListener("click", function () {
      var url = out.textContent;
      function done(ok) { toast.textContent = ok ? L("Lien copié.", "Link copied.") : L("Copie impossible : sélectionnez le lien à la main.", "Couldn't copy: select the link by hand."); }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(false); });
      else done(false);
    });
    labelKinds(); items(); update();
    window.__genRefresh = function () { var s = item.value; labelKinds(); items(); if (s) item.value = s; update(); };
  }

  /* ── Sous le capot : poids, pile, fiabilité ───────────────────────────── */
  function renderWeights() {
    var w = site.weights || {}, rows = [
      ["index.html", w["index.html"]], ["app.js", w["app.js"]], ["app.css", w["app.css"]],
      ["data/m/" + (w.month_name || "…") + ".json", w.month]
    ].filter(function (r) { return r[1]; });
    var total = rows.reduce(function (s, r) { return s + r[1].gz; }, 0), totalRaw = rows.reduce(function (s, r) { return s + r[1].kb; }, 0);
    $("#wbar").innerHTML = rows.map(function (r, i) { return '<i title="' + esc(r[0]) + '" style="width:' + (r[1].gz / total * 100).toFixed(1) + "%;opacity:" + (1 - i * 0.2).toFixed(2) + '"></i>'; }).join("");
    $("#wbody").innerHTML = rows.map(function (r, i) {
      return '<tr><td><span class="sw" style="opacity:' + (1 - i * 0.2).toFixed(2) + '"></span><code>' + esc(r[0]) + "</code></td><td>" + fmt(r[1].kb) + " Ko</td><td>" + fmt(r[1].gz) + " Ko</td></tr>";
    }).join("");
    $("#wfoot").innerHTML = "<tr><td>" + L("Premier affichage", "First load") + "</td><td>" + fmt(totalRaw) + " Ko</td><td>" + fmt(total) + " Ko</td></tr>";
  }
  function renderStack() {
    function chips(el, list) { el.innerHTML = list.map(function (d) { return "<li>" + esc(d[0]) + " <span>" + esc(d[1]) + "</span></li>"; }).join(""); }
    chips($("#stack-py"), site.stack.python); chips($("#stack-js"), site.stack.js);
    $("#ci-list").innerHTML = site.workflows.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("");
  }

  /* ── Sources : filtre ─────────────────────────────────────────────────── */
  function initSources() {
    var f = $("#src-filter"), items = $$(".srcs li"), cnt = $("#src-count");
    function norm(s) { return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
    function run() {
      var q = norm(f.value.trim()), n = 0;
      items.forEach(function (li) { var ok = !q || norm(li.textContent).indexOf(q) >= 0; li.hidden = !ok; if (ok) n++; });
      cnt.textContent = L(fmt(n) + " ligne" + (n > 1 ? "s" : "") + " sur " + fmt(items.length) + ".", fmt(n) + " of " + fmt(items.length) + " rows.");
    }
    f.addEventListener("input", run); run();
    window.__srcRefresh = run;
  }

  /* ── Démarrage ────────────────────────────────────────────────────────── */
  function renderAll() {
    renderFigures();
    if (site) { fillValues(); renderBars(); renderMonths(); renderWeights(); renderStack(); drawMap(); if (window.__genRefresh) window.__genRefresh(); }
    if (window.__srcRefresh) window.__srcRefresh();
  }
  readLang(); paintThemeIcon(); initSteps(); initSources();
  $("#lang-btn").addEventListener("click", function () {
    var cur = lang();
    try { localStorage.setItem("paf_lang", JSON.stringify(cur === "en" ? "fr" : "en")); } catch (e) {}
    readLang(); renderAll();
    if (site) { initMap(); }
  });
  $("#theme-btn").addEventListener("click", function () {
    var next = isDark() ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("paf_theme", JSON.stringify(next)); } catch (e) {}
    paintThemeIcon(); drawMap();
  });
  function get(u) { return fetch(u + "?" + Date.now()).then(function (r) { return r.json(); }).catch(function () { return null; }); }
  Promise.all([get("data/meta.json"), get("data/site.json"), get("data/m/index.json")]).then(function (r) {
    meta = r[0]; site = r[1]; months = r[2] && r[2].months;
    renderFigures();
    if (site) { renderAll(); initMap(); initGenerator(); }
  });
})();
