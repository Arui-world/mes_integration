import frappe


CLIENT_SCRIPT_NAME = "物料移动获取物料需求中的物料移动单号"


def execute():
    if not frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
        return

    script = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
    script.script = get_script()
    script.save(ignore_permissions=True)


def get_script():
    return r'''const MES_RECEIPT_STOCK_ENTRY_TYPES = [
    "Semi Finished Goods Receipt",
    "Finished Goods Receipt"
];

frappe.ui.form.on("Stock Entry", {
    refresh(frm) {
        update_custom_stock_entry_no(frm);
    },

    validate(frm) {
        update_custom_stock_entry_no(frm);
    }
});

function update_custom_stock_entry_no(frm) {
    if (MES_RECEIPT_STOCK_ENTRY_TYPES.includes(frm.doc.stock_entry_type)) {
        return;
    }

    if (!frm.doc.items || frm.doc.items.length === 0) {
        return;
    }

    let first_item = frm.doc.items[0];
    let mr_name = first_item.material_request;

    if (mr_name) {
        frappe.db.get_value(
            "Material Request",
            mr_name,
            "custom_stock_entry_no"
        ).then(r => {
            if (r && r.message) {
                frm.set_value("custom_stock_entry_no", r.message.custom_stock_entry_no || "");
            } else {
                frm.set_value("custom_stock_entry_no", "");
            }
        });
    } else {
        frm.set_value("custom_stock_entry_no", "");
    }
}
'''
