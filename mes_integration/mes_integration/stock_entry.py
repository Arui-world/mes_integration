import json

from requests.exceptions import RequestException

import frappe
from frappe.utils import flt, get_request_session, getdate, now

from mes_integration.mes_integration.integration_log import (
    create_mes_log,
    is_mes_api_user,
    update_mes_log,
)


@frappe.whitelist()
def push_to_mes(stock_entry_name):
    """
    将已提交的 Stock Entry 发料结果回写到 MES。
    """
    stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)

    if stock_entry.docstatus != 1:
        frappe.throw(frappe._("库存移动单必须已提交才能推送到 MES"))

    if stock_entry.get("custom_mes_status") == "Pushed":
        message = frappe._("此库存移动单已推送至 MES，无需重复推送")
        create_mes_log(
            direction="Outbound",
            event="Stock Entry Issue Confirm",
            status="Failed",
            reference_doctype="Stock Entry",
            reference_name=stock_entry.name,
            source="ERPNext",
            request_url=get_dlm_material_issue_callback_url(),
            error_message=message,
        )
        frappe.db.commit()
        frappe.throw(message)

    payload = build_issue_confirm_payload(stock_entry)
    request_url = get_dlm_material_issue_callback_url()
    mes_log = create_mes_log(
        direction="Outbound",
        event="Stock Entry Issue Confirm",
        status="Pending",
        reference_doctype="Stock Entry",
        reference_name=stock_entry.name,
        source="ERPNext",
        request_url=request_url,
        request_payload=payload,
    )

    frappe.logger().info(f"推送库存移动单 {stock_entry_name} 到 DLM: {frappe.as_json(payload)}")

    try:
        response = post_issue_confirm(payload, request_url)
        validate_issue_confirm_response(response, payload)
        stock_entry.db_set("custom_mes_status", "Pushed")

        update_mes_log(
            mes_log,
            status="Success",
            response_payload=response,
            trace_id=response.get("traceId"),
            processed=get_dlm_processed_count(response),
        )
    except Exception:
        update_mes_log(
            mes_log,
            status="Failed",
            error_message=frappe.get_traceback(),
        )
        frappe.db.commit()
        raise

    return {
        "status": "success",
        "message": f"库存移动单 {stock_entry_name} 已成功推送到 DLM",
        "mes_status": "Pushed",
        "processed": get_dlm_processed_count(response),
        "trace_id": response.get("traceId"),
        "timestamp": now(),
    }


def build_issue_confirm_payload(stock_entry):
    validate_stock_entry_for_issue_confirm(stock_entry)

    posting_date = getdate(stock_entry.posting_date).isoformat() if stock_entry.posting_date else None
    material_request = get_issue_material_request(stock_entry)
    batch_no = stock_entry.get("custom_stock_entry_no")
    items_by_key = {}
    missing_fields = []

    for row in stock_entry.get("items", []):
        issued_qty = flt(row.get("transfer_qty") or row.get("qty"))

        if issued_qty <= 0:
            continue

        if not row.get("item_code"):
            missing_fields.append(f"第 {row.idx} 行缺少: item_code")
            continue

        issued_unit = get_issued_unit(row)
        if not issued_unit:
            missing_fields.append(f"第 {row.idx} 行缺少: issued_unit")
            continue

        key = (row.get("item_code"), issued_unit)
        item = items_by_key.setdefault(
            key,
            {
                "item_code": row.get("item_code"),
                "total_issued_qty": 0,
                "issued_unit": issued_unit,
                "batch_details": [],
            },
        )
        item["total_issued_qty"] = flt(item["total_issued_qty"]) + issued_qty
        item["batch_details"].append(
            {
                "batch_no": batch_no,
                "issued_qty": issued_qty,
            }
        )

    if missing_fields:
        frappe.throw("<br>".join(missing_fields), title=frappe._("DLM 发料回调字段不完整"))

    items = list(items_by_key.values())
    if not items:
        frappe.throw(frappe._("没有可推送到 DLM 的发料明细"))

    return {
        "event": "stock_entry.submit",
        "timestamp": now(),
        "material_request": material_request,
        "stock_entry": stock_entry.name,
        "posting_date": posting_date,
        "from_warehouse": stock_entry.get("from_warehouse") or get_first_item_value(stock_entry, "s_warehouse"),
        "to_warehouse": stock_entry.get("to_warehouse") or get_first_item_value(stock_entry, "t_warehouse"),
        "items": items,
    }


def get_issue_material_request(stock_entry):
    material_requests = {
        row.get("material_request")
        for row in stock_entry.get("items", [])
        if row.get("material_request") and flt(row.get("transfer_qty") or row.get("qty")) > 0
    }

    if len(material_requests) > 1:
        frappe.throw(
            frappe._("一张物料移动只能回调一个 Material Request，当前包含：{0}").format(
                ", ".join(sorted(material_requests))
            )
        )

    return next(iter(material_requests), None)


def get_first_item_value(stock_entry, fieldname):
    for row in stock_entry.get("items", []):
        if row.get(fieldname):
            return row.get(fieldname)
    return None


def get_issued_unit(row):
    unit = (row.get("stock_uom") or row.get("uom") or "").strip()
    if not unit:
        return None

    if unit.lower() in {"kg", "kgs", "kilogram", "kilograms"} or unit in {"千克", "公斤"}:
        return "kg"

    return "个"


def validate_stock_entry_for_issue_confirm(stock_entry):
    if not stock_entry.get("custom_stock_entry_no"):
        frappe.throw(frappe._("请先填写物料移动的 custom_stock_entry_no，再推送至 DLM"))

    if not get_issue_material_request(stock_entry):
        frappe.throw(frappe._("请先关联原生 Material Request，再推送至 DLM"))


def post_issue_confirm(payload, url=None):
    url = url or get_dlm_material_issue_callback_url()
    timeout = flt(frappe.conf.get("mes_request_timeout") or 15)

    try:
        response = get_request_session().post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except RequestException as exc:
        response = getattr(exc, "response", None)
        log_mes_push_error("DLM 发料回调接口 HTTP 调用失败", payload, response)
        frappe.throw(
            get_mes_http_error_message(response)
            or frappe._("DLM 发料回调接口调用失败：{0}").format(url)
        )
    except ValueError:
        log_mes_push_error("DLM 发料回调接口响应不是 JSON", payload)
        frappe.throw(frappe._("DLM 发料回调接口响应不是 JSON，请查看 Error Log"))


def validate_issue_confirm_response(response, payload):
    if not isinstance(response, dict):
        log_mes_push_error("DLM 发料回调接口响应格式异常", payload, response)
        frappe.throw(frappe._("DLM 发料回调接口响应格式异常"))

    if not response.get("success"):
        log_mes_push_error("DLM 发料回调接口返回失败", payload, response)
        frappe.throw(get_mes_error_message(response) or frappe._("DLM 发料回调失败"))

    data = response.get("data") or {}
    status = data.get("status")
    valid_statuses = {"processed", "already_issued", "partial"}

    if status and status not in valid_statuses:
        log_mes_push_error("DLM 发料回调业务状态异常", payload, response)
        frappe.throw(
            get_mes_error_message(response)
            or frappe._("DLM 发料回调业务状态异常：{0}").format(status)
        )


def get_dlm_processed_count(response):
    data = response.get("data") or {}
    return data.get("lines_updated") or data.get("processed")


def get_dlm_material_issue_callback_url():
    url = frappe.conf.get("dlm_material_issue_callback_url")
    if not url:
        frappe.throw(frappe._("缺少 DLM 接口配置：dlm_material_issue_callback_url"))
    return url


def get_mes_error_message(response):
    messages = []

    if response.get("message"):
        messages.append(response.get("message"))

    for error in response.get("errors") or []:
        if isinstance(error, dict):
            messages.append(error.get("message") or error.get("error") or frappe.as_json(error))
        else:
            messages.append(str(error))

    for error in (response.get("data") or {}).get("errors") or []:
        if isinstance(error, dict):
            messages.append(error.get("error") or error.get("message") or frappe.as_json(error))
        else:
            messages.append(str(error))

    return "<br>".join(filter(None, messages))


def log_mes_push_error(title, payload, response=None):
    message = {
        "payload": payload,
        "response": get_response_for_log(response),
        "traceback": frappe.get_traceback(),
    }
    frappe.log_error(title=title, message=frappe.as_json(message))


def get_response_for_log(response):
    if response is None:
        return None

    if isinstance(response, dict):
        return response

    response_data = {
        "status_code": response.status_code,
        "text": response.text,
    }

    try:
        response_data["json"] = response.json()
    except ValueError:
        pass

    return response_data


def get_mes_http_error_message(response):
    if response is None:
        return None

    try:
        data = response.json()
    except ValueError:
        data = {}

    message = data.get("message") or response.text
    error_code = data.get("errorCode")
    trace_id = data.get("traceId")

    parts = [frappe._("MES HTTP 状态码: {0}").format(response.status_code)]

    if error_code:
        parts.append(frappe._("错误码: {0}").format(error_code))

    if message:
        parts.append(frappe._("错误信息: {0}").format(message))

    if trace_id:
        parts.append(frappe._("Trace ID: {0}").format(trace_id))

    return "<br>".join(parts)


@frappe.whitelist()
def reset_mes_status(stock_entry_name):
    """
    重置库存转移单的 MES Status 为 Unpushed（当已推送的订单被修改时）
    """
    stock_entry = frappe.get_doc("Stock Entry", stock_entry_name)

    if stock_entry.get("custom_mes_status") == "Pushed":
        stock_entry.db_set("custom_mes_status", "Unpushed")
        frappe.logger().info(f"库存转移单 {stock_entry_name} 已修改，MES 状态重置为 Unpushed")

        return {
            "status": "success",
            "message": f"库存转移单 {stock_entry_name} 的 MES 状态已重置为未推送",
            "mes_status": "Unpushed"
        }

    return {
        "status": "skipped",
        "message": "无需重置"
    }

PENDING_PRODUCTION = "Pending Production"
PENDING_FINAL_PAYMENT = "Pending Final Payment"
INVALID_SALES_ORDER_STATUSES = {"Draft", "Cancelled", "Closed"}


@frappe.whitelist()
def create_and_submit_stock_entry_from_mes(data=None, stock_entry=None):
    """
    Create and submit a Stock Entry from MES, then move the Sales Order flow
    to Pending Final Payment.

    Accepted payloads:
    1. data={"sales_order": "SAL-ORD-...", "stock_entry": {...}}
    2. data={...} with sales_order inside the Stock Entry payload
    """
    payload = parse_json_if_needed(data if data is not None else stock_entry)

    if not isinstance(payload, dict):
        frappe.throw(frappe._("缺少请求数据或数据格式不正确"))

    validate_mes_api_user()
    validate_mes_stock_entry_permissions()

    if payload.get("stock_entry"):
        stock_entry_data = parse_json_if_needed(payload.get("stock_entry"))
    else:
        stock_entry_data = payload

    if not isinstance(stock_entry_data, dict):
        frappe.throw(frappe._("缺少 Stock Entry 数据或数据格式不正确"))

    sales_order_doc = get_sales_order_by_name(payload, stock_entry_data)
    validate_sales_order_for_mes_stock_entry(sales_order_doc)

    stock_entry_data = stock_entry_data.copy()
    stock_entry_data.pop("sales_order", None)
    stock_entry_data.pop("sales_order_name", None)
    stock_entry_data["doctype"] = "Stock Entry"

    stock_entry_doc = frappe.get_doc(stock_entry_data)
    validate_mes_stock_entry_data(stock_entry_doc, sales_order_doc)
    stock_entry_doc.insert()
    stock_entry_doc.submit()

    sales_order_doc.check_permission("write")
    sales_order_doc.update({"custom_process_status": PENDING_FINAL_PAYMENT})
    sales_order_doc.save()
    sales_order_doc.notify_update()

    return {
        "status": "success",
        "message": frappe._("物料移动已创建并提交，销售订单已更新为待收尾款。"),
        "stock_entry": stock_entry_doc.name,
        "stock_entry_docstatus": stock_entry_doc.docstatus,
        "sales_order": sales_order_doc.name,
        "process_status": PENDING_FINAL_PAYMENT,
        "timestamp": now(),
    }


def get_sales_order_by_name(payload, stock_entry_data):
    sales_order = (
        payload.get("sales_order")
        or payload.get("sales_order_name")
        or stock_entry_data.get("sales_order")
        or stock_entry_data.get("sales_order_name")
    )

    if not sales_order:
        frappe.throw(frappe._("缺少销售订单编号 sales_order"))

    if not frappe.db.exists("Sales Order", sales_order):
        frappe.throw(frappe._("未找到销售订单 {0}").format(sales_order))

    return frappe.get_doc("Sales Order", sales_order)


def parse_json_if_needed(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def validate_mes_api_user():
    if not is_mes_api_user():
        frappe.throw(frappe._("当前用户没有 MES 接口调用权限"), frappe.PermissionError)


def validate_mes_stock_entry_permissions():
    for doctype, permission_type in (("Stock Entry", "create"), ("Stock Entry", "submit"), ("Sales Order", "write")):
        if not frappe.has_permission(doctype, permission_type):
            frappe.throw(
                frappe._("当前用户缺少 {0} 的 {1} 权限").format(doctype, permission_type),
                frappe.PermissionError,
            )


def validate_sales_order_for_mes_stock_entry(sales_order):
    sales_order.check_permission("write")

    status = sales_order.get("status")
    if status in INVALID_SALES_ORDER_STATUSES:
        frappe.throw(
            frappe._("销售订单 {0} 原生状态为 {1}，不能通过 MES 入库接口处理").format(
                sales_order.name,
                status,
            )
        )

    if sales_order.docstatus != 1:
        frappe.throw(frappe._("销售订单 {0} 必须已提交").format(sales_order.name))

    if sales_order.get("custom_process_status") != PENDING_PRODUCTION:
        frappe.throw(
            frappe._("只有生产中的销售订单才能更新为待收尾款。销售订单 {0} 当前状态：{1}").format(
                sales_order.name,
                sales_order.get("custom_process_status") or "",
            )
        )


def validate_mes_stock_entry_data(stock_entry, sales_order):
    if stock_entry.doctype != "Stock Entry":
        frappe.throw(frappe._("只能通过此接口创建 Stock Entry"))

    if stock_entry.docstatus != 0:
        frappe.throw(frappe._("MES 传入的物料移动必须是草稿状态"))

    if not stock_entry.get("purpose"):
        frappe.throw(frappe._("缺少物料移动 Purpose"))

    if not stock_entry.get("company"):
        stock_entry.company = sales_order.company

    if stock_entry.company != sales_order.company:
        frappe.throw(frappe._("物料移动公司必须与销售订单公司一致"))

    if not stock_entry.get("items"):
        frappe.throw(frappe._("物料移动至少需要一行明细"))

    for row in stock_entry.get("items"):
        if not row.get("item_code"):
            frappe.throw(frappe._("第 {0} 行缺少物料号").format(row.idx))

        if flt(row.get("qty")) <= 0:
            frappe.throw(frappe._("第 {0} 行数量必须大于 0").format(row.idx))

        if not row.get("s_warehouse") and not row.get("t_warehouse"):
            frappe.throw(frappe._("第 {0} 行至少需要来源仓库或目标仓库").format(row.idx))

def update_material_request_transferred_qty(stock_entry, method=None):
    mr_item_names = {
        row.material_request_item
        for row in stock_entry.get("items", [])
        if is_material_request_issue_row(row)
    }
    if not mr_item_names:
        return

    transferred_qty_by_item = get_submitted_transferred_qty_by_material_request_item(mr_item_names)
    mr_names = set()

    for mr_item_name in mr_item_names:
        transferred_qty = transferred_qty_by_item.get(mr_item_name, 0)
        mr_name = frappe.db.get_value("Material Request Item", mr_item_name, "parent")

        frappe.db.set_value(
            "Material Request Item",
            mr_item_name,
            {
                "custom_transferred_qty": transferred_qty,
                "ordered_qty": transferred_qty,
            },
            update_modified=False,
        )

        if mr_name:
            mr_names.add(mr_name)

    messages = []
    for mr_name in mr_names:
        status_details = update_material_request_issue_status(mr_name)
        if status_details:
            messages.append(
                "{0}: 已发 {1} / 需求 {2}, per_ordered={3}%, status={4}".format(
                    mr_name,
                    status_details["issued_qty"],
                    status_details["total_qty"],
                    status_details["per_ordered"],
                    status_details["status"],
                )
            )

    if messages:
        frappe.msgprint("<br>".join(messages), title=frappe._("Material Request 发料状态"))


def get_submitted_transferred_qty_by_material_request_item(mr_item_names):
    placeholders = ", ".join(["%s"] * len(mr_item_names))
    rows = frappe.db.sql(
        f"""
        SELECT
            sed.material_request_item,
            SUM(
                CASE
                    WHEN IFNULL(se.is_return, 0) = 1 THEN -IFNULL(sed.transfer_qty, 0)
                    ELSE IFNULL(sed.transfer_qty, 0)
                END
            ) AS transferred_qty
        FROM `tabStock Entry Detail` sed
        INNER JOIN `tabStock Entry` se ON se.name = sed.parent
        WHERE sed.material_request_item IN ({placeholders})
            AND sed.docstatus = 1
            AND se.docstatus = 1
            AND IFNULL(sed.s_warehouse, '') != ''
        GROUP BY sed.material_request_item
        """,
        tuple(mr_item_names),
        as_dict=True,
    )

    return {row.material_request_item: flt(row.transferred_qty) for row in rows}


def is_material_request_issue_row(row):
    return bool(
        row.get("material_request")
        and row.get("material_request_item")
        and row.get("s_warehouse")
    )


def update_material_request_issue_status(mr_name):
    mr = frappe.get_doc("Material Request", mr_name)
    if mr.docstatus != 1 or mr.status in ("Stopped", "Cancelled"):
        return None

    total_qty = 0
    issued_qty = 0

    for row in mr.get("items", []):
        total_qty += flt(row.stock_qty or row.qty)
        issued_qty += flt(row.get("custom_transferred_qty"))

    per_ordered = (issued_qty / total_qty) * 100 if total_qty else 0

    if per_ordered >= 100:
        per_ordered = 100
        status = "Issued"
    elif per_ordered > 0:
        status = "Partially Ordered"
    else:
        status = "Pending"

    frappe.db.set_value(
        "Material Request",
        mr_name,
        {
            "per_ordered": per_ordered,
            "status": status,
        },
        update_modified=False,
    )

    return {
        "issued_qty": flt(issued_qty),
        "total_qty": flt(total_qty),
        "per_ordered": flt(per_ordered),
        "status": status,
    }

