/* Duval County, FL — Distress Intelligence — operator lead board (ported
   from el-paso-intel v5). Client-side only. Reads dashboard/data.json (or
   window.LEADS). Operator triage flags persist in localStorage; no backend. */
(function () {
  "use strict";

  // ---------- small helpers ----------
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function money(v) {
    var n = Number(v);
    return (v == null || v === "" || isNaN(n)) ? "—"
      : "$" + n.toLocaleString("en-US");
  }
  var MONTHS = { jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,oct:9,
    nov:10,dec:11 };
  function parseDate(s) {
    if (!s) return null;
    s = String(s).trim();
    var m = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (m) return new Date(+m[3], +m[1] - 1, +m[2]);
    m = s.match(/^([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})$/);
    if (m) {
      var mi = MONTHS[m[1].toLowerCase().slice(0, 3)];
      if (mi != null) return new Date(+m[3], mi, +m[2]);
    }
    m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
    var d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }
  var TODAY = (function () {
    var d = new Date(); d.setHours(0, 0, 0, 0); return d;
  })();
  function daysFromToday(d) {
    return d ? Math.round((d - TODAY) / 86400000) : null;
  }

  // ---------- state ----------
  var DATA = (typeof window !== "undefined" && window.LEADS) || null;
  var records = [];
  // Standing rule #5 — the board opens on ALL records, neutrally sorted.
  // Filters default to empty selection — when nothing is selected, the
  // filter is INACTIVE (show everything), not "show nothing". Click a
  // signal / owner type to filter to just it; click more to stack.
  var state = {
    search: "", saleWindow: "any", valMin: null, valMax: null,
    signals: {}, owners: {}, absentee: false, oos: false, review: false,
    multiOnly: false, sort: "recent", shown: 0, preset: "all",
    newOnly: false, last30Only: false,
    taxDefaultOnly: false, hideTinyBal: false,
    yearsDelinquent: "any", balMin: null,
    addrOnly: false
  };
  var PAGE = 60;
  var marked = loadMarked();   // Set of lead_id (localStorage)
  var skipped = {};            // session-only hide
  var filtered = [];
  var io = null;
  var sentinel = null;   // persistent JS node — never lives in index.html

  function loadMarked() {
    try {
      var raw = localStorage.getItem("duv_marked_v5");
      var arr = raw ? JSON.parse(raw) : [];
      var s = {}; arr.forEach(function (x) { s[x] = true; });
      return s;
    } catch (e) { return {}; }
  }
  function saveMarked() {
    try {
      localStorage.setItem("duv_marked_v5",
        JSON.stringify(Object.keys(marked)));
    } catch (e) { /* storage unavailable — non-fatal */ }
  }

  // ---------- preprocessing ----------
  function fclSignal(r) {
    var s = (r.signals || []).filter(function (x) {
      return x.signal_type === "foreclosure_notice";
    });
    return s.length ? s[0] : null;
  }
  function prep(r) {
    r.signal_types = r.signal_types || [];
    r.signals = r.signals || [];
    var fs = fclSignal(r);
    r._fcl = fs;
    r._isFcl = !!fs;
    var sd = fs ? parseDate(fs.sale_date) : null;
    r._saleDate = sd;
    r._days = daysFromToday(sd);
    r._assessed = Number(r.assessed_value) || 0;
    r._review = r.parcel_resolution_status === "REVIEW_REQUIRED";
    // For "recent" sort, prefer the server-computed most_recent_event_date
    // (which excludes snapshot sources — PA estate + TC delinquency — so
    // those don't get falsely pinned to "today"). Fall back to
    // latest_event_date for older payloads.
    r._filed = parseDate(r.most_recent_event_date) ||
               parseDate(r.latest_event_date);
    // Recency — county recorded/event date, NOT the scrape clock. Server
    // computed these once in the build step; they survive lead-card updates.
    r._isNew = !!r.is_new;
    r._within30d = !!r.recorded_within_30_days;
    r._daysSinceEvent = (typeof r.days_since_event === "number")
      ? r.days_since_event : null;
    r._taxDefault = !!r.tax_default;
    r._taxBalance = (typeof r.tax_balance_due === "number")
      ? r.tax_balance_due : 0;
    r._yearsDelinq = (typeof r.years_delinquent_floor === "number")
      ? r.years_delinquent_floor : 0;
    r._tier = urgencyTier(r);
    var taxd = r.signal_types.indexOf("state_tax_lien") >= 0 ||
      r.signal_types.indexOf("federal_tax_lien") >= 0;
    r._taxDelinquent = taxd;
    r._blob = [r.owner_name, r.property_full_address, r.mailing_full_address,
      r.legal_description, r.filer_entity,
      (r.signals || []).map(function (s) {
        return (s.instrument_numbers || []).join(" ");
      }).join(" ")].join(" ").toLowerCase();
  }
  function urgencyTier(r) {
    var d = r._days;
    // tier 1-2: imminent foreclosure sale by sale date.
    if (r._isFcl && d != null && d >= 0 && d <= 21) return 1;
    if (r._isFcl && d != null && d > 21 && d <= 60) return 2;
    // tier 3: tax-deed-pipeline progression (Applied/Sold/Certified/Escheated
    // — multi-year delinquent leads already moving through the deed sale
    // process; FL Ch. 197 requires 2+ years). NO estate-only clause here —
    // estate-titled property is just a probate signal, not an urgency
    // ranking on its own (standing rule #5).
    if (r._taxDefault && (r._yearsDelinq || 0) >= 2) return 3;
    if ((r.signal_count || 0) >= 2) return 4;
    // tier 5: stand-alone tax_default with meaningful balance.
    if (r._taxDefault && (r._taxBalance || 0) >= 1000) return 5;
    var tax = (r.signal_types || []).indexOf("state_tax_lien") >= 0 ||
      (r.signal_types || []).indexOf("federal_tax_lien") >= 0;
    if (tax && r.out_of_state_owner_flag) return 5;
    return 6;
  }

  // ---------- boot ----------
  function boot(payload) {
    records = (payload && payload.records) || [];
    records.forEach(prep);

    $("topStats").innerHTML = topStatsHtml(payload);
    // Standing rule #5/#6 — the build-status banner ("PARTIAL LEAD BOARD
    // (PARTIAL_BUILD) — v5.4.0 staged pipeline. Primary event sources: ...")
    // is internal build commentary and never renders on the client-facing
    // board. The #banner element is reused below by the fetch error-handler
    // to surface a "could not load data" message; it stays hidden on a
    // successful boot regardless of build_label.
    $("banner").hidden = true;

    buildPresets();
    buildSignalFilter();
    buildOwnerFilter();
    wireControls();
    setupObserver();
    render();
    document.documentElement.setAttribute("data-ready", "1");
  }

  function topStatsHtml(p) {
    var fclAddr = records.filter(function (r) {
      return r._isFcl && r.property_full_address;
    }).length;
    var soon = records.filter(function (r) {
      return r._isFcl && r._days != null && r._days >= 0 && r._days <= 21;
    }).length;
    var estates = records.filter(function (r) {
      return r.owner_type === "ESTATE";
    }).length;
    var newCount = (typeof p.new_leads === "number") ? p.new_leads
      : records.filter(function (r) { return r._isNew; }).length;
    var last30 = (typeof p.last_30d_leads === "number") ? p.last_30d_leads
      : records.filter(function (r) { return r._within30d; }).length;
    var taxDef = (typeof p.tax_default_leads === "number")
      ? p.tax_default_leads
      : records.filter(function (r) { return r._taxDefault; }).length;
    var taxBal = (typeof p.tax_balance_total_owed === "number")
      ? p.tax_balance_total_owed : 0;
    var act = p.actionable_leads != null ? p.actionable_leads : records.length;
    function st(n, l, cls) {
      return '<div class="topstat ' + (cls || "") + '"><div class="n">' +
        n + '</div><div class="l">' + l + "</div></div>";
    }
    var addrR = (typeof p.address_resolved_leads === "number")
      ? p.address_resolved_leads
      : records.filter(function (r) { return r.has_street_address; }).length;
    return st(records.length.toLocaleString(), "leads") +
      st(addrR.toLocaleString(), "address resolved") +
      st(newCount.toLocaleString(),
        "NEW today" + (p.refresh_date ? " (" + esc(p.refresh_date) + ")" : ""),
        "new") +
      st(last30.toLocaleString(), "filed last 30 days") +
      st(taxDef.toLocaleString(),
        "tax-default leads", "tax") +
      st(money(taxBal), "owed to county", "tax") +
      st(act.toLocaleString(), "actionable") +
      st(soon, "sale &le;21 days", "urgent") +
      st(estates, "estate-titled leads", "estate");
  }

  // ---------- sidebar ----------
  var PRESETS = [
    { id: "addrResolved", label: "Address resolved" },
    { id: "new", label: "NEW today" },
    { id: "last30", label: "Last 30 days" },
    { id: "fcl21", label: "Foreclosures — next 21 days" },
    { id: "estates", label: "Estate-titled properties" },
    { id: "oos", label: "Out-of-state absentees" },
    { id: "multi", label: "Multi-signal stacked" },
    { id: "tax", label: "Tax delinquent (all)" },
    { id: "tax2yr", label: "Tax delinquent 2+ yr" },
    { id: "tax5yr", label: "Tax delinquent 5+ yr" },
    { id: "all", label: "Show all" }
  ];
  function buildPresets() {
    var box = $("presets");
    PRESETS.forEach(function (p) {
      var b = document.createElement("button");
      b.className = "preset"; b.textContent = p.label; b.dataset.id = p.id;
      b.addEventListener("click", function () { applyPreset(p.id); });
      box.appendChild(b);
    });
  }
  function markPresetActive(id) {
    state.preset = id;
    Array.prototype.forEach.call($("presets").children, function (b) {
      b.classList.toggle("active", b.dataset.id === id);
    });
  }

  function buildSignalFilter() {
    var counts = {}, labels = {};
    records.forEach(function (r) {
      (r.signals || []).forEach(function (s) {
        counts[s.signal_type] = (counts[s.signal_type] || 0) + 1;
        labels[s.signal_type] = s.signal_label || s.signal_type;
      });
    });
    var box = $("signalFilter");
    Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })
      .forEach(function (t) {
        // Standing rule #5 — default UNSELECTED. Empty selection = no filter.
        state.signals[t] = false;
        var l = document.createElement("label");
        l.className = "chk";
        l.innerHTML = '<input type="checkbox" data-sig="' + esc(t) +
          '"> ' + esc(labels[t]) + '<span class="cnt">' +
          counts[t].toLocaleString() + "</span>";
        l.querySelector("input").addEventListener("change", function (e) {
          state.signals[t] = e.target.checked; markPresetActive("");
          render();
        });
        box.appendChild(l);
      });
  }
  function buildOwnerFilter() {
    var counts = {};
    records.forEach(function (r) {
      var o = r.owner_type || "UNKNOWN";
      counts[o] = (counts[o] || 0) + 1;
    });
    var box = $("ownerFilter");
    Object.keys(counts).sort().forEach(function (o) {
      // Standing rule #5 — default UNSELECTED.
      state.owners[o] = false;
      var l = document.createElement("label");
      l.className = "chk";
      l.innerHTML = '<input type="checkbox" data-own="' + esc(o) +
        '"> ' + esc(o) + '<span class="cnt">' +
        counts[o].toLocaleString() + "</span>";
      l.querySelector("input").addEventListener("change", function (e) {
        state.owners[o] = e.target.checked; markPresetActive(""); render();
      });
      box.appendChild(l);
    });
  }

  function wireControls() {
    var deb;
    $("search").addEventListener("input", function (e) {
      clearTimeout(deb);
      deb = setTimeout(function () {
        state.search = e.target.value.trim().toLowerCase(); render();
      }, 300);
    });
    $("saleWindow").addEventListener("change", function (e) {
      state.saleWindow = e.target.value; markPresetActive(""); render();
    });
    $("valMin").addEventListener("input", function (e) {
      state.valMin = e.target.value === "" ? null : Number(e.target.value);
      markPresetActive(""); render();
    });
    $("valMax").addEventListener("input", function (e) {
      state.valMax = e.target.value === "" ? null : Number(e.target.value);
      markPresetActive(""); render();
    });
    $("togAbsentee").addEventListener("change", function (e) {
      state.absentee = e.target.checked; markPresetActive(""); render();
    });
    $("togOos").addEventListener("change", function (e) {
      state.oos = e.target.checked; markPresetActive(""); render();
    });
    $("togReview").addEventListener("change", function (e) {
      state.review = e.target.checked; markPresetActive(""); render();
    });
    $("togNew").addEventListener("change", function (e) {
      state.newOnly = e.target.checked; markPresetActive(""); render();
    });
    $("togLast30").addEventListener("change", function (e) {
      state.last30Only = e.target.checked; markPresetActive(""); render();
    });
    $("togTaxDefault").addEventListener("change", function (e) {
      state.taxDefaultOnly = e.target.checked; markPresetActive(""); render();
    });
    $("togHideTinyBal").addEventListener("change", function (e) {
      state.hideTinyBal = e.target.checked; markPresetActive(""); render();
    });
    $("yearsDelinquent").addEventListener("change", function (e) {
      state.yearsDelinquent = e.target.value; markPresetActive(""); render();
    });
    $("balMin").addEventListener("input", function (e) {
      state.balMin = e.target.value === "" ? null : Number(e.target.value);
      markPresetActive(""); render();
    });
    $("togAddrOnly").addEventListener("change", function (e) {
      state.addrOnly = e.target.checked; markPresetActive(""); render();
    });
    $("sortMode").addEventListener("change", function (e) {
      state.sort = e.target.value; render();
    });
    $("resetBtn").addEventListener("click", function () { applyPreset("all"); });
    $("exportFiltered").addEventListener("click", function () {
      exportCsv(filtered, "duval_fl_leads_filtered.csv");
    });
    $("exportMarked").addEventListener("click", function () {
      var rows = records.filter(function (r) { return marked[r.lead_id]; });
      if (!rows.length) { alert("No leads marked for review yet."); return; }
      exportCsv(rows, "duval_fl_leads_marked.csv");
    });
  }

  function applyPreset(id) {
    // reset everything to defaults first
    state.search = ""; $("search").value = "";
    state.saleWindow = "any"; $("saleWindow").value = "any";
    state.valMin = null; state.valMax = null;
    $("valMin").value = ""; $("valMax").value = "";
    state.absentee = false; $("togAbsentee").checked = false;
    state.oos = false; $("togOos").checked = false;
    state.review = false; $("togReview").checked = false;
    state.newOnly = false; $("togNew").checked = false;
    state.last30Only = false; $("togLast30").checked = false;
    state.taxDefaultOnly = false; $("togTaxDefault").checked = false;
    state.hideTinyBal = false; $("togHideTinyBal").checked = false;
    state.yearsDelinquent = "any"; $("yearsDelinquent").value = "any";
    state.balMin = null; $("balMin").value = "";
    state.addrOnly = false; $("togAddrOnly").checked = false;
    state.multiOnly = false;
    // Standing rule #5 — reset = empty selection (no filter), not all-checked.
    setAllChecks("signalFilter", "sig", state.signals, false);
    setAllChecks("ownerFilter", "own", state.owners, false);

    if (id === "addrResolved") {
      state.addrOnly = true; $("togAddrOnly").checked = true;
    } else if (id === "new") {
      state.newOnly = true; $("togNew").checked = true;
      state.sort = "recent"; $("sortMode").value = "recent";
    } else if (id === "last30") {
      state.last30Only = true; $("togLast30").checked = true;
      state.sort = "recent"; $("sortMode").value = "recent";
    } else if (id === "fcl21") {
      state.saleWindow = "21"; $("saleWindow").value = "21";
      onlyChecks("signalFilter", "sig", state.signals, ["foreclosure_notice"]);
    } else if (id === "estates") {
      onlyChecks("ownerFilter", "own", state.owners, ["ESTATE"]);
    } else if (id === "oos") {
      state.absentee = true; $("togAbsentee").checked = true;
      state.oos = true; $("togOos").checked = true;
    } else if (id === "multi") {
      state.multiOnly = true;
    } else if (id === "tax") {
      state.taxDefaultOnly = true; $("togTaxDefault").checked = true;
      state.hideTinyBal = true;    $("togHideTinyBal").checked = true;
      state.sort = "value"; $("sortMode").value = "value";
    } else if (id === "tax2yr") {
      state.taxDefaultOnly = true; $("togTaxDefault").checked = true;
      state.yearsDelinquent = "2"; $("yearsDelinquent").value = "2";
      state.sort = "value"; $("sortMode").value = "value";
    } else if (id === "tax5yr") {
      state.taxDefaultOnly = true; $("togTaxDefault").checked = true;
      state.yearsDelinquent = "5"; $("yearsDelinquent").value = "5";
      state.sort = "value"; $("sortMode").value = "value";
    }
    markPresetActive(id);
    render();
  }
  function setAllChecks(boxId, attr, store, on) {
    $(boxId).querySelectorAll("input[type=checkbox]").forEach(function (c) {
      c.checked = on; store[c.dataset[attr]] = on;
    });
  }
  function onlyChecks(boxId, attr, store, keep) {
    $(boxId).querySelectorAll("input[type=checkbox]").forEach(function (c) {
      var on = keep.indexOf(c.dataset[attr]) >= 0;
      c.checked = on; store[c.dataset[attr]] = on;
    });
  }

  // ---------- filtering + sorting ----------
  function applyFilters() {
    // Standing rule #5 — empty selection = no filter (show everything).
    // Click-to-select / stack: any selected type is included; nothing
    // selected means the filter is inactive.
    var anySig = Object.keys(state.signals).some(
      function (k) { return state.signals[k]; });
    var anyOwn = Object.keys(state.owners).some(
      function (k) { return state.owners[k]; });
    var win = state.saleWindow === "any" ? null : Number(state.saleWindow);

    return records.filter(function (r) {
      if (skipped[r.lead_id]) return false;
      if (state.review && !r._review) return false;
      if (anySig) {
        var hit = (r.signal_types || []).some(function (t) {
          return state.signals[t];
        });
        if (!hit) return false;
      }
      if (anyOwn && !state.owners[r.owner_type || "UNKNOWN"]) return false;
      if (state.absentee && !r.absentee_owner_flag) return false;
      if (state.oos && !r.out_of_state_owner_flag) return false;
      if (state.newOnly && !r._isNew) return false;
      if (state.last30Only && !r._within30d) return false;
      if (state.addrOnly && !r.has_street_address) return false;
      if (state.taxDefaultOnly && !r._taxDefault) return false;
      if (state.yearsDelinquent !== "any") {
        var yMin = Number(state.yearsDelinquent);
        if (!r._taxDefault || (r._yearsDelinq || 0) < yMin) return false;
      }
      if (state.balMin != null && (r._taxBalance || 0) < state.balMin) return false;
      // Default-hide low-priority: <$100 balance AND 1-year only AND no
      // other distress signal stacked. Keeps the board operator-grade.
      if (state.hideTinyBal && r._taxDefault &&
          (r._taxBalance || 0) < 100 && (r._yearsDelinq || 0) <= 1 &&
          (r.signal_count || 0) <= 1) return false;
      if (state.multiOnly && (r.signal_count || 0) < 2) return false;
      if (win != null) {
        if (!r._isFcl || r._days == null || r._days < 0 || r._days > win)
          return false;
      }
      if (state.valMin != null && r._assessed < state.valMin) return false;
      if (state.valMax != null &&
        (r._assessed > state.valMax || r._assessed === 0)) return false;
      if (state.search && r._blob.indexOf(state.search) < 0) return false;
      return true;
    });
  }
  function sortRows(rows) {
    var c = rows.slice();
    var by = state.sort;
    // Standing rule #7-addendum — a lead with a real street address is
    // operator-actionable; one with only city/state isn't. The default
    // sort puts address-resolved leads above no-street leads, then
    // applies the chosen secondary ordering within each bucket.
    function addrRank(r) { return r.has_street_address ? 0 : 1; }
    c.sort(function (a, b) {
      var ar = addrRank(a), br = addrRank(b);
      if (ar !== br) return ar - br;
      if (by === "sale") {
        var av = a._saleDate ? a._saleDate.getTime() : 8e15;
        var bv = b._saleDate ? b._saleDate.getTime() : 8e15;
        return av - bv;
      }
      if (by === "value") return b._assessed - a._assessed;
      if (by === "recent") {
        var af = a._filed ? a._filed.getTime() : 0;
        var bf = b._filed ? b._filed.getTime() : 0;
        return bf - af;
      }
      if (by === "signals")
        return (b.signal_count || 0) - (a.signal_count || 0);
      if (a._tier !== b._tier) return a._tier - b._tier;
      if (a._tier <= 2) {
        var as = a._saleDate ? a._saleDate.getTime() : 8e15;
        var bs = b._saleDate ? b._saleDate.getTime() : 8e15;
        return as - bs;
      }
      if ((b.signal_count || 0) !== (a.signal_count || 0))
        return (b.signal_count || 0) - (a.signal_count || 0);
      return b._assessed - a._assessed;
    });
    return c;
  }

  // ---------- rendering (UI-7 incremental window) ----------
  function setupObserver() {
    sentinel = document.createElement("div");
    sentinel.className = "sentinel";
    io = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) renderMore();
    }, { root: $("leadList"), rootMargin: "300px" });
  }
  function render() {
    filtered = sortRows(applyFilters());
    state.shown = 0;
    var list = $("leadList");
    io.unobserve(sentinel);
    list.innerHTML = "";               // detaches sentinel — JS ref survives
    $("rowCount").textContent = filtered.length.toLocaleString() +
      " of " + records.length.toLocaleString() + " leads";
    $("markedCount").textContent = Object.keys(marked).length;
    updateFilterSummary();

    var empty = $("emptyMsg");
    if (!filtered.length) {
      empty.hidden = false;
      empty.innerHTML = "<b>No leads match the current filters.</b>" +
        "Try widening the foreclosure sale window, clearing the assessed-" +
        "value range, or re-checking signal/owner types — or hit " +
        "<em>Show all</em>.";
      return;
    }
    empty.hidden = true;
    renderMore();
  }
  function renderMore() {
    var list = $("leadList");
    var end = Math.min(state.shown + PAGE, filtered.length);
    var frag = document.createDocumentFragment();
    for (var i = state.shown; i < end; i++) frag.appendChild(rowEl(filtered[i]));
    list.appendChild(frag);
    list.appendChild(sentinel);        // keep sentinel last
    state.shown = end;
    if (state.shown < filtered.length) io.observe(sentinel);
    else io.unobserve(sentinel);
  }

  function chipHtml(r) {
    return (r.signals || []).map(function (s) {
      var n = s.count || 1;
      var cb = n > 1 ? '<span class="cb">' + n + "</span>" : "";
      var cls = "chip", label = esc(s.signal_label || s.signal_type);
      if (s.signal_type === "foreclosure_notice") {
        cls += " fcl";
        var d = r._days;
        if (d != null && d >= 0 && d <= 21) cls += " soon";
        if (s.sale_date) {
          label = "Foreclosure — Sale " + esc(s.sale_date);
          if (d != null) label += d < 0 ? " (past)"
            : d === 0 ? " (today)" : " (in " + d + "d)";
        }
      } else if (s.signal_type === "estate_titled_property" ||
        s.signal_type === "trust_titled_property") {
        cls += " estate";
      } else if (s.signal_type === "state_tax_lien" ||
        s.signal_type === "federal_tax_lien") {
        cls += " tax";
      }
      return '<span class="' + cls + '">' + label + cb + "</span>";
    }).join("");
  }
  function rowEl(r) {
    var el = document.createElement("div");
    el.className = "lead u-" + r._tier +
      (r._review ? " review" : "") + (marked[r.lead_id] ? " marked" : "");
    el.dataset.id = r.lead_id;

    var addr;
    if (r.property_full_address)
      addr = '<div class="addr">' + esc(r.property_full_address) + "</div>";
    else if (r.legal_description)
      addr = '<div class="addr legal">Legal: ' +
        esc(r.legal_description) + "</div>";
    else
      addr = '<div class="addr none">No property address — skip-trace ' +
        'from owner + instrument</div>';

    var mail = (r.mailing_full_address &&
      r.mailing_full_address !== r.property_full_address)
      ? '<div class="mail">Mailing: ' + esc(r.mailing_full_address) +
        "</div>" : "";
    var filer = r._review && r.filer_entity
      ? '<div class="filer-note">Filed by: ' + esc(r.filer_entity) +
        " — debtor not identified in record</div>" : "";

    var ownCls = "owner" +
      (/unidentified party/i.test(r.owner_name || "") ? " placeholder" : "");
    var badges = badgeHtml(r);
    var av = r._assessed
      ? '<div class="assessed">' + money(r.assessed_value) +
        '<div class="ac">assessed</div></div>' : "";

    el.innerHTML =
      '<div class="lead-main">' +
        '<div class="lead-id">' +
          '<div class="' + ownCls + '">' + esc(r.owner_name || "—") +
            '<span class="otype">' + esc(r.owner_type || "UNKNOWN") +
            "</span></div>" +
          addr + mail + filer +
          '<div class="chips">' + chipHtml(r) + "</div>" +
        "</div>" +
        '<div class="lead-right">' + av +
          '<div class="badges">' + badges + "</div>" +
        "</div>" +
      "</div>" +
      '<div class="detail"></div>';

    el.addEventListener("click", function (ev) {
      if (ev.target.closest(".detail-actions")) return;
      toggleDetail(el, r);
    });
    return el;
  }
  function badgeHtml(r) {
    var b = [];
    if (r._isNew)
      b.push('<span class="badge new">NEW</span>');
    if (r._taxDefault && (r._taxBalance || 0) > 0) {
      var y = r._yearsDelinq || 1;
      var ylabel = y >= 5 ? "5+ yr" : (y + (y === 1 ? " yr" : " yr"));
      b.push('<span class="badge tax">$' +
        Math.round(r._taxBalance).toLocaleString("en-US") +
        " · " + esc(ylabel) + " delinquent</span>");
      if (r.parcel_deed_status && r.parcel_deed_status !== "Paid Off")
        b.push('<span class="badge tax">' + esc(r.parcel_deed_status) + "</span>");
    }
    if (r._review)
      b.push('<span class="badge warn">REVIEW REQUIRED</span>');
    if (r.absentee_owner_flag)
      b.push('<span class="badge warn">Absentee</span>');
    if (r.out_of_state_owner_flag)
      b.push('<span class="badge warn">Out-of-state</span>');
    if (r.homestead === "HOMESTEAD")
      b.push('<span class="badge good">Homestead</span>');
    if (r.epcad_enrichment_status === "ENRICHED" ||
      r.parcel_resolution_status === "RESOLVED" && r.parcel_id)
      b.push('<span class="badge">JaxGIS enriched</span>');
    return b.join("");
  }

  // ---------- detail panel (UI-4) ----------
  function toggleDetail(el, r) {
    if (el.classList.contains("open")) {
      el.classList.remove("open"); return;
    }
    var d = el.querySelector(".detail");
    if (!d.dataset.built) { d.innerHTML = detailHtml(r); d.dataset.built = "1"; }
    el.classList.add("open");
    wireDetail(el, d, r);
  }
  function detailHtml(r) {
    var fs = r._fcl;
    var rows = [];
    function add(k, v) { if (v) rows.push([k, v]); }
    add("Resolution", r.parcel_resolution_status +
      (r.epcad_enrichment_status ? " · JaxGIS " + r.epcad_enrichment_status : ""));
    if (r.filer_entity) add("Filer entity", esc(r.filer_entity));
    add("Parcel ID", r.parcel_id);
    add("Legal description", esc(r.legal_description));
    add("Mailing address", esc(r.mailing_full_address));
    if (r.assessed_value != null || r.appraised_value != null)
      add("Assessed / Appraised",
        money(r.assessed_value) + " / " + money(r.appraised_value) +
        (r.homestead ? " · " + r.homestead.replace("_", " ").toLowerCase()
          : ""));
    if (fs) {
      add("Foreclosure sale date", esc(fs.sale_date));
      add("DoT document #", esc(fs.dot_document_number));
      add("Lender / beneficiary", esc(fs.lender_beneficiary));
      var legal = ["subdivision", "lot", "block", "unit"].map(function (k) {
        return fs[k] ? k + " " + fs[k] : "";
      }).filter(Boolean).join(", ");
      add("Plat", esc(legal));
    }
    if (r._taxDefault) {
      add("Tax delinquency", money(r.tax_balance_due) + " — " +
        (r.years_delinquent_floor || 1) +
        ((r.years_delinquent_floor || 1) === 1 ? " yr" : "+ yr") +
        (r.parcel_deed_status
          ? " · " + esc(r.parcel_deed_status) : "") +
        (r.tax_bankrupt ? " · BANKRUPTCY ON FILE" : "") +
        (r.tax_litigation ? " · LITIGATION ON FILE" : ""));
    }
    r.signals.forEach(function (s) {
      var ins = (s.instrument_numbers || []).join(", ");
      if (ins) add(s.signal_label + " instr#", esc(ins));
    });
    var urls = (r.source_urls || []).map(function (u) {
      return '<a href="' + esc(u) + '" target="_blank" rel="noopener">' +
        esc(u) + "</a>";
    }).join("<br>");
    if (urls) rows.push(["Source records", urls]);

    var grid = '<dl class="detail-grid">' + rows.map(function (kv) {
      return "<dt>" + kv[0] + "</dt><dd>" + kv[1] + "</dd>";
    }).join("") + "</dl>";
    var mk = marked[r.lead_id];
    return grid +
      '<div class="detail-actions">' +
        '<button class="btn btn-mark act-mark">' +
          (mk ? "✓ Marked for review" : "Mark for review") + "</button>" +
        '<button class="btn act-skip">Skip (hide)</button>' +
        '<button class="btn act-export">Export this lead</button>' +
      "</div>";
  }
  function wireDetail(el, d, r) {
    var mb = d.querySelector(".act-mark");
    mb.onclick = function () {
      if (marked[r.lead_id]) delete marked[r.lead_id];
      else marked[r.lead_id] = true;
      saveMarked();
      el.classList.toggle("marked", !!marked[r.lead_id]);
      mb.textContent = marked[r.lead_id]
        ? "✓ Marked for review" : "Mark for review";
      $("markedCount").textContent = Object.keys(marked).length;
    };
    d.querySelector(".act-skip").onclick = function () {
      skipped[r.lead_id] = true; render();
    };
    d.querySelector(".act-export").onclick = function () {
      exportCsv([r], "duval_fl_lead_" + (r.lead_id || "row") + ".csv");
    };
  }

  // ---------- filter summary (UI-5) ----------
  function updateFilterSummary() {
    var parts = [];
    var preset = PRESETS.filter(function (p) {
      return p.id === state.preset && p.id !== "all";
    })[0];
    if (preset) parts.push("<b>" + esc(preset.label) + "</b>");
    if (state.search) parts.push('search "' + esc(state.search) + '"');
    if (state.saleWindow !== "any")
      parts.push("sale &le; " + state.saleWindow + " days");
    var sigOn = Object.keys(state.signals).filter(function (k) {
      return state.signals[k];
    });
    if (sigOn.length)
      parts.push(sigOn.length === 1 ? esc(sigOn[0])
        : sigOn.length + " signal types");
    var ownOn = Object.keys(state.owners).filter(function (k) {
      return state.owners[k];
    });
    if (ownOn.length)
      parts.push("owner " + ownOn.join("/"));
    if (state.valMin != null) parts.push("min " + money(state.valMin));
    if (state.valMax != null) parts.push("max " + money(state.valMax));
    if (state.absentee) parts.push("absentee");
    if (state.oos) parts.push("out-of-state");
    if (state.review) parts.push("review-required");
    if (state.newOnly) parts.push("NEW today");
    if (state.last30Only) parts.push("filed last 30d");
    if (state.taxDefaultOnly) parts.push("tax-default");
    if (state.yearsDelinquent !== "any")
      parts.push(state.yearsDelinquent + "+ yr delinquent");
    if (state.balMin != null) parts.push("balance &ge; " + money(state.balMin));
    if (state.hideTinyBal) parts.push("low-priority hidden");
    if (state.addrOnly) parts.push("address-resolved only");
    if (state.multiOnly) parts.push("multi-signal");
    $("filterSummary").innerHTML = parts.length
      ? "Showing: " + parts.join(" · ")
      : "Showing: <b>all leads</b> — sorted by urgency";
  }

  // ---------- CSV (UI-8) ----------
  var CSV_COLS = ["lead_id", "owner_name", "owner_type",
    "parcel_resolution_status", "epcad_enrichment_status", "filer_entity",
    "property_full_address", "property_city", "property_zip",
    "mailing_full_address", "mailing_state", "assessed_value",
    "appraised_value", "homestead", "absentee_owner_flag",
    "out_of_state_owner_flag", "signal_count", "primary_signal",
    "latest_event_date", "legal_description", "parcel_id"];
  function exportCsv(rows, fname) {
    var head = CSV_COLS.concat(["sale_date", "signal_types", "source_urls"]);
    var lines = [head.join(",")];
    rows.forEach(function (r) {
      var cells = CSV_COLS.map(function (c) { return q(r[c]); });
      cells.push(q(r._fcl ? r._fcl.sale_date : ""));
      cells.push(q((r.signal_types || []).join("; ")));
      cells.push(q((r.source_urls || []).join(" ")));
      lines.push(cells.join(","));
    });
    var blob = new Blob([lines.join("\n")], { type: "text/csv" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = fname;
    document.body.appendChild(a); a.click(); a.remove();
  }
  function q(v) {
    if (v == null) v = "";
    return '"' + String(v).replace(/"/g, '""') + '"';
  }

  // ---------- start ----------
  function start() {
    if (DATA) { boot(DATA); return; }
    fetch("data.json").then(function (r) { return r.json(); }).then(boot)
      .catch(function (e) {
        var b = $("banner"); b.hidden = false;
        b.textContent = "Could not load data (" + e + ").";
        document.documentElement.setAttribute("data-ready", "1");
      });
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", start);
  else start();
})();
