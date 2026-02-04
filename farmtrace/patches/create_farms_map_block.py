# Copyright (c) 2026, Mania and contributors
# For license information, please see license.txt

import frappe


def execute():
	"""Create Farms Map Custom HTML Block and add to workspace (for existing installations)."""
	from farmtrace.install import create_farms_map_custom_block, update_workspace_with_farms_map

	create_farms_map_custom_block()
	update_workspace_with_farms_map()
