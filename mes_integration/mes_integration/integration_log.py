import frappe


def create_mes_log(
	direction,
	event,
	status="Success",
	reference_doctype=None,
	reference_name=None,
	source=None,
	user=None,
	request_url=None,
	request_payload=None,
	response_payload=None,
	error_message=None,
	trace_id=None,
	processed=None,
	http_status_code=None,
):
	if not frappe.db.exists("DocType", "MES Integration Log"):
		return None

	try:
		log = frappe.get_doc(
			{
				"doctype": "MES Integration Log",
				"direction": direction,
				"event": event,
				"status": status,
				"source": source,
				"user": user or get_current_user(),
				"reference_doctype": reference_doctype,
				"reference_name": reference_name,
				"request_url": request_url,
				"request_payload": as_json(request_payload),
				"response_payload": as_json(response_payload),
				"error_message": error_message,
				"trace_id": trace_id,
				"processed": processed,
				"http_status_code": http_status_code,
			}
		)
		log.insert(ignore_permissions=True)
		return log
	except Exception:
		frappe.log_error(title="Failed to create MES Integration Log", message=frappe.get_traceback())
		return None


def update_mes_log(log, **values):
	if not log:
		return

	try:
		updates = {}
		for fieldname, value in values.items():
			if fieldname in ("request_payload", "response_payload"):
				updates[fieldname] = as_json(value)
			else:
				updates[fieldname] = value

		frappe.db.set_value("MES Integration Log", log.name, updates, update_modified=True)
	except Exception:
		frappe.log_error(title="Failed to update MES Integration Log", message=frappe.get_traceback())


def log_inbound_material_request(doc, method=None):
	log_inbound_document(doc, method)


def log_inbound_stock_entry(doc, method=None):
	log_inbound_document(doc, method)


def log_inbound_document(doc, method=None):
	if doc.doctype not in ("Material Request", "Stock Entry"):
		return

	event = {
		"after_insert": "Document Created",
		"on_submit": "Document Submitted",
	}.get(method, method or "Document Event")

	create_mes_log(
		direction="Inbound",
		event=event,
		status="Success",
		reference_doctype=doc.doctype,
		reference_name=doc.name,
		source=get_request_source(),
		request_url=get_request_url(),
		request_payload=doc.as_dict(no_nulls=True),
		response_payload={"docstatus": doc.docstatus},
	)


def get_request_source():
	if is_mes_api_user():
		return "MES"

	if not getattr(frappe.local, "request", None):
		return "Background"

	path = getattr(frappe.request, "path", "") or ""
	if path.startswith("/api/"):
		return "External API"

	return "Desk"


def is_mes_api_user():
	return is_api_key_request()


def is_api_key_request():
	if not getattr(frappe.local, "request", None):
		return False

	authorization = frappe.get_request_header("Authorization") or ""
	return authorization.lower().startswith("token ")


def get_current_user():
	user = getattr(frappe.session, "user", None)

	if not user:
		return None

	return user


def get_request_url():
	if not getattr(frappe.local, "request", None):
		return None

	return getattr(frappe.request, "url", None)


def as_json(value):
	if value is None or isinstance(value, str):
		return value

	return frappe.as_json(value, indent=2)
