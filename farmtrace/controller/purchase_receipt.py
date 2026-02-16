import frappe
from frappe.utils import flt


@frappe.whitelist()
def get_items_from_farm_intake(intake_names):

    if isinstance(intake_names, str):
        intake_names = frappe.parse_json(intake_names)

    all_items = []
    supplier = None
    posting_date = None

    for name in intake_names:
        intake = frappe.get_doc("Farm Purchase Intake", name)

        # ✅ Get supplier from farmer
        supplier = frappe.db.get_value("Farmer", intake.farmer, "supplier")
        if not supplier:
            frappe.throw(f"Farmer {intake.farmer} has no Supplier linked")

        posting_date = intake.purchase_date

        # ✅ Loop child table items
        for row in intake.items:
            if not row.item:
                frappe.throw(f"Item missing in child row of intake {intake.name}")
            
            all_items.append({
                "item_code": row.item,  # child table item link
                "qty": flt(row.quantity),
                "uom": intake.uom,
                "farm_purchase_intake": intake.name,
                "barcode": getattr(row, "barcode", None)
            })

    return {
        "supplier": supplier,
        "posting_date": posting_date,
        "items": all_items
    }
