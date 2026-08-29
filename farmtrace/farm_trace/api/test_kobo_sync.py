# Copyright (c) 2026, Mania and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from farmtrace.farm_trace.api.kobo_sync import (
	_get_kobo_repeat_group,
	_get_kobo_value,
	_get_or_create_farmer,
	_get_repeat_row_value,
	_split_field_mappings,
)


class TestKoboSync(FrappeTestCase):
	def test_get_kobo_value_matches_nested_field_paths(self):
		sub = {
			"crop_procurement/payment_method": "mobile",
			"crop_procurement/mobile_payment/mobile_provider": "yass",
			"crop_procurement/mobile_payment/mobile_number": "0712150091",
			"crop_procurement/mobile_payment/mobile_name": "John Doe",
		}
		self.assertEqual(_get_kobo_value(sub, "payment_method"), "mobile")
		self.assertEqual(_get_kobo_value(sub, "mobile_payment/mobile_provider"), "yass")
		self.assertEqual(_get_kobo_value(sub, "mobile_payment/mobile_number"), "0712150091")
		self.assertEqual(_get_kobo_value(sub, "mobile_payment/mobile_name"), "John Doe")

	def test_split_field_mappings(self):
		mappings = [
			{"kobo_field_name": "farmer", "target_field": "farmer"},
			{
				"kobo_repeat_group": "crop_procurement/bag",
				"target_child_table": "items",
				"kobo_field_name": "barcode",
				"target_field": "barcode",
			},
			{
				"kobo_repeat_group": "crop_procurement/bag",
				"target_child_table": "items",
				"kobo_field_name": "bag_weight",
				"target_field": "quantity",
			},
		]
		parent_map, child_maps = _split_field_mappings(
			mappings, target_doctype="Farm Purchase Intake"
		)
		self.assertEqual(parent_map, {"farmer": "farmer"})
		self.assertEqual(
			child_maps[("crop_procurement/bag", "items")],
			{"barcode": "barcode", "bag_weight": "quantity"},
		)

	def test_split_field_mappings_infers_items_child_table(self):
		mappings = [
			{
				"kobo_repeat_group": "crop_procurement/bag",
				"kobo_field_name": "barcode",
				"target_field": "barcode",
			},
			{
				"kobo_repeat_group": "crop_procurement/bag",
				"kobo_field_name": "bag_weight",
				"target_field": "quantity",
			},
		]
		_, child_maps = _split_field_mappings(
			mappings, target_doctype="Farm Purchase Intake"
		)
		self.assertEqual(
			child_maps[("crop_procurement/bag", "items")],
			{"barcode": "barcode", "bag_weight": "quantity"},
		)

	def test_parent_mapping_ignores_stray_target_child_table(self):
		mappings = [
			{
				"kobo_field_name": "_submitted_by",
				"target_field": "submitted_byuser",
				"target_child_table": "items",
			},
		]
		parent_map, child_maps = _split_field_mappings(
			mappings, target_doctype="Farm Purchase Intake"
		)
		self.assertEqual(parent_map, {"_submitted_by": "submitted_byuser"})
		self.assertEqual(child_maps, {})

	def test_get_kobo_repeat_group_from_array(self):
		sub = {
			"crop_procurement/bag": [
				{
					"crop_procurement/bag/barcode": "111",
					"crop_procurement/bag/bag_weight": "2.5",
				},
				{
					"crop_procurement/bag/barcode": "222",
					"crop_procurement/bag/bag_weight": "3.0",
				},
			]
		}
		rows = _get_kobo_repeat_group(sub, "crop_procurement/bag")
		self.assertEqual(len(rows), 2)
		self.assertEqual(rows[0]["crop_procurement/bag/barcode"], "111")

	def test_get_kobo_repeat_group_from_comma_separated(self):
		sub = {"crop_procurement/bag": "111,222,333"}
		field_map = {"barcode": "barcode"}
		rows = _get_kobo_repeat_group(sub, "crop_procurement/bag", field_map)
		self.assertEqual(len(rows), 3)
		self.assertEqual(rows[0]["barcode"], "111")

	def test_get_repeat_row_value(self):
		row = {
			"crop_procurement/bag/barcode": "1970844076211",
			"crop_procurement/bag/Barcode": "1970844076211",
			"crop_procurement/bag/bag_weight": "0.7",
		}
		self.assertEqual(
			_get_repeat_row_value(row, "barcode", "crop_procurement/bag"),
			"1970844076211",
		)
		self.assertEqual(
			_get_repeat_row_value(row, "bag_weight", "crop_procurement/bag"),
			"0.7",
		)

	def test_get_or_create_farmer_creates_stub(self):
		farmer_ref = "TEST-KOBO-FARMER-001"
		if frappe.db.exists("Farmer", farmer_ref):
			frappe.delete_doc("Farmer", farmer_ref, force=1)

		name = _get_or_create_farmer(farmer_ref)
		self.assertEqual(name, farmer_ref)
		self.assertTrue(frappe.db.exists("Farmer", farmer_ref))

		# Second call should reuse existing farmer
		self.assertEqual(_get_or_create_farmer(farmer_ref), farmer_ref)
