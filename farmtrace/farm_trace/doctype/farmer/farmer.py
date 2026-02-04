# Copyright (c) 2026, Mania and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class Farmer(Document):
	def before_save(self):
		# Set full_name from first_name + middle_name + last_name only if full_name doesn't exist
		if not self.get("full_name"):
			parts = [
				self.get("first_name"),
				self.get("middle_name"),
				self.get("last_name"),
			]
			full_name = " ".join(p for p in parts if p)
			if full_name:
				self.full_name = full_name.strip()



