/* FoodShare frontend: plain JS single-page app, served by FastAPI at /app */
(function () {
  "use strict";

  var CFG = window.FOODSHARE_CONFIG || {};
  var API = (CFG.apiBase || location.origin).replace(/\/$/, "");
  var CENTER = CFG.defaultCenter || { lat: 17.385, lng: 78.4867 };

  var S = { token: null, user: null, view: null, authTab: "login", map: null, markers: [], picker: null };

  // ---------- helpers ----------
  function store(k, v) {
    try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { /* ignore */ }
    return null;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function $(sel, root) { return (root || document).querySelector(sel); }
  function app() { return document.getElementById("app"); }

  // API datetimes are naive UTC (no Z)
  function parseUTC(s) {
    if (!s) return null;
    return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(s) ? s : s + "Z");
  }
  function fmt(s) {
    var d = parseUTC(s);
    return d ? d.toLocaleString([], { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "-";
  }
  function timeLeft(s) {
    var d = parseUTC(s);
    if (!d) return "";
    var m = Math.round((d - Date.now()) / 60000);
    if (m <= 0) return "expired";
    if (m < 60) return m + " min left";
    if (m < 2880) return Math.round(m / 60) + " h left";
    return Math.round(m / 1440) + " d left";
  }
  function toast(msg, isErr) {
    var box = document.getElementById("toasts");
    var t = document.createElement("div");
    t.className = "toast" + (isErr ? " error" : "");
    t.textContent = msg;
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, 4200);
  }

  function errText(data, status) {
    var d = data && data.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map(function (x) { return (x.loc ? x.loc.slice(1).join(".") + ": " : "") + x.msg; }).join("; ");
    return "Request failed (" + status + ")";
  }

  function api(path, o) {
    o = o || {};
    var headers = {};
    var body;
    if (S.token && o.auth !== false) headers.Authorization = "Bearer " + S.token;
    if (o.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(o.json); }
    else if (o.urlencoded) { headers["Content-Type"] = "application/x-www-form-urlencoded"; body = new URLSearchParams(o.urlencoded).toString(); }
    else if (o.form) { body = o.form; }
    return fetch(API + path, { method: o.method || "GET", headers: headers, body: body }).then(function (r) {
      if (o.blob && r.ok) return r.blob();
      return r.text().then(function (txt) {
        var data = null;
        try { data = txt ? JSON.parse(txt) : null; } catch (e) { /* not json */ }
        if (r.status === 401 && o.auth !== false && S.token) { signOut(); throw new Error("Session expired. Sign in again."); }
        if (!r.ok) { var err = new Error(errText(data, r.status)); err.status = r.status; throw err; }
        return data;
      });
    });
  }
  function fail(e) { toast(e.message || "Something went wrong", true); }

  // ---------- Google Maps ----------
  var mapsPromise = null;
  function loadMaps() {
    if (!CFG.googleMapsKey) return Promise.reject(new Error("no key"));
    if (window.google && window.google.maps) return Promise.resolve();
    if (mapsPromise) return mapsPromise;
    mapsPromise = new Promise(function (res, rej) {
      window.__fsMapsReady = function () { res(); };
      var s = document.createElement("script");
      s.src = "https://maps.googleapis.com/maps/api/js?key=" + encodeURIComponent(CFG.googleMapsKey) + "&callback=__fsMapsReady";
      s.onerror = function () { mapsPromise = null; rej(new Error("Maps failed to load")); };
      document.head.appendChild(s);
      setTimeout(function () { if (!(window.google && window.google.maps)) { mapsPromise = null; rej(new Error("Maps timed out")); } }, 12000);
    });
    window.gm_authFailure = function () { toast("Google Maps key was rejected. Check key restrictions and billing.", true); };
    return mapsPromise;
  }
  function mapOff(el, text) {
    el.innerHTML = '<div class="map-off">' + esc(text) + "</div>";
  }
  function dot(color) {
    return { path: window.google.maps.SymbolPath.CIRCLE, scale: 9, fillColor: color, fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2 };
  }

  // items: [{lat,lng,title,html,color}]
  function renderMap(el, items) {
    if (!el) return;
    loadMaps().then(function () {
      var m = new google.maps.Map(el, { center: CENTER, zoom: 11, mapTypeControl: false, streetViewControl: false });
      var info = new google.maps.InfoWindow();
      var b = new google.maps.LatLngBounds();
      items.forEach(function (it) {
        var mk = new google.maps.Marker({ position: { lat: it.lat, lng: it.lng }, map: m, title: it.title, icon: dot(it.color || "#1f5c43") });
        mk.addListener("click", function () { info.setContent(it.html); info.open(m, mk); });
        b.extend(mk.getPosition());
      });
      if (items.length > 1) m.fitBounds(b, 50);
      else if (items.length === 1) { m.setCenter(b.getCenter()); m.setZoom(14); }
    }).catch(function () {
      mapOff(el, CFG.googleMapsKey ? "Map could not load." : "Map is off. Add a Google Maps key in config.js to see locations here.");
    });
  }

  // Location picker. Returns {get(): {lat,lng,address}|null}
  function initPicker(root, init) {
    var st = { lat: init && init.lat != null ? init.lat : null, lng: init && init.lng != null ? init.lng : null };
    var latI = $('[name="lat"]', root), lngI = $('[name="lng"]', root), addrI = $('[name="address"]', root);
    var mapEl = $(".pmap", root);
    var map, marker, geocoder;
    function setPos(lat, lng, pan) {
      st.lat = lat; st.lng = lng;
      latI.value = Number(lat).toFixed(6); lngI.value = Number(lng).toFixed(6);
      if (marker) { marker.setPosition({ lat: lat, lng: lng }); marker.setMap(map); }
      if (map && pan) { map.panTo({ lat: lat, lng: lng }); }
    }
    function reverse() {
      if (!geocoder || st.lat == null) return;
      geocoder.geocode({ location: { lat: st.lat, lng: st.lng } }, function (r, status) {
        if (status === "OK" && r[0] && !addrI.value.trim()) addrI.value = r[0].formatted_address;
      });
    }
    if (st.lat != null) { latI.value = st.lat; lngI.value = st.lng; }
    function manual() {
      var a = parseFloat(latI.value), b = parseFloat(lngI.value);
      if (isFinite(a) && isFinite(b)) setPos(a, b, true);
    }
    latI.addEventListener("change", manual);
    lngI.addEventListener("change", manual);
    $(".use-loc", root).addEventListener("click", function () {
      if (!navigator.geolocation) return toast("Location not supported in this browser", true);
      navigator.geolocation.getCurrentPosition(function (p) {
        setPos(p.coords.latitude, p.coords.longitude, true); if (map) map.setZoom(15); reverse();
      }, function () { toast("Could not get your location. Allow it, or type lat/lng.", true); });
    });
    var find = $(".find-loc", root);
    loadMaps().then(function () {
      geocoder = new google.maps.Geocoder();
      var c = st.lat != null ? { lat: st.lat, lng: st.lng } : CENTER;
      map = new google.maps.Map(mapEl, { center: c, zoom: st.lat != null ? 15 : 11, mapTypeControl: false, streetViewControl: false });
      marker = new google.maps.Marker({ position: c, map: st.lat != null ? map : null, draggable: true, icon: dot("#d9533f") });
      map.addListener("click", function (e) { setPos(e.latLng.lat(), e.latLng.lng(), false); reverse(); });
      marker.addListener("dragend", function (e) { setPos(e.latLng.lat(), e.latLng.lng(), false); reverse(); });
      find.addEventListener("click", function () {
        var q = addrI.value.trim();
        if (!q) return toast("Type an address first", true);
        geocoder.geocode({ address: q }, function (r, status) {
          if (status === "OK" && r[0]) { var l = r[0].geometry.location; setPos(l.lat(), l.lng(), true); map.setZoom(15); }
          else toast("Address not found (" + status + ")", true);
        });
      });
    }).catch(function () {
      mapOff(mapEl, "Map is off. Use 'Use my location' or type latitude and longitude.");
      find.disabled = true;
    });
    return {
      get: function () {
        var a = parseFloat(latI.value), b = parseFloat(lngI.value);
        if (!isFinite(a) || !isFinite(b)) return null;
        return { lat: a, lng: b, address: addrI.value.trim() };
      }
    };
  }
  function pickerHTML(addr, label) {
    return '<div class="field"><label>' + esc(label || "Address") + '</label>' +
      '<div class="row gap"><input name="address" class="grow" required minlength="3" value="' + esc(addr || "") + '" placeholder="Street, area, city">' +
      '<button type="button" class="btn ghost small find-loc">Find on map</button>' +
      '<button type="button" class="btn ghost small use-loc">Use my location</button></div></div>' +
      '<div class="pmap"></div>' +
      '<div class="grid2"><div class="field"><label>Latitude</label><input name="lat" inputmode="decimal" required></div>' +
      '<div class="field"><label>Longitude</label><input name="lng" inputmode="decimal" required></div></div>' +
      '<p class="hint">Click the map or drag the pin to set the exact spot.</p>';
  }

  // ---------- small UI pieces ----------
  function ring(conf, label) {
    var p = Math.max(0, Math.min(1, conf || 0)), r = 18, c = 2 * Math.PI * r;
    var col = label === "rotten" ? "#d9533f" : "#1f5c43";
    return '<svg class="ring" width="48" height="48" viewBox="0 0 48 48" role="img" aria-label="confidence ' + Math.round(p * 100) + ' percent">' +
      '<circle class="ring-bg" cx="24" cy="24" r="' + r + '" fill="none" stroke="#dfe7e1" stroke-width="5"/>' +
      '<circle class="ring-fg" cx="24" cy="24" r="' + r + '" fill="none" stroke="' + col + '" stroke-width="5" stroke-linecap="round" stroke-dasharray="' + (c * p).toFixed(1) + " " + c.toFixed(1) + '" transform="rotate(-90 24 24)"/>' +
      '<text class="ring-t" x="24" y="28" text-anchor="middle" font-size="12" fill="currentColor">' + Math.round(p * 100) + "</text></svg>";
  }
  function chip(text, kind) { return '<span class="chip' + (kind ? " " + kind : "") + '">' + esc(String(text).replace(/_/g, " ")) + "</span>"; }
  function vChip(v) {
    var k = { auto_approved: "ok", admin_approved: "ok", rejected: "bad", admin_rejected: "bad", manual_review: "warn", pending: "warn" }[v];
    return chip(v, k);
  }
  function sChip(s) {
    var k = { delivered: "ok", accepted: "ok", picked_up: "ok", expired: "bad", rejected: "bad" }[s];
    return chip(s, k);
  }
  function empty(t) { return '<div class="empty">' + esc(t) + "</div>"; }
  function loading() { return '<div class="loading">Loading...</div>'; }

  function authImg(id, imgEl) {
    api("/donations/" + id + "/image", { blob: true }).then(function (b) { imgEl.src = URL.createObjectURL(b); }).catch(function () { imgEl.closest(".thumb") && imgEl.closest(".thumb").remove(); });
  }
  function hydrateImages(root) {
    Array.prototype.forEach.call(root.querySelectorAll("img[data-img]"), function (im) { authImg(im.getAttribute("data-img"), im); });
  }

  // ---------- auth ----------
  function signOut() {
    S.token = null; S.user = null; store("fs_token", null);
    renderAuth();
  }

  function renderAuth() {
    var reg = S.authTab === "register";
    app().innerHTML =
      '<div class="auth"><aside class="auth-side"><div class="wordmark">FoodShare</div>' +
      "<h1>Good food should reach a plate, not a bin.</h1>" +
      '<ol class="flow"><li><strong>Donate.</strong> Post surplus food with a photo.</li>' +
      "<li><strong>Verify.</strong> AI checks fruit freshness, admins review the rest.</li>" +
      "<li><strong>Match.</strong> The nearest suitable NGO is suggested.</li>" +
      "<li><strong>Deliver.</strong> A volunteer picks it up and drops it off.</li></ol></aside>" +
      '<div class="auth-main"><div class="auth-card">' +
      '<div class="tabs2" role="tablist"><button role="tab" data-action="authtab" data-v="login" aria-selected="' + !reg + '">Sign in</button>' +
      '<button role="tab" data-action="authtab" data-v="register" aria-selected="' + reg + '">Create account</button></div>' +
      '<form class="form" id="authform">' +
      (reg ? '<div class="field"><label>Full name</label><input name="name" required minlength="2"></div>' : "") +
      '<div class="field"><label>Email</label><input name="email" type="email" required autocomplete="email"></div>' +
      '<div class="field"><label>Password</label><input name="password" type="password" required minlength="6" maxlength="64" autocomplete="' + (reg ? "new-password" : "current-password") + '"></div>' +
      (reg ? '<div class="field"><label>I am a</label><select name="role"><option value="donor">Donor (restaurant, home, event)</option><option value="ngo">NGO</option><option value="volunteer">Volunteer</option></select></div>' +
        '<div class="field"><label>Phone (optional)</label><input name="phone" inputmode="tel"></div>' : "") +
      '<button class="btn" type="submit">' + (reg ? "Create account" : "Sign in") + "</button></form></div></div></div>";
    $("#authform").addEventListener("submit", function (e) {
      e.preventDefault();
      var f = e.target, btn = $("button[type=submit]", f); btn.disabled = true;
      var email = f.email.value.trim(), pw = f.password.value;
      var p = reg
        ? api("/auth/register", { method: "POST", auth: false, json: { name: f.name.value.trim(), email: email, password: pw, role: f.role.value, phone: f.phone.value.trim() || null } })
        : Promise.resolve();
      p.then(function () { return api("/auth/login", { method: "POST", auth: false, urlencoded: { username: email, password: pw } }); })
        .then(function (t) { S.token = t.access_token; store("fs_token", S.token); return boot(); })
        .catch(function (err) { fail(err); btn.disabled = false; });
    });
  }

  // ---------- shell ----------
  var TABS = {
    donor: [["donate", "Donate"], ["mine", "My donations"]],
    ngo: [["available", "Available food"], ["ngopickups", "My pickups"], ["org", "Organisation"]],
    volunteer: [["open", "Open pickups"], ["vpickups", "My pickups"]],
    admin: [["overview", "Overview"], ["review", "Review queue"], ["all", "All donations"]]
  };
  var VIEWS = {};

  function shell() {
    var tabs = TABS[S.user.role] || [];
    if (!S.view || !tabs.some(function (t) { return t[0] === S.view; })) S.view = tabs[0] && tabs[0][0];
    app().innerHTML =
      '<header class="top"><div class="wordmark">FoodShare</div><nav>' +
      tabs.map(function (t) { return '<button data-action="nav" data-v="' + t[0] + '"' + (t[0] === S.view ? ' aria-current="page"' : "") + ">" + esc(t[1]) + "</button>"; }).join("") +
      '</nav><div class="who"><span>' + esc(S.user.name) + ' <span class="role">' + esc(S.user.role) + '</span></span><button data-action="signout">Sign out</button></div></header>' +
      '<main id="view">' + loading() + "</main>";
    var v = VIEWS[S.view];
    if (v) v($("#view"));
  }
  function go(v) { S.view = v; shell(); }

  function boot() {
    return api("/auth/me").then(function (u) { S.user = u; shell(); }).catch(function (e) {
      if (S.token) { S.token = null; store("fs_token", null); }
      renderAuth(); if (e && e.message) fail(e);
    });
  }

  // ---------- donor ----------
  VIEWS.donate = function (el) {
    var soon = new Date(Date.now() + 6 * 3600 * 1000);
    var local = new Date(soon - soon.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    el.innerHTML = '<div class="narrow"><h2>Donate food</h2><p class="lede">Fill in the details, then add a photo so we can check freshness.</p>' +
      '<form class="form" id="donform">' +
      '<div class="grid2"><div class="field"><label>Food name</label><input name="food_name" required minlength="2" maxlength="120" placeholder="e.g. Bananas"></div>' +
      '<div class="field"><label>Type</label><select name="food_type"><option value="fruit">Fruit</option><option value="vegetable">Vegetable</option><option value="bread">Bread</option><option value="cooked">Cooked meal</option><option value="packaged">Packaged</option></select></div></div>' +
      '<div class="grid2"><div class="field"><label>Quantity (servings or items)</label><input name="quantity" type="number" min="1" max="10000" value="10" required></div>' +
      '<div class="field"><label>Use before</label><input name="expiry_at" type="datetime-local" value="' + local + '" required></div></div>' +
      pickerHTML("", "Pickup address") +
      '<button class="btn" type="submit">Post donation</button></form></div>';
    var picker = initPicker(el, null);
    $("#donform").addEventListener("submit", function (e) {
      e.preventDefault();
      var f = e.target, pos = picker.get();
      if (!pos) return toast("Set the pickup location first", true);
      var btn = $("button[type=submit]", f); btn.disabled = true;
      api("/donations", {
        method: "POST", json: {
          food_name: f.food_name.value.trim(), food_type: f.food_type.value, quantity: parseInt(f.quantity.value, 10),
          expiry_at: new Date(f.expiry_at.value).toISOString().replace(/\.\d+Z$/, "").replace("Z", ""),
          pickup_address: pos.address || f.address.value.trim(), lat: pos.lat, lng: pos.lng
        }
      }).then(function (d) { toast("Donation posted. Add a photo to verify it."); S.focus = d.id; go("mine"); })
        .catch(function (err) { fail(err); btn.disabled = false; });
    });
  };

  function donationRow(d, extra) {
    var ai = d.freshness_label ? '<div class="mono">' + esc(d.freshness_label) + " " + Math.round((d.freshness_confidence || 0) * 100) + "%</div>" : "";
    return '<div class="row-item" data-id="' + d.id + '">' +
      (d.freshness_label ? ring(d.freshness_confidence, d.freshness_label) : "") +
      '<div class="grow"><strong>' + esc(d.food_name) + "</strong> " + chip(d.food_type) +
      '<div class="meta">' + esc(d.quantity) + " units · " + esc(d.pickup_address) + " · " + esc(timeLeft(d.expiry_at)) + " (" + esc(fmt(d.expiry_at)) + ")</div>" +
      '<div class="chips">' + vChip(d.verification_status) + " " + sChip(d.status) + "</div>" + ai + "</div>" +
      '<div class="actions">' + (extra || "") + "</div></div>";
  }

  VIEWS.mine = function (el) {
    api("/donations/mine").then(function (list) {
      if (!list.length) { el.innerHTML = '<h2>My donations</h2>' + empty("Nothing posted yet. Use Donate to add your first one."); return; }
      el.innerHTML = '<h2>My donations</h2><div id="dlist">' + list.map(function (d) {
        var canVerify = d.status === "posted" && (d.verification_status === "pending" || d.verification_status === "manual_review");
        var verify = canVerify
          ? '<label class="btn small">' + (d.verification_status === "pending" ? "Add photo & verify" : "Replace photo") +
            '<input type="file" accept="image/jpeg,image/png,image/webp" data-change="verify" data-id="' + d.id + '" hidden></label>'
          : "";
        var matches = d.verification_status === "auto_approved" || d.verification_status === "admin_approved"
          ? '<button class="btn ghost small" data-action="matches" data-id="' + d.id + '">View matches</button>' : "";
        return donationRow(d, verify + matches) + '<div class="result" id="res' + d.id + '"></div>';
      }).join("") + "</div>";
      if (S.focus) { var n = $('[data-id="' + S.focus + '"]', el); n && n.scrollIntoView(); S.focus = null; }
    }).catch(function (e) { el.innerHTML = empty(e.message); });
  };

  function doVerify(input) {
    var id = input.getAttribute("data-id"), file = input.files[0];
    if (!file) return;
    var box = document.getElementById("res" + id);
    box.innerHTML = '<div class="notice">Checking the photo...</div>';
    var fd = new FormData(); fd.append("file", file);
    api("/donations/" + id + "/verify", { method: "POST", form: fd }).then(function (r) {
      var ai = r.ai, kind = "";
      if (r.donation.verification_status === "rejected" || r.donation.verification_status === "admin_rejected") kind = " bad";
      else if (r.donation.verification_status === "manual_review") kind = " warn";
      box.innerHTML = '<div class="notice' + kind + '"><strong>' + esc(r.message) + "</strong>" +
        (ai ? '<div class="mono">AI: ' + esc(ai.predicted_class) + " · " + Math.round(ai.confidence * 100) + "% confidence · threshold " + Math.round(ai.threshold * 100) + "%</div>" +
          '<ul class="top3">' + (ai.top3 || []).map(function (t) { return "<li>" + esc(t["class"]) + " " + (t.probability * 100).toFixed(1) + "%</li>"; }).join("") + "</ul>" : "") + "</div>";
      toast("Verification done");
      setTimeout(function () { if (S.view === "mine") VIEWS.mine($("#view")); }, 2500);
    }).catch(function (e) { box.innerHTML = '<div class="notice bad">' + esc(e.message) + "</div>"; });
  }

  function showMatches(id) {
    var box = document.getElementById("res" + id);
    box.innerHTML = '<div class="notice">Finding NGOs...</div>';
    api("/donations/" + id + "/matches").then(function (list) {
      if (!list.length) { box.innerHTML = '<div class="notice warn">No NGO currently accepts this food nearby.</div>'; return; }
      box.innerHTML = '<div class="matches">' + list.map(function (m, i) {
        var b = m.breakdown || {};
        function bar(l, v) { return '<div class="mini">' + l + '<div class="bar"><i style="width:' + Math.round((v || 0) * 100) + '%"></i></div></div>'; }
        return '<div class="match"><h4>' + (i + 1) + ". " + esc(m.org_name) + " " + chip("score " + (m.score * 100).toFixed(0))+ "</h4>" +
          '<div class="meta">' + esc(m.address) + " · " + m.distance_km + " km · about " + m.travel_minutes + " min · capacity left " + m.remaining_capacity + "</div>" +
          bar("Distance", b.distance) + bar("Urgency", b.urgency) + bar("Capacity", b.capacity) + "</div>";
      }).join("") + "</div>";
    }).catch(function (e) { box.innerHTML = '<div class="notice bad">' + esc(e.message) + "</div>"; });
  }

  // ---------- NGO ----------
  VIEWS.available = function (el) {
    el.innerHTML = '<div class="list-head"><h2>Available food</h2></div><div class="split"><div id="alist">' + loading() + '</div><div class="mapcol"><div class="bigmap" id="bigmap"></div></div></div>';
    api("/donations/available").then(function (list) {
      $("#alist").innerHTML = list.length ? list.map(function (d) {
        return donationRow(d, '<button class="btn small" data-action="accept" data-id="' + d.id + '">Accept</button>');
      }).join("") : empty("No verified food is waiting right now.");
      renderMap($("#bigmap"), list.map(function (d) {
        return { lat: d.lat, lng: d.lng, title: d.food_name, html: "<strong>" + esc(d.food_name) + "</strong><br>" + esc(d.quantity) + " units<br>" + esc(d.pickup_address) };
      }));
    }).catch(function (e) { $("#alist").innerHTML = empty(e.message); });
  };

  function pickupRow(p, actions) {
    return '<div class="row-item"><div class="grow"><strong>' + esc(p.food_name) + "</strong> " + chip(p.food_type) + " " + sChip(p.status) +
      '<div class="meta">' + esc(p.quantity) + " units · expires " + esc(fmt(p.expiry_at)) + "</div>" +
      '<div class="meta">From: ' + esc(p.pickup_address) + "</div>" +
      '<div class="meta">To: ' + esc(p.ngo_name) + ", " + esc(p.ngo_address) + "</div></div>" +
      '<div class="actions">' + (actions || "") + "</div></div>";
  }
  function pickupMap(el, list) {
    renderMap(el, list.map(function (p) {
      return { lat: p.lat, lng: p.lng, title: p.food_name, color: "#e8a317", html: "<strong>" + esc(p.food_name) + "</strong><br>" + esc(p.pickup_address) + "<br>To: " + esc(p.ngo_name) };
    }));
  }

  VIEWS.ngopickups = function (el) {
    el.innerHTML = "<h2>My pickups</h2><div id=\"plist\">" + loading() + "</div>";
    api("/pickups/mine").then(function (l) { $("#plist").innerHTML = l.length ? l.map(function (p) { return pickupRow(p); }).join("") : empty("No accepted donations yet."); })
      .catch(function (e) { $("#plist").innerHTML = empty(e.message); });
  };

  VIEWS.org = function (el) {
    el.innerHTML = '<div class="narrow">' + loading() + "</div>";
    api("/ngos/me").catch(function (e) { if (e.status === 404) return null; throw e; }).then(function (n) {
      var types = ["fruit", "vegetable", "bread", "cooked", "packaged"];
      var acc = n ? n.accepted_food_types : types;
      el.innerHTML = '<div class="narrow"><h2>Organisation profile</h2><p class="lede">' + (n ? "Update your details." : "Set this up first so donors can be matched to you.") + "</p>" +
        '<form class="form" id="orgform"><div class="field"><label>Organisation name</label><input name="org_name" required minlength="2" value="' + esc(n ? n.org_name : "") + '"></div>' +
        pickerHTML(n ? n.address : "", "Address") +
        '<div class="field"><label>Daily capacity (servings)</label><input name="capacity" type="number" min="1" max="100000" value="' + (n ? n.capacity : 100) + '" required></div>' +
        '<div class="field"><div class="legend">Accepted food</div><div class="checks">' + types.map(function (t) {
          return '<label><input type="checkbox" name="types" value="' + t + '"' + (acc.indexOf(t) > -1 ? " checked" : "") + "> " + t + "</label>";
        }).join("") + '</div></div><button class="btn" type="submit">Save</button></form></div>';
      var picker = initPicker(el, n ? { lat: n.lat, lng: n.lng } : null);
      $("#orgform").addEventListener("submit", function (e) {
        e.preventDefault();
        var f = e.target, pos = picker.get();
        if (!pos) return toast("Set the location first", true);
        var chosen = Array.prototype.map.call(f.querySelectorAll('input[name="types"]:checked'), function (c) { return c.value; });
        if (!chosen.length) return toast("Pick at least one food type", true);
        api("/ngos/me", { method: "PUT", json: { org_name: f.org_name.value.trim(), address: pos.address || f.address.value.trim(), lat: pos.lat, lng: pos.lng, capacity: parseInt(f.capacity.value, 10), accepted_food_types: chosen } })
          .then(function () { toast("Profile saved"); }).catch(fail);
      });
    }).catch(function (e) { el.innerHTML = empty(e.message); });
  };

  // ---------- volunteer ----------
  VIEWS.open = function (el) {
    el.innerHTML = '<div class="list-head"><h2>Open pickups</h2></div><div class="split"><div id="plist">' + loading() + '</div><div class="mapcol"><div class="bigmap" id="bigmap"></div></div></div>';
    api("/pickups/open").then(function (l) {
      $("#plist").innerHTML = l.length ? l.map(function (p) { return pickupRow(p, '<button class="btn small" data-action="claim" data-id="' + p.id + '">Claim</button>'); }).join("") : empty("No open pickups right now.");
      pickupMap($("#bigmap"), l);
    }).catch(function (e) { $("#plist").innerHTML = empty(e.message); });
  };
  VIEWS.vpickups = function (el) {
    el.innerHTML = '<div class="list-head"><h2>My pickups</h2></div><div class="split"><div id="plist">' + loading() + '</div><div class="mapcol"><div class="bigmap" id="bigmap"></div></div></div>';
    api("/pickups/mine").then(function (l) {
      $("#plist").innerHTML = l.length ? l.map(function (p) {
        var a = p.status === "accepted" ? '<button class="btn small" data-action="pickedup" data-id="' + p.id + '">Mark picked up</button>'
          : p.status === "picked_up" ? '<button class="btn small" data-action="delivered" data-id="' + p.id + '">Mark delivered</button>' : "";
        return pickupRow(p, a);
      }).join("") : empty("You have not claimed any pickups.");
      pickupMap($("#bigmap"), l.filter(function (p) { return p.status !== "delivered"; }));
    }).catch(function (e) { $("#plist").innerHTML = empty(e.message); });
  };

  // ---------- admin ----------
  VIEWS.overview = function (el) {
    el.innerHTML = "<h2>Overview</h2>" + loading();
    api("/admin/stats").then(function (s) {
      function walk(o) {
        return Object.keys(o).map(function (k) {
          var v = o[k];
          if (v && typeof v === "object") return '<div class="stack"><h3>' + esc(k.replace(/_/g, " ")) + '</h3><div class="kv">' +
            Object.keys(v).map(function (kk) { return "<span>" + esc(kk.replace(/_/g, " ")) + '</span><span class="mono">' + esc(typeof v[kk] === "object" ? JSON.stringify(v[kk]) : v[kk]) + "</span>"; }).join("") + "</div></div>";
          return '<div><div class="n">' + esc(typeof v === "number" && v % 1 ? v.toFixed(2) : v) + '</div><div class="l">' + esc(k.replace(/_/g, " ")) + "</div></div>";
        }).join("");
      }
      var flat = {}, nested = {};
      Object.keys(s).forEach(function (k) { (s[k] && typeof s[k] === "object" ? nested : flat)[k] = s[k]; });
      el.innerHTML = "<h2>Overview</h2>" + '<div class="band">' + walk(flat) + '</div><div class="cols">' + walk(nested) + "</div>";
    }).catch(function (e) {
      el.innerHTML = "<h2>Overview</h2>" + empty(e.status === 404 ? "Stats are not available yet. Add the stats route (Step 8) to the backend." : e.message);
    });
  };
  VIEWS.review = function (el) {
    el.innerHTML = "<h2>Review queue</h2><div id=\"rq\">" + loading() + "</div>";
    api("/admin/review-queue").then(function (l) {
      $("#rq").innerHTML = l.length ? l.map(function (d) {
        return '<div class="review"><div class="thumb"><img alt="Donation photo" data-img="' + d.id + '" width="120"></div><div class="grow"><strong>' + esc(d.food_name) + "</strong> " + chip(d.food_type) +
          '<div class="meta">' + esc(d.quantity) + " units · " + esc(d.pickup_address) + " · use before " + esc(fmt(d.expiry_at)) + "</div>" +
          (d.freshness_label ? '<div class="mono">AI: ' + esc(d.freshness_label) + " " + Math.round((d.freshness_confidence || 0) * 100) + "%</div>" : '<div class="meta">No AI result (not fruit, or no photo)</div>') + "</div>" +
          '<div class="actions"><button class="btn small" data-action="review" data-d="approve" data-id="' + d.id + '">Approve</button>' +
          '<button class="btn danger small" data-action="review" data-d="reject" data-id="' + d.id + '">Reject</button></div></div>';
      }).join("") : empty("Queue is empty.");
      hydrateImages($("#rq"));
    }).catch(function (e) { $("#rq").innerHTML = empty(e.message); });
  };
  VIEWS.all = function (el) {
    el.innerHTML = '<div class="list-head"><h2>All donations</h2></div><div class="split"><div id="alist">' + loading() + '</div><div class="mapcol"><div class="bigmap" id="bigmap"></div></div></div>';
    api("/donations").then(function (l) {
      $("#alist").innerHTML = l.length ? l.map(function (d) { return donationRow(d); }).join("") : empty("No donations yet.");
      renderMap($("#bigmap"), l.map(function (d) { return { lat: d.lat, lng: d.lng, title: d.food_name, html: "<strong>" + esc(d.food_name) + "</strong><br>" + esc(d.status) }; }));
    }).catch(function (e) { $("#alist").innerHTML = empty(e.message); });
  };

  // ---------- events ----------
  function refresh() { var v = VIEWS[S.view]; if (v) v($("#view")); }
  function act(path, msg) { return api(path, { method: "POST" }).then(function () { toast(msg); refresh(); }).catch(fail); }

  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-action]");
    if (!t) return;
    var a = t.getAttribute("data-action"), id = t.getAttribute("data-id");
    if (a === "authtab") { S.authTab = t.getAttribute("data-v"); renderAuth(); }
    else if (a === "nav") go(t.getAttribute("data-v"));
    else if (a === "signout") signOut();
    else if (a === "matches") showMatches(id);
    else if (a === "accept") { t.disabled = true; act("/donations/" + id + "/accept", "Accepted. A volunteer can now claim it."); }
    else if (a === "claim") { t.disabled = true; act("/pickups/" + id + "/claim", "Pickup claimed"); }
    else if (a === "pickedup") { t.disabled = true; act("/pickups/" + id + "/picked-up", "Marked as picked up"); }
    else if (a === "delivered") { t.disabled = true; act("/pickups/" + id + "/delivered", "Delivered. Thank you!"); }
    else if (a === "review") {
      t.disabled = true;
      api("/admin/donations/" + id + "/review", { method: "POST", json: { decision: t.getAttribute("data-d") } })
        .then(function () { toast("Decision saved"); refresh(); }).catch(function (er) { fail(er); t.disabled = false; });
    }
  });
  document.addEventListener("change", function (e) {
    if (e.target.getAttribute && e.target.getAttribute("data-change") === "verify") doVerify(e.target);
  });

  // ---------- start ----------
  S.token = store("fs_token");
  if (S.token) boot(); else renderAuth();
})();
