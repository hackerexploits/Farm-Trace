// Copyright (c) 2026, Mania and contributors
// For license information, please see license.txt

frappe.ui.form.on("Farm Purchase Intake", {
	refresh(frm) {
		if (frm.doc.purchase_date) {
			set_season_from_purchase_date(frm);
		}
		calculate_totals(frm);
	},

	purchase_date(frm) {
		set_season_from_purchase_date(frm);
	},

	validate(frm) {
		set_season_from_purchase_date(frm);
	},
});

frappe.ui.form.on("Farm Purchase Intake Item", {
	quantity(frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},
	unit_price(frm, cdt, cdn) {
		calculate_row_amount(frm, cdt, cdn);
	},
	amount(frm) {
		calculate_totals(frm);
	},
	items_remove(frm) {
		calculate_totals(frm);
	},
});

function set_season_from_purchase_date(frm) {
	if (!frm.doc.purchase_date) {
		frm.set_value("season", "");
		return;
	}

	const year = frappe.datetime.str_to_obj(frm.doc.purchase_date).getFullYear();
	frm.set_value("season", String(year));
}

function calculate_row_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const amount = flt(row.quantity) * flt(row.unit_price);
	frappe.model.set_value(cdt, cdn, "amount", amount);
}

function calculate_totals(frm) {
	let total_qty = 0;
	let total_amount = 0;

	(frm.doc.items || []).forEach(row => {
		total_qty += flt(row.quantity);
		total_amount += flt(row.amount);
	});

	frm.set_value("total_qty", total_qty);
	frm.set_value("total_amount", total_amount);
}