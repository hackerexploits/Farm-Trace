frappe.ui.form.on("Purchase Receipt", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0) {
			return;
		}

		frm.add_custom_button(
			__("Farm Purchase Intake"),
			() => open_farm_purchase_intake_dialog(frm),
			__("Get Items From")
		);
	},
});

function open_farm_purchase_intake_dialog(frm) {
	new frappe.ui.form.MultiSelectDialog({
		doctype: "Farm Purchase Intake",
		target: frm,
		setters: [
			{
				fieldtype: "Link",
				fieldname: "farmer",
				options: "Farmer",
				label: __("Farmer"),
			},
			{
				fieldtype: "Data",
				fieldname: "farmer_name",
				label: __("Farmer Name"),
				read_only: 1,
				hidden: 1,
			},
		],
		data_fields: [
			{
				fieldtype: "Date",
				fieldname: "from_date",
				label: __("From Date"),
			},
			{
				fieldtype: "Date",
				fieldname: "to_date",
				label: __("To Date"),
			},
		],
		add_filters_group: 1,
		get_query() {
			const filters = {
				docstatus: 1,
				receipt_created: 0,
				purchase_receipt: ["is", "not set"],
			};

			const from_date = this.dialog?.fields_dict?.from_date?.get_value();
			const to_date = this.dialog?.fields_dict?.to_date?.get_value();

			if (from_date && to_date) {
				filters.purchase_date = ["between", [from_date, to_date]];
			} else if (from_date) {
				filters.purchase_date = [">=", from_date];
			} else if (to_date) {
				filters.purchase_date = ["<=", to_date];
			}

			return { filters };
		},
		action(selections) {
			if (!selections.length) {
				frappe.msgprint(__("Please select at least one Farm Purchase Intake"));
				return;
			}

			frappe.call({
				method: "farmtrace.controller.purchase_receipt.get_items_from_farm_intake",
				args: {
					intake_names: selections,
				},
				freeze: true,
				callback(r) {
					if (!r.message) {
						return;
					}

					const data = r.message;
					frm.set_value("company", data.company);
					frm.set_value("supplier", data.supplier);
					frm.set_value("posting_date", data.posting_date);
					if (data.currency) {
						frm.set_value("currency", data.currency);
					}

					frm.clear_table("items");
					(data.items || []).forEach((d) => {
						const row = frm.add_child("items");
						Object.assign(row, d);
					});

					frm.refresh_field("items");
				},
			});

			this.dialog.hide();
		},
	});
}
