// Copyright (c) 2026, Mania and contributors
// For license information, please see license.txt

frappe.ui.form.on("Farmer", {
	refresh(frm) {
		// Auto-fetch district, state, and country when village is selected
		if (frm.doc.village) {
			frm.trigger("village");
		}
	},
	
	village(frm) {
		if (frm.doc.village) {
			frappe.db.get_doc("Village", frm.doc.village)
				.then(doc => {
					if (doc.district) {
						frm.set_value("district", doc.district);
					}
					if (doc.state) {
						frm.set_value("state", doc.state);
					}
					if (doc.country) {
						frm.set_value("country", doc.country);
					}
				});
		} else {
			frm.set_value("district", "");
			frm.set_value("state", "");
			frm.set_value("country", "");
		}
	}
});

