import frappe
from frappe import _
from frappe.utils import flt, getdate


def get_or_create_supplier_from_farmer(farmer_name):
	"""Return supplier linked to farmer, creating one when missing."""
	farmer = frappe.get_doc("Farmer", farmer_name)

	if farmer.supplier:
		return farmer.supplier

	if frappe.db.exists("Supplier", farmer.name):
		supplier = farmer.name
	else:
		supplier_doc = frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": farmer.full_name or farmer.name,
				"supplier_group": "All Supplier Groups",
				"supplier_type": "Individual",
			}
		)
		supplier_doc.name = farmer.name
		supplier_doc.insert(ignore_permissions=True)
		supplier = supplier_doc.name

	farmer.db_set("supplier", supplier)
	return supplier


def _get_default_warehouse(company):
	warehouse = frappe.get_single_value("Stock Settings", "default_warehouse")
	if warehouse and frappe.get_cached_value("Warehouse", warehouse, "company") == company:
		return warehouse

	return frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 0, "disabled": 0},
		"name",
		order_by="creation asc",
	)


def _get_purchase_defaults():
	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		frappe.throw(_("Please set a default Company"))

	warehouse = _get_default_warehouse(company)
	return company, warehouse


def _validate_intake_for_receipt(intake):
	if intake.docstatus != 1:
		frappe.throw(_("Farm Purchase Intake {0} must be submitted").format(intake.name))

	if intake.receipt_created and intake.purchase_receipt:
		frappe.throw(
			_("Purchase Receipt {0} already exists for {1}").format(
				intake.purchase_receipt, intake.name
			)
		)

	if not intake.items:
		frappe.throw(_("Farm Purchase Intake {0} has no collected produce rows").format(intake.name))


def _build_pr_item_row(intake, row, warehouse):
	if not row.item:
		frappe.throw(_("Item missing in collected produce row for intake {0}").format(intake.name))

	item_details = frappe.db.get_value(
		"Item", row.item, ["item_name", "stock_uom"], as_dict=True
	) or {}
	uom = intake.uom or item_details.get("stock_uom")
	stock_uom = item_details.get("stock_uom") or uom

	item_row = {
		"item_code": row.item,
		"item_name": item_details.get("item_name") or row.item,
		"qty": flt(row.quantity),
		"rate": flt(row.unit_price),
		"price_list_rate": flt(row.unit_price),
		"uom": uom,
		"stock_uom": stock_uom,
		"conversion_factor": 1,
		"warehouse": warehouse,
	}

	intake_link_field = _get_intake_link_field()
	if intake_link_field:
		item_row[intake_link_field] = intake.name

	barcode_field = _get_barcode_field()
	if barcode_field and row.barcode:
		item_row[barcode_field] = row.barcode

	return item_row


def _get_intake_link_field():
	if frappe.get_meta("Purchase Receipt Item").has_field("farm_purchase_intake"):
		return "farm_purchase_intake"
	if frappe.get_meta("Purchase Receipt Item").has_field("custom_farm_purchase_intake"):
		return "custom_farm_purchase_intake"
	return None


def _get_barcode_field():
	if frappe.get_meta("Purchase Receipt Item").has_field("custom_transaction_barcode"):
		return "custom_transaction_barcode"
	if frappe.get_meta("Purchase Receipt Item").has_field("transaction_barcode"):
		return "transaction_barcode"
	return None


def _build_purchase_receipt_data(intake_names):
	if isinstance(intake_names, str):
		intake_names = frappe.parse_json(intake_names)

	if not intake_names:
		frappe.throw(_("Select at least one Farm Purchase Intake"))

	company, warehouse = _get_purchase_defaults()
	all_items = []
	supplier = None
	posting_date = None
	currency = None

	for name in intake_names:
		intake = frappe.get_doc("Farm Purchase Intake", name)
		_validate_intake_for_receipt(intake)

		intake_supplier = get_or_create_supplier_from_farmer(intake.farmer)
		if supplier and supplier != intake_supplier:
			frappe.throw(_("Selected intakes must belong to the same farmer/supplier"))
		supplier = intake_supplier

		posting_date = intake.purchase_date or posting_date
		currency = intake.currency or currency

		for row in intake.items:
			all_items.append(_build_pr_item_row(intake, row, warehouse))

	if not all_items:
		frappe.throw(_("No purchase receipt items found in selected intakes"))

	return {
		"company": company,
		"supplier": supplier,
		"posting_date": posting_date or getdate(),
		"currency": currency,
		"items": all_items,
	}


def _make_purchase_receipt(intake_names):
	data = _build_purchase_receipt_data(intake_names)

	pr = frappe.new_doc("Purchase Receipt")
	pr.company = data["company"]
	pr.supplier = data["supplier"]
	pr.posting_date = data["posting_date"]
	if data.get("currency"):
		pr.currency = data["currency"]

	for item in data["items"]:
		pr.append("items", item)

	pr.insert(ignore_permissions=True)
	return pr


def _link_intakes_to_receipt(intake_names, purchase_receipt):
	for name in intake_names:
		frappe.db.set_value(
			"Farm Purchase Intake",
			name,
			{
				"purchase_receipt": purchase_receipt,
				"receipt_created": 1,
			},
			update_modified=False,
		)


@frappe.whitelist()
def get_items_from_farm_intake(intake_names):
	"""Return Purchase Receipt header and item rows for selected intakes."""
	return _build_purchase_receipt_data(intake_names)


@frappe.whitelist()
def create_purchase_receipt_from_intake(intake_name):
	"""Create a draft Purchase Receipt from one submitted Farm Purchase Intake."""
	if isinstance(intake_name, str) and intake_name.startswith("["):
		intake_names = frappe.parse_json(intake_name)
	else:
		intake_names = [intake_name]

	pr = _make_purchase_receipt(intake_names)
	_link_intakes_to_receipt(intake_names, pr.name)
	return pr.name


def update_intake_receipt_status(doc, method=None):
	"""Link intakes when a Purchase Receipt is submitted."""
	intake_names = set()
	link_field = _get_intake_link_field()

	for row in doc.get("items") or []:
		intake_name = row.get(link_field) if link_field else None
		if intake_name:
			intake_names.add(intake_name)

	for intake_name in intake_names:
		frappe.db.set_value(
			"Farm Purchase Intake",
			intake_name,
			{
				"purchase_receipt": doc.name,
				"receipt_created": 1,
			},
			update_modified=False,
		)


def _get_linked_intake_names(doc):
	"""Collect Farm Purchase Intake names linked to a Purchase Receipt."""
	intake_names = set()
	link_field = _get_intake_link_field()

	for row in doc.get("items") or []:
		intake_name = row.get(link_field) if link_field else None
		if intake_name:
			intake_names.add(intake_name)

	intake_names.update(
		frappe.get_all(
			"Farm Purchase Intake",
			filters={"purchase_receipt": doc.name},
			pluck="name",
		)
	)

	return intake_names


def _clear_intake_receipt_links(doc):
	for intake_name in _get_linked_intake_names(doc):
		intake_pr = frappe.db.get_value("Farm Purchase Intake", intake_name, "purchase_receipt")
		if intake_pr == doc.name:
			frappe.db.set_value(
				"Farm Purchase Intake",
				intake_name,
				{
					"purchase_receipt": None,
					"receipt_created": 0,
				},
				update_modified=False,
			)


def clear_intake_receipt_status(doc, method=None):
	"""Clear intake receipt link when Purchase Receipt is cancelled."""
	_clear_intake_receipt_links(doc)


def clear_intake_receipt_status_on_trash(doc, method=None):
	"""Clear intake receipt link when a draft Purchase Receipt is deleted."""
	if doc.docstatus != 0:
		return

	_clear_intake_receipt_links(doc)
