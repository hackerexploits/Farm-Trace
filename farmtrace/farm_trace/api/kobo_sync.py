# Copyright (c) 2026, Mania and contributors
# For license information, please see license.txt

import frappe
from frappe import _


# ─── Constants ────────────────────────────────────────────────────────────────

# Fields that must NEVER be normalized — store exactly as Kobo sends them
RAW_VALUE_FIELDS = {"landmark", "farm_boundary", "gps", "farm_gps", "boundary"}

# Maps: target_doctype -> (image_field_on_doc, xpath_keywords_to_match)
DOCTYPE_IMAGE_CONFIG = {
	"Farmer": ("contract_image", ["photo_farmer", "farmer_photo", "photo"]),
	"Farm":   ("photo",          ["photo_farm", "farm_photo", "photo"]),
}


# ─── Public API ───────────────────────────────────────────────────────────────

@frappe.whitelist()
def sync_now():
	"""Manual sync - syncs all enabled Kobo Form Configurations."""
	settings = frappe.get_single("Kobo Toolbox Settings")
	if not settings.enable_sync:
		frappe.throw(_("Kobo sync is disabled. Enable it in Kobo Toolbox Settings."))
	if not settings.api_token:
		frappe.throw(_("API Token is required in Kobo Toolbox Settings."))

	result = run_kobo_sync(triggered_by="Manual", settings=settings)
	return result.get("message", "Sync completed.")


@frappe.whitelist()
def sync_form(form_name):
	"""Sync a single Kobo Form Configuration by name."""
	settings = frappe.get_single("Kobo Toolbox Settings")
	if not settings.api_token:
		frappe.throw(_("API Token is required in Kobo Toolbox Settings."))

	config = frappe.get_doc("Kobo Form Configuration", form_name)
	if not config.enabled:
		frappe.throw(_("This form configuration is disabled."))

	result = _sync_single_form(
		base_url=(settings.api_url or "https://kf.kobotoolbox.org").rstrip("/"),
		headers={"Authorization": f"Token {settings.get_password('api_token')}"},
		config=config,
		triggered_by="Manual",
	)
	return result.get("message", "Sync completed.")


def run_scheduled_kobo_sync():
	"""Called by scheduler every 15 minutes."""
	settings = frappe.get_single("Kobo Toolbox Settings")
	if not settings.enable_sync or not settings.api_token:
		return
	run_kobo_sync(triggered_by="Scheduled", settings=settings)


def run_kobo_sync(triggered_by="Scheduled", settings=None):
	"""Run Kobo sync for all enabled form configurations."""
	if settings is None:
		settings = frappe.get_single("Kobo Toolbox Settings")

	base_url = (settings.api_url or "https://kf.kobotoolbox.org").rstrip("/")
	token = settings.get_password("api_token")
	if not token:
		return {"success": False, "message": "API Token required"}

	headers = {"Authorization": f"Token {token}"}

	configs = frappe.get_all(
		"Kobo Form Configuration",
		filters={"enabled": 1},
		fields=["name", "kobo_form_asset_uid", "target_doctype", "match_field", "field_mappings"],
	)

	if not configs:
		return {"success": True, "message": "No enabled form configurations."}

	msg_parts = []
	for cfg in configs:
		config_doc = frappe.get_doc("Kobo Form Configuration", cfg.name)
		result = _sync_single_form(
			base_url=base_url,
			headers=headers,
			config=config_doc,
			triggered_by=triggered_by,
		)
		if result:
			msg_parts.append(f"{config_doc.form_name or config_doc.target_doctype}: {result.get('message', '')}")

	return {"success": True, "message": "; ".join(msg_parts)}


# ─── Core Sync ────────────────────────────────────────────────────────────────

def _sync_single_form(base_url, headers, config, triggered_by):
	"""Sync one Kobo form to its target DocType."""
	field_map = _build_field_map(config.field_mappings or [])
	if not field_map:
		return {"message": "No field mappings configured", "created": 0, "updated": 0, "failed": 0}

	submissions, raw_response = _fetch_kobo_submissions(base_url, headers, config.kobo_form_asset_uid)
	target_doctype = config.target_doctype
	match_field = config.match_field or "name"

	created, updated, failed = 0, 0, 0
	errors = []

	for sub in submissions:
		try:
			values = {}
			for kobo_key, target_field in field_map.items():
				val = _get_kobo_value(sub, kobo_key)
				if val is not None and val != "":
					values[target_field] = str(val).strip() if val else None

			match_val = values.get(match_field) or _get_kobo_value(sub, match_field)
			if not match_val:
				failed += 1
				errors.append(f"Submission missing match field '{match_field}'")
				continue

			# Title-case string values (skips raw coordinate fields)
			values = _title_case_values(values)
			# Resolve Link fields
			values = _resolve_link_fields(target_doctype, values)

			existing = frappe.db.get_value(target_doctype, {match_field: match_val}, "name")
			if existing:
				doc = frappe.get_doc(target_doctype, existing)
				_set_doc_values(doc, values)
				_post_process_farm_doc(doc, sub, target_doctype)
				doc.flags.ignore_permissions = True
				doc.save()
				updated += 1
			else:
				doc = frappe.new_doc(target_doctype)
				_set_doc_values(doc, values)
				_fill_required_fields(doc, target_doctype, match_field, match_val, values, sub)
				_post_process_farm_doc(doc, sub, target_doctype)
				doc.flags.ignore_permissions = True
				doc.insert()
				created += 1

			_attach_kobo_image_to_doc(doc, sub, headers, target_doctype)

		except Exception as e:
			failed += 1
			errors.append(str(e)[:200])

	sync_label = config.form_name or f"{target_doctype}"
	_log_sync(sync_label, triggered_by, created, updated, failed, errors, kobo_response=raw_response)

	return {
		"message": f"{created} created, {updated} updated, {failed} failed",
		"created": created,
		"updated": updated,
		"failed": failed,
	}


# ─── Field Mapping & Value Extraction ─────────────────────────────────────────

def _get_kobo_value(sub, kobo_key):
	"""
	Get value from Kobo submission.
	Tries exact key first, then any key ending with /kobo_key.
	e.g. kobo_key='first_name' matches 'farmer_registration/first_name'
	"""
	if not kobo_key:
		return None

	val = sub.get(kobo_key)
	if val is not None and val != "":
		return val

	if "/" not in kobo_key:
		for key, v in sub.items():
			if key.endswith("/" + kobo_key) and v is not None and v != "":
				return v

	return None


def _build_field_map(mappings):
	"""Build kobo_field -> target_field dict from child table."""
	out = {}
	for m in mappings:
		kobo   = (m.get("kobo_field_name") or "").strip()
		target = (m.get("target_field") or m.get("farmer_field") or m.get("farm_field") or "").strip()
		if kobo and target:
			out[kobo] = target
	return out


# ─── Value Normalization ──────────────────────────────────────────────────────

def _is_raw_coordinate_value(value):
	"""
	Detect GPS/boundary strings that must not be normalized.
	e.g. '-3.365 36.705 1454 4.9' or '-3.36 36.70;-3.37 36.71;...'
	"""
	if not value or not isinstance(value, str):
		return False
	v = value.strip()
	return ";" in v or (
		v.count(" ") >= 1
		and any(c in v for c in ["-", "."])
		and all(
			part.lstrip("-").replace(".", "").isdigit()
			for part in v.split(" ")[:2]
			if part
		)
	)


def _normalize_kobo_slug(value):
	"""
	Convert Kobo snake_case slugs to human-readable form.
	e.g. rainforest_alliance_standard -> Rainforest Alliance Standard
	     vanilla_farming              -> Vanilla Farming
	     seira-buikwe                 -> Seira-Buikwe
	"""
	if not value or not isinstance(value, str):
		return value
	return " ".join(word.capitalize() for word in value.replace("_", " ").split())


def _title_case(s):
	"""
	Capitalise first letter of each word (handles spaces and hyphens).
	e.g. seira-buikwe -> Seira-Buikwe
	"""
	if not s:
		return s
	if "-" in s:
		return "-".join(part.strip().capitalize() for part in s.replace("-", " ").split())
	return " ".join(part.strip().capitalize() for part in s.split())


def _title_case_values(values):
	"""
	Apply title-case to all string values.
	Skips coordinate/boundary fields — they must stay raw.
	"""
	out = {}
	for k, v in values.items():
		if k in RAW_VALUE_FIELDS or _is_raw_coordinate_value(str(v) if v else ""):
			out[k] = v  # leave raw — do not touch
		elif v is not None and isinstance(v, str) and v.strip():
			out[k] = _title_case(v)
		else:
			out[k] = v
	return out


def _normalize_value_for_field(meta, fieldname, value):
	"""
	Normalize a single value to match its DocType field definition.

	- Raw/coordinate fields: returned as-is (no processing)
	- Select: case-insensitive match after Kobo slug conversion
	          e.g. 'rainforest_alliance_standard' -> 'Rainforest Alliance Standard'
	- Link:   tries multiple candidate forms against DB
	- Data/Text: title-case
	"""
	if value is None or (isinstance(value, str) and not value.strip()):
		return value

	value = str(value).strip()

	# Never normalize GPS/boundary coordinate strings
	if fieldname in RAW_VALUE_FIELDS or _is_raw_coordinate_value(value):
		return value

	df = meta.get_field(fieldname)
	if not df:
		return _normalize_kobo_slug(value)

	# ── SELECT ────────────────────────────────────────────────────────────────
	if df.fieldtype == "Select" and getattr(df, "options", None):
		options = [o.strip() for o in (df.options or "").split("\n") if o.strip()]

		# 1. Exact match
		if value in options:
			return value

		# 2. Case-insensitive exact match
		value_lower = value.lower()
		for opt in options:
			if opt.lower() == value_lower:
				return opt

		# 3. Kobo slug -> human form, case-insensitive
		#    e.g. rainforest_alliance_standard -> Rainforest Alliance Standard
		human = _normalize_kobo_slug(value)
		human_lower = human.lower()
		for opt in options:
			if opt.lower() == human_lower:
				return opt

		# 4. Underscore-replaced, no capitalisation
		slug_lower = value.replace("_", " ").lower()
		for opt in options:
			if opt.lower() == slug_lower:
				return opt

		# Nothing matched — log clearly so the admin can fix the mapping
		frappe.log_error(
			f"Select field '{fieldname}' has no option matching '{value}' "
			f"(tried human form: '{human}'). Available options: {options}",
			"Kobo Select Mismatch"
		)
		return value

	# ── LINK ─────────────────────────────────────────────────────────────────
	if df.fieldtype == "Link":
		for candidate in [value, _normalize_kobo_slug(value), _title_case(value)]:
			if candidate and frappe.db.exists(df.options, candidate):
				return candidate
		return _normalize_kobo_slug(value)  # best guess, _resolve_link_fields will refine

	# ── DATA / TEXT ───────────────────────────────────────────────────────────
	if df.fieldtype in ("Data", "Text", "Small Text", "Long Text"):
		return _title_case(value)

	return value


def _set_doc_values(doc, values):
	"""Set values on doc for fields that exist, normalizing each value."""
	meta = doc.meta
	for k, v in values.items():
		if hasattr(doc, k):
			v = _normalize_value_for_field(meta, k, v)
			setattr(doc, k, v)


def _resolve_link_fields(target_doctype, values):
	"""Try to resolve Link field values against existing DB records."""
	meta = frappe.get_meta(target_doctype)
	for fieldname, value in list(values.items()):
		if not value:
			continue
		df = meta.get_field(fieldname)
		if df and df.fieldtype == "Link" and df.options:
			existing = frappe.db.get_value(df.options, {"name": value}, "name")
			if not existing:
				link_meta = frappe.get_meta(df.options)
				for link_df in link_meta.get("fields", []):
					if link_df.fieldtype in ("Data", "Link") and link_df.fieldname != "name":
						existing = frappe.db.get_value(df.options, {link_df.fieldname: value}, "name")
						if existing:
							break
			if existing:
				values[fieldname] = existing
	return values


def _fill_required_fields(doc, target_doctype, match_field, match_val, values, sub):
	"""Fill required fields when creating a new doc."""
	meta = frappe.get_meta(target_doctype)
	for df in meta.get("fields", []):
		if df.reqd and not doc.get(df.fieldname):
			if df.fieldname == match_field:
				doc.set(df.fieldname, match_val)
			elif values.get(df.fieldname):
				doc.set(df.fieldname, values[df.fieldname])
			elif df.fieldtype == "Link" and df.options == "Farmer":
				pass  # must be mapped by user
			elif df.fieldname == "farm_id" and target_doctype == "Farm":
				doc.set("farm_id", values.get("farm_id") or sub.get("_uuid", "")[:50] or f"KOBO-{match_val}")
			elif df.fieldname == "farm_name" and target_doctype == "Farm":
				doc.set("farm_name", values.get("farm_name") or match_val or "Unnamed Farm")


# ─── Farm-Specific Post-Processing ───────────────────────────────────────────

def _post_process_farm_doc(doc, sub, target_doctype):
	"""
	Farm-specific post-processing after normal field mapping.
	Reads directly from the raw Kobo submission (sub) to avoid normalization issues.

	Writes:
	  doc.latitude   <- first value of farm_gps  (e.g. -3.3656872)
	  doc.longitude  <- second value of farm_gps (e.g.  36.7059021)
	  doc.landmark   <- farm_boundary string, stored RAW exactly as Kobo sends it
	"""
	if target_doctype != "Farm":
		return

	# ── farm_gps → latitude + longitude ──────────────────────────────────────
	# Kobo format: "-3.3656872 36.7059021 1454.5 4.942"
	#               [0]=lat    [1]=lng    [2]=alt [3]=accuracy (ignore 2 & 3)
	gps_raw = (
		sub.get("farmer_registration/farm_gps")
		or sub.get("farm_gps")
		or ""
	)
	if gps_raw:
		parts = str(gps_raw).strip().split()
		if len(parts) >= 2:
			try:
				lat = float(parts[0])
				lng = float(parts[1])
				if hasattr(doc, "latitude"):
					doc.latitude = lat
				if hasattr(doc, "longitude"):
					doc.longitude = lng
				frappe.logger().info(
					f"[Kobo] Farm '{doc.name}' → latitude={lat}, longitude={lng}"
				)
			except ValueError:
				frappe.log_error(
					f"Cannot parse farm_gps '{gps_raw}' for Farm '{doc.name}'",
					"Kobo GPS Parse Error"
				)

	# ── farm_boundary → landmark (RAW — no formatting whatsoever) ────────────
	# Kobo format: "-3.3658215 36.7059214 1454.9 2.7;-3.3658175 36.7059043 ..."
	# Store exactly as-is so the JS Leaflet polygon parser works correctly.
	boundary_raw = (
		sub.get("farmer_registration/farm_boundary")
		or sub.get("farm_boundary")
		or ""
	)
	if boundary_raw and hasattr(doc, "landmark"):
		doc.landmark = str(boundary_raw).strip()
		frappe.logger().info(
			f"[Kobo] Farm '{doc.name}' → landmark set ({len(doc.landmark)} chars)"
		)


# ─── Image Attachment ─────────────────────────────────────────────────────────

def _attach_kobo_image_to_doc(doc, sub, headers, target_doctype):
	"""
	Download a Kobo attachment and save it to the correct image field on the doc.

	Farmer -> contract_image  (matched by xpath: photo_farmer, farmer_photo, photo)
	Farm   -> photo           (matched by xpath: photo_farm, farm_photo, photo)

	Add more doctypes to DOCTYPE_IMAGE_CONFIG at the top of this file.
	"""
	config = DOCTYPE_IMAGE_CONFIG.get(target_doctype)
	if not config:
		return

	image_field, xpath_keywords = config

	if not hasattr(doc, image_field):
		return

	attachments = sub.get("_attachments") or []
	if not attachments:
		return

	# ── Step 1: Find the right attachment by question_xpath ───────────────────
	image_att = None

	# Try each keyword in priority order (most specific first)
	for keyword in xpath_keywords:
		for att in attachments:
			if att.get("is_deleted"):
				continue
			xpath = (att.get("question_xpath") or "").lower()
			if keyword.lower() in xpath:
				image_att = att
				break
		if image_att:
			break

	# Fallback: first non-deleted image attachment
	if not image_att:
		for att in attachments:
			if att.get("is_deleted"):
				continue
			if "image" in (att.get("mimetype") or "").lower():
				image_att = att
				break

	if not image_att:
		return

	# ── Step 2: Download ──────────────────────────────────────────────────────
	download_url = image_att.get("download_url")
	if not download_url:
		return

	try:
		import requests
		resp = requests.get(download_url, headers=headers, timeout=30)
		resp.raise_for_status()
		content = resp.content
	except Exception as e:
		frappe.log_error(
			f"Failed to download Kobo image for {target_doctype} '{doc.name}': {e}",
			"Kobo Image Download"
		)
		return

	# ── Step 3: Clean filename ────────────────────────────────────────────────
	fname = image_att.get("media_file_basename") or image_att.get("filename") or "kobo_image.jpg"
	if "/" in fname:
		fname = fname.split("/")[-1]
	if not fname.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
		fname += ".jpg"

	# ── Step 4: Save and attach ───────────────────────────────────────────────
	try:
		from frappe.utils.file_manager import save_file
		file_doc = save_file(
			fname=fname,
			content=content,
			dt=target_doctype,
			dn=doc.name,
			folder="Home/Attachments",
			is_private=0,
			df=image_field,
		)
		if file_doc and file_doc.file_url:
			setattr(doc, image_field, file_doc.file_url)
			doc.flags.ignore_permissions = True
			doc.save()
			frappe.logger().info(
				f"[Kobo] Attached image to {target_doctype} '{doc.name}' → field '{image_field}'"
			)
	except Exception as e:
		frappe.log_error(
			f"Failed to save Kobo image for {target_doctype} '{doc.name}' field '{image_field}': {e}",
			"Kobo Image Save"
		)


# ─── Kobo API ─────────────────────────────────────────────────────────────────

def _fetch_kobo_submissions(base_url, headers, asset_uid):
	"""Fetch submissions from Kobo API v2. Returns (submissions_list, raw_response_text)."""
	url = f"{base_url}/api/v2/assets/{asset_uid}/data/"
	try:
		import requests
		resp = requests.get(url, headers=headers, timeout=60)
		raw_response = resp.text
		resp.raise_for_status()
		data = resp.json()
		if isinstance(data, dict) and "results" in data:
			return data["results"], raw_response
		if isinstance(data, list):
			return data, raw_response
		return [], raw_response
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Kobo API Error")
		raise frappe.ValidationError(_("Kobo API error: {0}").format(str(e)))


# ─── Sync Logging ─────────────────────────────────────────────────────────────

def _log_sync(sync_type, triggered_by, created, updated, failed, errors, kobo_response=None):
	from frappe.utils import now
	status = "Success" if failed == 0 else ("Failed" if created == 0 and updated == 0 else "Partial")
	response_stored = (
		(kobo_response[:100000] + "\n... (truncated)")
		if kobo_response and len(kobo_response) > 100000
		else (kobo_response or "")
	)
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
		kobo_response=response_stored,
	)
	log.insert(ignore_permissions=True)
	frappe.db.commit()