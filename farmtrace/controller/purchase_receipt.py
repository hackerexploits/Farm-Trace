import frappe
from frappe.utils import flt
from frappe import _


def get_or_create_supplier_from_farmer(farmer_name):
    """Return supplier linked to farmer.
    Creates supplier if missing using Farmer ID as Supplier ID.
    """

    farmer = frappe.get_doc("Farmer", farmer_name)

    # Already linked
    if farmer.supplier:
        return farmer.supplier

    frappe.logger().info(
        f"Supplier missing for Farmer {farmer.name}. Creating one."
    )

    # Prevent duplicate creation (important in concurrent calls)
    if frappe.db.exists("Supplier", farmer.name):
        supplier = farmer.name
    else:
        supplier_doc = frappe.get_doc({
            "doctype": "Supplier",
            "supplier_name": farmer.full_name or farmer.name,
            "supplier_group": "All Supplier Groups",
            "supplier_type": "Individual",
        })

        # Farmer ID becomes Supplier ID
        supplier_doc.name = farmer.name
        supplier_doc.insert(ignore_permissions=True)

        supplier = supplier_doc.name

    # Link back to Farmer
    farmer.db_set("supplier", supplier)

    return supplier




@frappe.whitelist()
def get_items_from_farm_intake(intake_names):

    if isinstance(intake_names, str):
        intake_names = frappe.parse_json(intake_names)

    all_items = []
    supplier = None
    posting_date = None

    for name in intake_names:
        intake = frappe.get_doc("Farm Purchase Intake", name)

        # ✅ Get or auto-create supplier
        supplier = get_or_create_supplier_from_farmer(intake.farmer)

        posting_date = intake.purchase_date

        # ✅ Loop child items
        for row in intake.items:
            if not row.item:
                frappe.throw(
                    _("Item missing in child row of intake {0}")
                    .format(intake.name)
                )

            all_items.append({
                "item_code": row.item,
                "item_name": row.item,
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
