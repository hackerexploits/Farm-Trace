"""Update Farms Map block height to 75vh (3/4 of viewport)."""
import frappe


def execute():
	if frappe.db.exists("Custom HTML Block", "Farms Map"):
		doc = frappe.get_doc("Custom HTML Block", "Farms Map")
		# Update map height from 450px to 75vh
		if "450px" in doc.style:
			doc.style = doc.style.replace("height: 450px", "height: 75vh")
			doc.save(ignore_permissions=True)
			frappe.db.commit()
