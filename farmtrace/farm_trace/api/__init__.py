# Copyright (c) 2026, Mania and contributors

import frappe


@frappe.whitelist()
def get_farm_locations():
	"""Get farm name, latitude, longitude for farms that have coordinates."""
	farms = frappe.get_all(
		"Farm",
		fields=["name", "farm_name", "farmer", "village", "latitude", "longitude"],
	)
	result = []
	for f in farms:
		lat = f.get("latitude")
		lng = f.get("longitude")
		if not lat or not lng:
			continue
		try:
			lat_f = float(str(lat).strip())
			lng_f = float(str(lng).strip())
			if -90 <= lat_f <= 90 and -180 <= lng_f <= 180:
				result.append({
					"name": f["name"],
					"farm_name": f.get("farm_name"),
					"farmer": f.get("farmer"),
					"village": f.get("village"),
					"latitude": str(lat_f),
					"longitude": str(lng_f),
				})
		except (ValueError, TypeError):
			pass
	return result
