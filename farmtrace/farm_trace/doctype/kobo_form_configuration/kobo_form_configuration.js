// Copyright (c) 2026, Mania and contributors
// For license information, please see license.txt

frappe.ui.form.on("Kobo Form Configuration", {
	refresh: function (frm) {
		if (frm.doc.enabled && frm.doc.kobo_form_asset_uid && frm.doc.target_doctype) {
			frm.add_custom_button(__("Sync Now"), function () {
				frappe.call({
					method: "farmtrace.farm_trace.api.kobo_sync.sync_form",
					args: { form_name: frm.doc.name },
					freeze: true,
					callback: function (r) {
						if (!r.exc && r.message) {
							frappe.msgprint({
								title: __("Sync Complete"),
								message: r.message,
								indicator: "green",
							});
							frm.reload_doc();
						}
					},
				});
			}).addClass("btn-primary");
		}
	},
	target_doctype: function (frm) {
		if (frm.doc.target_doctype) {
			frappe.model.with_doctype(frm.doc.target_doctype, function () {
				const fields = frappe.meta.get_docfield(frm.doc.target_doctype);
				// Could optionally populate match_field options from target doctype fields
			});
		}
	},
});
