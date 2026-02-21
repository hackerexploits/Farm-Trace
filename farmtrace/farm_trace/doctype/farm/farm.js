frappe.ui.form.on("Farm", {

    onload_post_render(frm) {
        let kobo_boundary =
            "-3.3658215 36.7059214 1454.9000244140625 2.7;" +
            "-3.3658175 36.7059043 1454.9000244140625 3.616;" +
            "-3.3656591 36.7061084 1454.4000244140625 9.275;" +
            "-3.3656361 36.7059905 1454.199951171875 20.501;" +
            "-3.3656302 36.706017 1454.300048828125 24.822;" +
            "-3.3657807 36.7060211 1454.300048828125 5.885;" +
            "-3.365507 36.706104 1454.5 16.097;" +
            "-3.3656554 36.7059443 1454.5 3.916;" +
            "-3.3658215 36.7059214 1454.9000244140625 2.7";

        let coordinates = kobo_boundary.split(";").map(p => {
            let parts = p.trim().split(" ");
            return [parseFloat(parts[0]), parseFloat(parts[1])];
        });

        load_leaflet(frm, () => draw_polygon(frm, coordinates));
    }
});


function load_leaflet(frm, callback) {
    if (!document.getElementById("leaflet-css")) {
        let css  = document.createElement("link");
        css.id   = "leaflet-css";
        css.rel  = "stylesheet";
        css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(css);
    }
    if (window.L) { callback(); return; }
    let script    = document.createElement("script");
    script.src    = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload = callback;
    document.head.appendChild(script);
}


function draw_polygon(frm, coordinates) {

    if (frm._farm_map) {
        frm._farm_map.remove();
        frm._farm_map = null;
    }

    // ✅ STEP 1 — Inject CSS to bust out of Frappe's column constraints
    if (!document.getElementById("farm-map-styles")) {
        let style = document.createElement("style");
        style.id  = "farm-map-styles";
        style.innerHTML = `
            /* Force the field row, column, section to not clip the map */
            [data-fieldname="polygon_map"],
            [data-fieldname="polygon_map"] .form-column,
            [data-fieldname="polygon_map"] .frappe-field,
            [data-fieldname="polygon_map"] ~ .form-column,
            .farm-map-section .section-body,
            .farm-map-section .form-column {
                width: 100% !important;
                max-width: 100% !important;
                flex: 0 0 100% !important;
                padding: 0 !important;
                overflow: visible !important;
            }

            #farm-map-container {
                width: 100% !important;
                height: 520px !important;
                display: block !important;
                position: relative !important;
            }

            #farm-map {
                width: 100% !important;
                height: 520px !important;
                display: block !important;
                border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }

            /* Fix Leaflet tiles not covering full area */
            #farm-map .leaflet-container {
                width: 100% !important;
                height: 100% !important;
            }
        `;
        document.head.appendChild(style);
    }

    // ✅ STEP 2 — Find the actual wrapper and bust every parent's width
    let wrapper = frm.fields_dict.polygon_map.$wrapper;

    // Walk up and remove any width restrictions Frappe set
    let node = wrapper[0];
    for (let i = 0; i < 8; i++) {
        if (!node || node === document.body) break;
        node.style.setProperty("width",     "100%",    "important");
        node.style.setProperty("max-width", "100%",    "important");
        node.style.setProperty("flex",      "0 0 100%","important");
        node.style.setProperty("overflow",  "visible", "important");
        node.style.setProperty("padding",   "0",       "important");
        node = node.parentElement;
    }

    // ✅ STEP 3 — Render map container
    wrapper[0].innerHTML = `
        <div id="farm-map-container">
            <div id="farm-map"></div>
        </div>
        <div id="farm-info" style="
            margin-top: 10px;
            font-size: 13px;
            color: #444;
            font-family: sans-serif;
            padding: 8px 12px;
            background: #f8f8f8;
            border-radius: 6px;
            border-left: 4px solid #4caf50;
        ">
            🌿 <b>Farm Boundary</b> &nbsp;·&nbsp;
            <span id="farm-area-ha">calculating…</span> &nbsp;·&nbsp;
            <span id="farm-pts"></span>
        </div>
    `;

    // ✅ STEP 4 — Compute center upfront so map has a valid view immediately
    let lats       = coordinates.map(c => c[0]);
    let lngs       = coordinates.map(c => c[1]);
    let center_lat = (Math.min(...lats) + Math.max(...lats)) / 2;
    let center_lng = (Math.min(...lngs) + Math.max(...lngs)) / 2;

    // ✅ STEP 5 — Init map after layout settles
    setTimeout(() => {

        // Confirm container size before proceeding
        let el = document.getElementById("farm-map");
        console.log(`[FarmMap] Container: ${el.offsetWidth}px × ${el.offsetHeight}px`);

        let map = L.map("farm-map", {
            zoomControl:       true,
            attributionControl: true
        });
        frm._farm_map = map;

        // Give Leaflet a real center immediately — prevents blank tile syndrome
        map.setView([center_lat, center_lng], 18);

        // Tiles
        let satellite = L.tileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            { maxZoom: 22, attribution: "© Esri" }
        );
        let labels = L.tileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}",
            { maxZoom: 22 }
        );
        let osm = L.tileLayer(
            "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            { maxZoom: 19, attribution: "© OpenStreetMap" }
        );

        satellite.addTo(map);
        labels.addTo(map);

        L.control.layers(
            { "🛰️ Satellite": L.layerGroup([satellite, labels]), "🗺️ Street": osm },
            {},
            { position: "topright", collapsed: false }
        ).addTo(map);

        // Polygon
        let polygon = L.polygon(coordinates, {
            color: "#FFEB3B", weight: 3, opacity: 1,
            fillColor: "#FFEB3B", fillOpacity: 0.25
        }).addTo(map);

        // GPS dots
        coordinates.forEach((c, i) => {
            if (i === coordinates.length - 1) return;
            L.circleMarker(c, {
                radius: 6, color: "#fff", weight: 2,
                fillColor: "#FFEB3B", fillOpacity: 1
            }).addTo(map);
        });

        // ✅ STEP 6 — Triple invalidate to handle Frappe reflows
        let bounds = polygon.getBounds();

        map.invalidateSize(true);
        map.fitBounds(bounds, { padding: [40, 40] });

        setTimeout(() => {
            map.invalidateSize(true);
            map.fitBounds(bounds, { padding: [40, 40] });
        }, 300);

        setTimeout(() => {
            map.invalidateSize(true);
            map.fitBounds(bounds, { padding: [40, 40] });
        }, 800);

        // Info bar
        let area_ha = compute_area_ha(coordinates);
        let el_area = document.getElementById("farm-area-ha");
        let el_pts  = document.getElementById("farm-pts");
        if (el_area) el_area.textContent = `~${area_ha.toFixed(4)} ha`;
        if (el_pts)  el_pts.textContent  = `${coordinates.length - 1} GPS points`;

    }, 700);
}


function compute_area_ha(coords) {
    let n = coords.length - 1;
    let area = 0;
    const R = 6371000;
    for (let i = 0; i < n; i++) {
        let j    = (i + 1) % n;
        let lat1 = coords[i][0] * Math.PI / 180;
        let lat2 = coords[j][0] * Math.PI / 180;
        let dLon = (coords[j][1] - coords[i][1]) * Math.PI / 180;
        area += dLon * (2 + Math.sin(lat1) + Math.sin(lat2));
    }
    return Math.abs(area * R * R / 2) / 10000;
}
