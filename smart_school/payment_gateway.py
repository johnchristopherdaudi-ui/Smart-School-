import frappe
import requests


def initiate_mobile_money_payment(student, amount, phone_number, provider, term):
    log = frappe.get_doc({
        "doctype": "Payment Gateway Log",
        "student": student,
        "amount": amount,
        "phone_number": phone_number,
        "provider": provider,
        "status": "Pending"
    })
    log.insert(ignore_permissions=True)

    try:
        response = call_provider_api(phone_number, amount, provider)

        if response.get("success"):
            log.status = "Success"
            log.transaction_reference = response.get("reference")
            log.response_message = response.get("message")
            log.save(ignore_permissions=True)

            create_fee_payment_from_gateway(student, amount, term, log.transaction_reference)
        else:
            log.status = "Failed"
            log.response_message = response.get("message")
            log.save(ignore_permissions=True)

    except Exception as e:
        log.status = "Failed"
        log.response_message = str(e)
        log.save(ignore_permissions=True)

    return log


def call_provider_api(phone_number, amount, provider):
    api_url = frappe.conf.get("mobile_money_api_url")
    api_key = frappe.conf.get("mobile_money_api_key")

    if not api_url or not api_key:
        return simulate_payment(phone_number, amount, provider)

    payload = {
        "phone_number": phone_number,
        "amount": amount,
        "provider": provider
    }

    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.post(api_url, json=payload, headers=headers, timeout=30)
    return response.json()


def simulate_payment(phone_number, amount, provider):
    reference = frappe.generate_hash(length=10).upper()

    return {
        "success": True,
        "reference": f"SIM-{reference}",
        "message": f"Simulated payment of {amount} via {provider} completed successfully (demo mode)."
    }


def create_fee_payment_from_gateway(student, amount, term, reference):
    fee_payment = frappe.get_doc({
        "doctype": "Fee Payment",
        "student": student,
        "term": term,
        "amount_paid": amount,
        "payment_date": frappe.utils.today(),
        "payment_method": "Mobile Money",
        "receipt_number": reference
    })
    fee_payment.insert(ignore_permissions=True)