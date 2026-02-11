// Copyright (c) 2026, Mania and contributors
// For license information, please see license.txt

frappe.ui.form.on("Farmer", {

	refresh(frm) {

		// Render age if already saved
		if (frm.doc.dob) {
			calculate_age(frm);
		}

		// Auto-fetch district, state, and country when village is selected
		if (frm.doc.village) {
			frm.trigger("village");
		}
		calculate_total_hectares(frm);
	},

	village(frm) {
		if (frm.doc.village) {
			frappe.db.get_doc("Village", frm.doc.village)
				.then(doc => {
					frm.set_value("district", doc.district || "");
					frm.set_value("state", doc.state || "");
					frm.set_value("country", doc.country || "");
				});
		} else {
			frm.set_value("district", "");
			frm.set_value("state", "");
			frm.set_value("country", "");
		}
	},

	// When DOB changes
	dob(frm) {
		calculate_age(frm);
	},

	validate(frm) {
		calculate_age(frm);
	}
});


function calculate_age(frm) {

	if (!frm.doc.dob) {
		frm.set_value("age", null);
		$(frm.fields_dict['full_age'].wrapper).html('');
		return;
	}

	let today = new Date();
	let birthDate = new Date(frm.doc.dob);

	// Prevent future date
	if (today < birthDate) {
		frappe.msgprint(__('Please select a valid Date of Birth'));
		frm.set_value('dob', '');
		$(frm.fields_dict['full_age'].wrapper).html('');
		return;
	}

	let years = today.getFullYear() - birthDate.getFullYear();
	let months = today.getMonth() - birthDate.getMonth();
	let days = today.getDate() - birthDate.getDate();

	if (days < 0) {
		months -= 1;
		let lastMonth = new Date(today.getFullYear(), today.getMonth(), 0);
		days += lastMonth.getDate();
	}

	if (months < 0) {
		years -= 1;
		months += 12;
	}

	// Set integer age
	frm.set_value("age", years);

	// Proper HTML rendering (THIS is what was missing)
	$(frm.fields_dict['full_age'].wrapper).html(
		`<div style="font-weight:600;">
			${years} years, ${months} months, ${days} days
		</div>`
	);
}
function calculate_total_hectares(frm) {

	if (!frm.doc.name) return;

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Farm",  // <-- confirm correct doctype name
			fields: ["sum(hectares) as total"],
			filters: {
				farmer: frm.doc.name
			},
			limit_page_length: 1
		},
		callback: function(r) {

			let total = 0;

			if (r.message && r.message.length) {
				total = r.message[0].total || 0;
			}

			$(frm.fields_dict['total_farmhac'].wrapper).html(
				`<div style="font-weight:600; font-size:14px;">
					Total Hectares: 
					<span style="color:#2E7D32">${total}</span>
				</div>`
			);
		}
	});
}
