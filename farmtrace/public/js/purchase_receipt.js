frappe.ui.form.on('Purchase Receipt', {

    refresh(frm) {

        if (frm.doc.docstatus !== 0) return;

        frm.add_custom_button(
            "Farm Purchase Intake",
            () => {

                new frappe.ui.form.MultiSelectDialog({
                    doctype: "Farm Purchase Intake",
                    target: frm,

                    setters: {
                        farmer: null,
                        purchase_date: null
                    },

                    add_filters_group: 1,

                    date_field: "purchase_date",

                    get_query() {
                        return {
                            filters: {
                                docstatus: 1
                            }
                        };
                    },

                    action(selections) {

                        if (!selections.length) {
                            frappe.msgprint("Please select at least one Intake");
                            return;
                        }

                        frappe.call({
                            method: "farmtrace.controller.purchase_receipt.get_items_from_farm_intake",
                            args: {
                                intake_names: selections
                            },
                            callback(r) {

                                if (!r.message) return;

                                frm.set_value("supplier", r.message.supplier);
                                frm.set_value("posting_date", r.message.posting_date);

                                frm.clear_table("items");

                                r.message.items.forEach(d => {
                                    let row = frm.add_child("items");
                                    Object.assign(row, d);
                                });

                                frm.refresh_field("items");
                            }
                        });

                        this.dialog.hide();
                    }
                });

            },
            "Get Items From"
        );
    }
});
