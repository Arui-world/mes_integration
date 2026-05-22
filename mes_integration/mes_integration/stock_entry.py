from requests.exceptions import RequestException

import frappe
from frappe.utils import flt, get_request_session, getdate, now

from mes_integration.mes_integration.integration_log import create_mes_log, update_mes_log


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
