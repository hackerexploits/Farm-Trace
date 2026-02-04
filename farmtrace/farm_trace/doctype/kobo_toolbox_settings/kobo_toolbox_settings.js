// Copyright (c) 2026, Mania and contributors
// For license information, please see license.txt

frappe.ui.form.on("Kobo Toolbox Settings", {
	refresh: function (frm) {
		if (frm.doc.enable_sync) {
			frm.add_custom_button(__("Sync Now"), function () {
				frappe.call({
					method: "farmtrace.farm_trace.api.kobo_sync.sync_now",
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
});
