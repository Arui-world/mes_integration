import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


MATERIAL_REQUEST_EXTRA_TYPES = (
	"Material Transfer for Manufacture",
	"Injection Molding Issuance",
)
STOCK_ENTRY_EXTRA_PURPOSES = ("Injection Molding Issuance",)


def execute():
	append_select_options("Material Request", "material_request_type", MATERIAL_REQUEST_EXTRA_TYPES)
	append_select_options("Stock Entry", "purpose", STOCK_ENTRY_EXTRA_PURPOSES)
	append_select_options("Stock Entry Type", "purpose", STOCK_ENTRY_EXTRA_PURPOSES)
	ensure_stock_entry_type("Injection Molding Issuance")

	for doctype in ("Material Request", "Stock Entry", "Stock Entry Type"):
		frappe.clear_cache(doctype=doctype)


def append_select_options(doctype, fieldname, extra_options):
	options = get_select_options(doctype, fieldname)
	changed = False

	for option in extra_options:
		if option not in options:
			options.append(option)
			changed = True

	if changed:
		make_property_setter(
			doctype,
			fieldname,
			"options",
			"\n".join(options),
			"Text",
			validate_fields_for_doctype=False,
		)


def get_select_options(doctype, fieldname):
	property_setter_value = frappe.db.get_value(
		"Property Setter",
		{"doc_type": doctype, "field_name": fieldname, "property": "options"},
		"value",
	)
	if property_setter_value:
		return split_options(property_setter_value)

	field = frappe.get_meta(doctype).get_field(fieldname)
	return split_options(field.options if field else "")


def split_options(options):
	return [option.strip() for option in (options or "").split("\n") if option.strip()]


def ensure_stock_entry_type(name):
	if frappe.db.exists("Stock Entry Type", name):
		return

	frappe.get_doc(
		{
			"doctype": "Stock Entry Type",
			"name": name,
			"purpose": name,
		}
	).insert(ignore_permissions=True)
