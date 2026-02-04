# Copyright (c) 2026, Mania and contributors
# For license information, please see license.txt

import frappe


def after_install():
	create_farms_map_custom_block()
	update_workspace_with_farms_map()


def create_farms_map_custom_block():
	"""Create the Farms Map Custom HTML Block if it doesn't exist."""
	if frappe.db.exists("Custom HTML Block", "Farms Map"):
		return

	html = """<div class="farms-map-container">
	<div class="map-header">
		<h5 class="mb-0">Farm Locations Map</h5>
		<p class="text-muted small mb-0">Farms with latitude and longitude coordinates</p>
	</div>
	<div id="farms-map" class="farms-map"></div>
	<div class="map-legend mt-2">
		<span class="badge badge-primary">Farm</span>
	</div>
</div>"""

	css = """.farms-map-container {
	padding: 1rem;
	background: var(--fg-color);
	border-radius: var(--border-radius);
	border: 1px solid var(--border-color);
}
.farms-map {
	height: 75vh;
	width: 100%;
	border-radius: var(--border-radius);
	z-index: 0;
}
.map-header {
	margin-bottom: 1rem;
}"""

	script = """(function() {
	if (typeof L === 'undefined') {
		const link = document.createElement('link');
		link.rel = 'stylesheet';
		link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
		link.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
		link.crossOrigin = '';
		document.head.appendChild(link);
		
		const script = document.createElement('script');
		script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
		script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
		script.crossOrigin = '';
		script.onload = initMap;
		document.head.appendChild(script);
	} else {
		initMap();
	}
	
	function initMap() {
		const mapEl = root_element.querySelector('#farms-map');
		if (!mapEl) return;
		
		const map = L.map(mapEl).setView([0, 0], 2);
		L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
		}).addTo(map);
		
		frappe.call({
			method: 'farmtrace.farm_trace.api.get_farm_locations',
			callback: function(r) {
				if (r.message && r.message.length > 0) {
					const bounds = [];
					r.message.forEach(function(farm) {
						const lat = parseFloat(farm.latitude);
						const lng = parseFloat(farm.longitude);
						if (!isNaN(lat) && !isNaN(lng)) {
							const marker = L.marker([lat, lng]).addTo(map);
							const popupContent = '<b>' + (farm.farm_name || farm.name) + '</b><br>' +
								(farm.farmer ? 'Farmer: ' + farm.farmer : '') + '<br>' +
								(farm.village ? 'Village: ' + farm.village : '') + '<br>' +
								'<a href="/app/farm/' + encodeURIComponent(farm.name) + '" target="_blank">View Farm</a>';
							marker.bindPopup(popupContent);
							bounds.push([lat, lng]);
						}
					});
					if (bounds.length > 0) {
						map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
					}
				} else {
					mapEl.innerHTML = '<div class="text-muted text-center p-5">No farms with location data found.</div>';
				}
			}
		});
	}
})();"""

	doc = frappe.get_doc({
		"doctype": "Custom HTML Block",
		"name": "Farms Map",
		"html": html,
		"style": css,
		"script": script,
	})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()


def update_workspace_with_farms_map():
	"""Add Farms Map custom block to FarmTrace Dashboard workspace."""
	workspace = frappe.get_doc("Workspace", "FarmTrace Dashboard")
	
	# Parse content
	import json
	content = json.loads(workspace.content) if isinstance(workspace.content, str) else workspace.content
	
	# Check if Farms Map block already exists
	farms_map_exists = any(
		block.get("type") == "custom_block" and 
		block.get("data", {}).get("custom_block_name") == "Farms Map"
		for block in content
	)
	if farms_map_exists:
		return
	
	# Add separator and Farms Map block at the end
	import uuid
	content.append({
		"id": str(uuid.uuid4())[:11],
		"type": "custom_block",
		"data": {"custom_block_name": "Farms Map", "col": 12}
	})
	
	# Add to custom_blocks if not present
	block_names = [cb.custom_block_name for cb in workspace.custom_blocks]
	if "Farms Map" not in block_names:
		workspace.append("custom_blocks", {"custom_block_name": "Farms Map", "label": "Farms Map"})
	
	workspace.content = json.dumps(content)
	workspace.save(ignore_permissions=True)
	frappe.db.commit()
