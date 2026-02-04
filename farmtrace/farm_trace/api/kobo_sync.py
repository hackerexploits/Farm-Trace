# Copyright (c) 2026, Mania and contributors
# For license information, please see license.txt

import frappe
from frappe import _


@frappe.whitelist()
def sync_now(sync_type="All"):
	"""Manual sync trigger. sync_type: Farmer, Farm, or All."""
	settings = frappe.get_single("Kobo Toolbox Settings")
	if not settings.enable_sync:
		frappe.throw(_("Kobo sync is disabled. Enable it in Kobo Toolbox Settings."))
	if not settings.api_token:
		frappe.throw(_("API Token is required in Kobo Toolbox Settings."))

	result = run_kobo_sync(
		sync_type=sync_type,
		triggered_by="Manual",
		settings=settings,
	)
	return result.get("message", "Sync completed.")


def run_scheduled_kobo_sync():
	"""Called by scheduler every 15 minutes."""
	settings = frappe.get_single("Kobo Toolbox Settings")
	if not settings.enable_sync or not settings.api_token:
		return
	run_kobo_sync(sync_type="All", triggered_by="Scheduled", settings=settings)


def run_kobo_sync(sync_type="All", triggered_by="Scheduled", settings=None):
	"""Run Kobo sync for Farmer and/or Farm forms."""
	if settings is None:
		settings = frappe.get_single("Kobo Toolbox Settings")

	base_url = (settings.api_url or "").rstrip("/")
	token = settings.get_password("api_token")
	if not base_url or not token:
		return {"success": False, "message": "API URL and Token required"}

	headers = {"Authorization": f"Token {token}"}
	results = {"farmer": None, "farm": None}

	# Sync Farmers
	if sync_type in ("All", "Farmer") and settings.farmer_form_asset_uid:
		results["farmer"] = _sync_farmers(
			base_url=base_url,
			headers=headers,
			asset_uid=settings.farmer_form_asset_uid,
			match_field=settings.farmer_match_field or "farmer_id",
			mappings=settings.farmer_field_mappings or [],
			triggered_by=triggered_by,
		)

	# Sync Farms
	if sync_type in ("All", "Farm") and settings.farm_form_asset_uid:
		results["farm"] = _sync_farms(
			base_url=base_url,
			headers=headers,
			asset_uid=settings.farm_form_asset_uid,
			match_field=settings.farm_match_field or "farm_id",
			mappings=settings.farm_field_mappings or [],
			triggered_by=triggered_by,
		)

	# Build message
	msg_parts = []
	if results["farmer"]:
		r = results["farmer"]
		msg_parts.append(f"Farmers: {r['created']} created, {r['updated']} updated, {r['failed']} failed")
	if results["farm"]:
		r = results["farm"]
		msg_parts.append(f"Farms: {r['created']} created, {r['updated']} updated, {r['failed']} failed")

	return {"success": True, "message": "; ".join(msg_parts) if msg_parts else "No forms configured."}


def _fetch_kobo_submissions(base_url, headers, asset_uid):
	"""Fetch submissions from Kobo API v2."""
	url = f"{base_url}/api/v2/assets/{asset_uid}/data/"
	try:
		import requests
		resp = requests.get(url, headers=headers, timeout=60)
		resp.raise_for_status()
		data = resp.json()
		# Kobo returns {"results": [...]} or list
		if isinstance(data, dict) and "results" in data:
			return data["results"]
		if isinstance(data, list):
			return data
		return []
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Kobo API Error")
		raise frappe.ValidationError(_("Kobo API error: {0}").format(str(e)))


def _build_field_map(mappings):
	"""Build kobo_field -> target_field dict from child table."""
	out = {}
	for m in mappings:
		kobo = (m.get("kobo_field_name") or "").strip()
		target = (m.get("farmer_field") or m.get("farm_field") or "").strip()
		if kobo and target:
			out[kobo] = target
	return out


def _sync_farmers(base_url, headers, asset_uid, match_field, mappings, triggered_by):
	"""Sync Farmer submissions from Kobo to Farmer doctype."""
	field_map = _build_field_map(mappings)
	if not field_map:
		# Default mappings for common fields
		field_map = {
			"farmer_id": "farmer_id",
			"farmer_code": "farmer_code",
			"first_name": "first_name",
			"last_name": "last_name",
			"latitude": "latitude",
			"longitude": "longitude",
			"phone_number": "phone_number",
			"mobile_number": "mobile_number",
			"address": "address",
		}

	submissions = _fetch_kobo_submissions(base_url, headers, asset_uid)
	created, updated, failed = 0, 0, 0
	errors = []

	for sub in submissions:
		try:
			# Map Kobo fields to Farmer fields
			values = {}
			for kobo_key, farmer_field in field_map.items():
				val = sub.get(kobo_key)
				if val is not None and val != "":
					values[farmer_field] = str(val).strip() if val else None

			match_val = values.get(match_field) or sub.get(match_field)
			if not match_val:
				failed += 1
				errors.append(f"Submission missing match field '{match_field}'")
				continue

			# Find existing or create new
			existing = frappe.db.get_value("Farmer", {match_field: match_val}, "name")
			if existing:
				doc = frappe.get_doc("Farmer", existing)
				for k, v in values.items():
					if hasattr(doc, k):
						setattr(doc, k, v)
				doc.flags.ignore_permissions = True
				doc.save()
				updated += 1
			else:
				doc = frappe.new_doc("Farmer")
				for k, v in values.items():
					if hasattr(doc, k):
						setattr(doc, k, v)
				doc.flags.ignore_permissions = True
				doc.insert()
				created += 1
		except Exception as e:
			failed += 1
			errors.append(str(e)[:200])

	_log_sync("Farmer", triggered_by, created, updated, failed, errors)
	return {"created": created, "updated": updated, "failed": failed}


def _sync_farms(base_url, headers, asset_uid, match_field, mappings, triggered_by):
	"""Sync Farm submissions from Kobo to Farm doctype."""
	field_map = _build_field_map(mappings)
	if not field_map:
		field_map = {
			"farm_id": "farm_id",
			"farm_name": "farm_name",
			"farmer": "farmer",
			"latitude": "latitude",
			"longitude": "longitude",
			"hectares": "hectares",
		}

	submissions = _fetch_kobo_submissions(base_url, headers, asset_uid)
	created, updated, failed = 0, 0, 0
	errors = []

	for sub in submissions:
		try:
			values = {}
			for kobo_key, farm_field in field_map.items():
				val = sub.get(kobo_key)
				if val is not None and val != "":
					values[farm_field] = str(val).strip() if val else None

			match_val = values.get(match_field) or sub.get(match_field)
			if not match_val:
				failed += 1
				errors.append(f"Submission missing match field '{match_field}'")
				continue

			# Farm links to Farmer - ensure farmer exists or resolve by name
			farmer_val = values.get("farmer")
			if farmer_val:
				# Try match by farmer name (Farmer doc name) or farmer_id
				farmer_name = frappe.db.get_value("Farmer", {"farmer_id": farmer_val}, "name")
				if not farmer_name:
					farmer_name = frappe.db.get_value("Farmer", {"farmer_code": farmer_val}, "name")
				if not farmer_name:
					farmer_name = frappe.db.get_value("Farmer", {"name": farmer_val}, "name")
				if farmer_name:
					values["farmer"] = farmer_name

			existing = frappe.db.get_value("Farm", {match_field: match_val}, "name")
			if existing:
				doc = frappe.get_doc("Farm", existing)
				for k, v in values.items():
					if hasattr(doc, k):
						setattr(doc, k, v)
				doc.flags.ignore_permissions = True
				doc.save()
				updated += 1
			else:
				doc = frappe.new_doc("Farm")
				for k, v in values.items():
					if hasattr(doc, k):
						setattr(doc, k, v)
				# Farm requires farmer and farm_name; autoname uses farm_id
				if not doc.get("farm_id"):
					doc.farm_id = sub.get("_uuid", "")[:50] or f"KOBO-{match_val}"
				if not doc.get("farmer") and farmer_val:
					doc.farmer = farmer_val
				if not doc.get("farm_name"):
					doc.farm_name = values.get("farm_name") or match_val or "Unnamed Farm"
				doc.flags.ignore_permissions = True
				doc.insert()
				created += 1
		except Exception as e:
			failed += 1
			errors.append(str(e)[:200])

	_log_sync("Farm", triggered_by, created, updated, failed, errors)
	return {"created": created, "updated": updated, "failed": failed}


def _log_sync(sync_type, triggered_by, created, updated, failed, errors):
	from frappe.utils import now
	status = "Success" if failed == 0 else ("Failed" if created == 0 and updated == 0 else "Partial")
	log = frappe.get_doc(
		doctype="Kobo Sync Log",
		sync_type=sync_type,
		status=status,
		triggered_by=triggered_by,
		started_at=now(),
		ended_at=now(),
		records_created=created,
		records_updated=updated,
		records_failed=failed,
		error_log="\n".join(errors[:20]) if errors else None,
	)
	log.insert(ignore_permissions=True)
	frappe.db.commit()
