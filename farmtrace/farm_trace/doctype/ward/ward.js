// Copyright (c) 2026, Mania and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ward", {
	refresh(frm) {
		// Auto-fetch state and country when district is selected
		if (frm.doc.district) {
			frm.trigger("district");
		}
	},
	
	district(frm) {
		if (frm.doc.district) {
			frappe.db.get_doc("District", frm.doc.district)
				.then(doc => {
					if (doc.state) {
						frm.set_value("state", doc.state);
					}
					if (doc.country) {
						frm.set_value("country", doc.country);
					}
				});
		} else {
			frm.set_value("state", "");
			frm.set_value("country", "");
		}
	}
});
