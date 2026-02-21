// // Copyright (c) 2026, Mania and contributors
// // For license information, please see license.txt

// frappe.ui.form.on("Kobo Toolbox Settings", {
// 	refresh: function (frm) {
// 		if (frm.doc.enable_sync) {
// 			frm.add_custom_button(__("Sync All Forms"), function () {
// 				frappe.call({
// 					method: "farmtrace.farm_trace.api.kobo_sync.sync_now",
// 					freeze: true,
// 					callback: function (r) {
// 						if (!r.exc && r.message) {
// 							frappe.msgprint({
// 								title: __("Sync Complete"),
// 								message: r.message,
// 								indicator: "green",
// 							});
// 							frm.reload_doc();
// 						}
// 					},
// 				});
// 			}).addClass("btn-primary");
// 		}
// 	},
// });

// Copyright (c) 2026, Mania and contributors

frappe.ui.form.on("Kobo Toolbox Settings", {
	refresh: function (frm) {

		// ---------------------------
		// EXISTING SYNC BUTTON
		// ---------------------------
		if (frm.doc.enable_sync) {
			frm.add_custom_button(__("Sync All Forms"), function () {
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

		// ---------------------------
		// GENERATE BARCODE BUTTON
		// ---------------------------
		frm.add_custom_button(__("Generate Barcodes"), function () {

			let d = new frappe.ui.Dialog({
				title: __("Generate EAN Barcodes"),
				fields: [
					{
						label: "Number of Barcodes",
						fieldname: "qty",
						fieldtype: "Int",
						reqd: 1,
						default: 1
					}
				],
				primary_action_label: __("Generate"),
				primary_action(values) {

					if (!values.qty || values.qty <= 0) {
						frappe.msgprint(__("Enter a valid quantity"));
						return;
					}

					d.hide();

					frappe.call({
						method: "farmtrace.farm_trace.api.barcode.generate_barcodes",
						args: {
							qty: values.qty
						},
						freeze: true,
						freeze_message: __("Generating barcodes..."),
						callback: function (r) {
							if (!r.exc) {
								frappe.msgprint({
									title: __("Success"),
									message: __(
										"{0} barcodes created successfully",
										[r.message || 0]
									),
									indicator: "green",
								});
							}
						}
					});
				}
			});

			d.show();
		}).addClass("btn-success");
	},
});