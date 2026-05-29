import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


REMOVE_PURPOSES = ("Injection Molding Issuance",)


def execute():
	remove_select_options("Stock Entry", "purpose", REMOVE_PURPOSES)
	remove_select_options("Stock Entry Type", "purpose", REMOVE_PURPOSES)

	if frappe.db.exists("Stock Entry Type", "Injection Molding Issuance"):
		frappe.delete_doc("Stock Entry Type", "Injection Molding Issuance", ignore_permissions=True, force=True)

	for doctype in ("Stock Entry", "Stock Entry Type"):
		frappe.clear_cache(doctype=doctype)


def remove_select_options(doctype, fieldname, remove_options):
	options = get_select_options(doctype, fieldname)
	new_options = [option for option in options if option not in remove_options]

	if new_options != options:
		make_property_setter(
			doctype,
			fieldname,
			"options",
			"\n".join(new_options),
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
