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
            request_url=get_mes_issue_confirm_url(),
            error_message=message,
        )
        frappe.db.commit()
        frappe.throw(message)

    payload = build_issue_confirm_payload(stock_entry)
    request_url = get_mes_issue_confirm_url()
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

    frappe.logger().info(f"推送库存移动单 {stock_entry_name} 到 MES: {frappe.as_json(payload)}")

    try:
        response = post_issue_confirm(payload, request_url)
        validate_issue_confirm_response(response, payload)
        stock_entry.db_set("custom_mes_status", "Pushed")

        update_mes_log(
            mes_log,
            status="Success",
            response_payload=response,
            trace_id=response.get("traceId"),
            processed=response.get("data", {}).get("processed"),
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
        "message": f"库存移动单 {stock_entry_name} 已成功推送到 MES",
        "mes_status": "Pushed",
        "processed": response.get("data", {}).get("processed"),
        "trace_id": response.get("traceId"),
        "timestamp": now(),
    }


def build_issue_confirm_payload(stock_entry):
    validate_stock_entry_for_issue_confirm(stock_entry)

    posting_date = getdate(stock_entry.posting_date).isoformat() if stock_entry.posting_date else None
    items = []
    missing_fields = []

    for row in stock_entry.get("items", []):
        actual_issued_qty = flt(row.get("transfer_qty") or row.get("qty"))

        if actual_issued_qty <= 0:
            continue

        item = {
            "production_order_no": row.get("custom_material_request_no")
            or stock_entry.get("custom_material_request_no"),
            "item_code": row.get("item_code"),
            "custom_stock_entry_no": row.get("custom_stock_entry_no")
            or stock_entry.get("custom_stock_entry_no"),
            "actual_issued_qty": actual_issued_qty,
            "posting_date": posting_date,
            "stock_entry_name": stock_entry.name,
        }

        missing = [
            field
            for field in ("production_order_no", "item_code", "custom_stock_entry_no")
            if not item.get(field)
        ]
        if missing:
            missing_fields.append(f"第 {row.idx} 行缺少: {', '.join(missing)}")

        items.append(item)

    if missing_fields:
        frappe.throw("<br>".join(missing_fields), title=frappe._("MES 发料回写字段不完整"))

    if not items:
        frappe.throw(frappe._("没有可推送到 MES 的发料明细"))

    return {"items": items}


def validate_stock_entry_for_issue_confirm(stock_entry):
    if not stock_entry.get("custom_material_request_no") and not any(
        row.get("custom_material_request_no") for row in stock_entry.get("items", [])
    ):
        frappe.throw(frappe._("请先填写生产汇总单号 custom_material_request_no"))


def post_issue_confirm(payload, url=None):
    url = url or get_mes_issue_confirm_url()
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
        log_mes_push_error("MES 发料回写接口 HTTP 调用失败", payload, response)
        frappe.throw(
            get_mes_http_error_message(response)
            or frappe._("MES 发料回写接口调用失败：{0}").format(url)
        )
    except ValueError:
        log_mes_push_error("MES 发料回写接口响应不是 JSON", payload)
        frappe.throw(frappe._("MES 发料回写接口响应不是 JSON，请查看 Error Log"))


def validate_issue_confirm_response(response, payload):
    if not isinstance(response, dict):
        log_mes_push_error("MES 发料回写接口响应格式异常", payload, response)
        frappe.throw(frappe._("MES 发料回写接口响应格式异常"))

    if not response.get("success"):
        log_mes_push_error("MES 发料回写接口返回失败", payload, response)
        frappe.throw(get_mes_error_message(response) or frappe._("MES 发料回写失败"))

    data = response.get("data") or {}

    if not data.get("success"):
        log_mes_push_error("MES 发料回写存在业务失败", payload, response)
        frappe.throw(get_mes_error_message(response) or frappe._("MES 发料回写存在业务失败"))

    expected_count = len(payload.get("items") or [])
    processed_count = flt(data.get("processed"))

    if processed_count != expected_count:
        log_mes_push_error("MES 发料回写处理条数不一致", payload, response)
        frappe.throw(
            frappe._("MES 发料回写处理条数不一致，ERP 推送 {0} 条，MES 处理 {1} 条").format(
                expected_count,
                processed_count,
            )
        )


def get_mes_issue_confirm_url():
    url = frappe.conf.get("mes_issue_confirm_url")
    if not url:
        frappe.throw(frappe._("缺少 MES 接口配置：mes_issue_confirm_url"))
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
    if not response:
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
    if not response:
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
    1. data={"custom_odt": "ODT-...", "stock_entry": {...}}
    2. data={...} with custom_odt inside the Stock Entry payload
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

    sales_order_doc = get_sales_order_by_custom_odt(payload, stock_entry_data)
    validate_sales_order_for_mes_stock_entry(sales_order_doc)

    stock_entry_data = stock_entry_data.copy()
    stock_entry_data.pop("custom_odt", None)
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
        "custom_odt": sales_order_doc.get("custom_odt"),
        "process_status": PENDING_FINAL_PAYMENT,
        "timestamp": now(),
    }


def get_sales_order_by_custom_odt(payload, stock_entry_data):
    custom_odt = payload.get("custom_odt") or stock_entry_data.get("custom_odt")

    if not custom_odt:
        frappe.throw(frappe._("缺少销售订单自定义字段 custom_odt"))

    sales_orders = frappe.get_all(
        "Sales Order",
        filters={"custom_odt": custom_odt},
        pluck="name",
    )

    if not sales_orders:
        frappe.throw(frappe._("未找到 custom_odt 为 {0} 的销售订单").format(custom_odt))

    if len(sales_orders) > 1:
        frappe.throw(
            frappe._("custom_odt {0} 匹配到多个销售订单，请检查销售订单 custom_odt 唯一性").format(
                custom_odt
            )
        )

    return frappe.get_doc("Sales Order", sales_orders[0])


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

