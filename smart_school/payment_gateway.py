import frappe
import requests

# Base for a real mobile money aggregator integration (D5). Not wired to the portal yet:
# the portal uses the demo flow in portal_utils while Smart School Settings.enable_demo_payments is on.
#
# TODO (real aggregator): move to an async flow: push request -> provider callback with signature
# verification -> create the Fee Payment only from a verified callback. A verified callback means the
# money has already left the parent's wallet, so it must NEVER be rejected for exceeding the
# outstanding balance: record the Fee Payment anyway and let Fee Payment mark the overpayment
# (overpayment field) for the accountant to refund or carry forward.


def initiate_mobile_money_payment(student, amount, phone_number, provider, term):
	log = frappe.get_doc(
		{
			"doctype": "Payment Gateway Log",
			"student": student,
			"term": term,
			"amount": amount,
			"phone_number": phone_number,
			"provider": provider,
			"status": "Pending",
		}
	)
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

	# Never fall back to a simulated success: a missing config must not create real Fee Payments
	if not api_url or not api_key:
		frappe.throw("Mobile money aggregator is not configured")

	payload = {"phone_number": phone_number, "amount": amount, "provider": provider}

	headers = {"Authorization": f"Bearer {api_key}"}

	response = requests.post(api_url, json=payload, headers=headers, timeout=30)
	return response.json()


def create_fee_payment_from_gateway(student, amount, term, reference):
	fee_payment = frappe.get_doc(
		{
			"doctype": "Fee Payment",
			"student": student,
			"term": term,
			"amount_paid": amount,
			"payment_date": frappe.utils.today(),
			"payment_method": "Mobile Money",
			"receipt_number": reference,
		}
	)
	fee_payment.insert(ignore_permissions=True)
	fee_payment.submit()
