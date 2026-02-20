
# In farmtrace/farm_trace/api.py
import frappe

@frappe.whitelist()
def get_farm_locations():
    return frappe.get_all(
        'Farm',
        fields=[
            'name', 'farm_name', 'farmer', 'village',
            'latitude', 'longitude',
            'country',        # ← confirm exact fieldname in Farm doctype
            'district',       # ← confirm exact fieldname
            'crop_type',      # ← confirm exact fieldname
            'farmer_group'    # ← confirm exact fieldname
        ],
        filters={'latitude': ['!=', ''], 'longitude': ['!=', '']}
    )