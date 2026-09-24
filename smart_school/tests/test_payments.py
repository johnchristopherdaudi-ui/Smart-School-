"""#4, #5, #8, #13, #17: payment requests, demo confirmation, fee statement and Fee Payment lifecycle."""

from unittest.mock import patch

import frappe

from smart_school.fees import get_fee_statement, get_term_outstanding
from smart_school.tests.factory import (
	ACCOUNTANT,
	PARENT_1,
	PARENT_2,
	SchoolTestCase,
	as_user,
	call,
	no_commit,
	pay,
	render,
)

PORTAL = "smart_school.portal_utils."
FEE_PAYMENT_MODULE = "smart_school.an_intergrated_academic_management_system.doctype.fee_payment.fee_payment"


class TestPaymentRequests(SchoolTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.set_single_value("Smart School Settings", "enable_demo_payments", 1)

	def request(self, **kwargs):
		args = dict(student=self.s["a"], term="_Test T3", provider="M-Pesa", phone_number="0754 123 456")
		args.update(kwargs)
		with as_user(PARENT_1), no_commit():
			return call(PORTAL + "create_payment_request", **args)

	def confirm(self, reference, user=PARENT_1, success=1):
		with as_user(user), no_commit():
			return call(PORTAL + "confirm_demo_payment", reference=reference, success=success)

	def test_request_validation(self):
		for bad in [
			dict(amount="0"),
			dict(amount="99999999"),
			dict(amount="abc"),
			dict(phone_number="12345"),
			dict(provider="M-pesa"),
			dict(term='_Test T3";alert(1);//'),
			dict(student=self.s["e"]),
		]:
			with self.subTest(bad=bad):
				self.assertRaises(frappe.ValidationError, self.request, **bad)

	def test_mpesa_partial_payment_stored_with_normalised_phone(self):
		ref = self.request(amount="300000")["reference"]
		log = frappe.db.get_value(
			"Payment Gateway Log",
			{"transaction_reference": ref},
			["term", "amount", "phone_number", "provider", "status"],
			as_dict=True,
		)
		self.assertEqual(
			(log.term, log.amount, log.phone_number, log.provider, log.status),
			("_Test T3", 300000, "255754123456", "M-Pesa", "Pending"),
		)

	def test_double_confirm_creates_one_payment(self):
		ref = self.request(amount="100000")["reference"]
		result = self.confirm(ref)
		self.assertTrue(result["success"])
		self.assertRaises(frappe.ValidationError, self.confirm, ref)
		self.assertEqual(frappe.db.count("Fee Payment", {"receipt_number": ref, "docstatus": 1}), 1)
		self.assertEqual(frappe.db.get_value("Fee Payment", result["fee_payment"], "term"), "_Test T3")

	def test_second_pending_request_cannot_overpay(self):
		outstanding = get_term_outstanding(self.s["b"], "_Test T3")
		first = self.request(student=self.s["b"], amount=str(outstanding))["reference"]
		second = self.request(student=self.s["b"], amount=str(outstanding))["reference"]
		self.assertTrue(self.confirm(first)["success"])
		self.assertFalse(self.confirm(second)["success"])
		self.assertEqual(
			frappe.db.get_value("Payment Gateway Log", {"transaction_reference": second}, "status"), "Failed"
		)

	def test_other_parent_cannot_confirm(self):
		ref = self.request(amount="1000")["reference"]
		self.assertRaises(frappe.PermissionError, self.confirm, ref, PARENT_2)

	def test_demo_switch_off(self):
		ref = self.request(amount="1000")["reference"]
		frappe.db.set_single_value("Smart School Settings", "enable_demo_payments", 0)
		self.assertRaises(frappe.PermissionError, self.request)
		self.assertRaises(frappe.PermissionError, self.confirm, ref)
		with as_user(PARENT_1):
			status, body, _ = render("parent-portal/fees", student=self.s["a"])
		self.assertEqual(status, 200)
		self.assertNotIn('class="sp-pay-btn"', body)

	def test_pay_page_escapes_and_validates_input(self):
		with as_user(PARENT_1):
			status, body, _ = render("parent-portal/pay", student=self.s["a"], term="_Test T3")
			self.assertEqual(status, 200)
			self.assertIn(f'student: "{self.s["a"]}"', body)  # JSON, not a hand-quoted string
			status, body, _ = render("parent-portal/pay", student=self.s["a"], term='_Test T3";alert(1);//')
		self.assertNotEqual(status, 200)
		self.assertNotIn('";alert(1)', body)


class TestFeeStatementAndPayments(SchoolTestCase):
	def test_terms_without_payments_are_debt(self):
		statement = get_fee_statement(self.s["d"])
		self.assertEqual([r.term for r in statement.rows], ["_Test T1", "_Test T2", "_Test T3"])
		self.assertEqual(statement.balance, 600000 + 750000 + 800000)

	def test_credit_pays_oldest_debt_first(self):
		pay(self.s["c"], "_Test T1", 300000)
		pay(self.s["c"], "_Test T3", 1000000)  # 200,000 more than T3's fee
		statement = get_fee_statement(self.s["c"])
		rows = {r.term: r for r in statement.rows}
		self.assertEqual(rows["_Test T1"].credit_applied, 200000)
		self.assertEqual(rows["_Test T1"].remaining, 100000)
		self.assertEqual(rows["_Test T2"].remaining, 750000)
		self.assertEqual(statement.credit, 0)

	def test_leftover_credit(self):
		pay(self.s["b"], "_Test T1", 600000)
		pay(self.s["b"], "_Test T2", 750000)
		pay(self.s["b"], "_Test T3", 900000)
		statement = get_fee_statement(self.s["b"])
		self.assertEqual((statement.balance, statement.credit), (0, 100000))

	def test_draft_not_counted_and_one_notification_on_submit(self):
		before = get_term_outstanding(self.s["a"], "_Test T2")
		with patch(f"{FEE_PAYMENT_MODULE}.send_notification") as notify, as_user(ACCOUNTANT):
			doc = frappe.get_doc(
				{
					"doctype": "Fee Payment",
					"student": self.s["a"],
					"term": "_Test T2",
					"amount_paid": 50000,
					"payment_date": frappe.utils.today(),
					"payment_method": "Cash",
					"status": "Partial",
				}
			).insert()
			self.assertEqual(get_term_outstanding(self.s["a"], "_Test T2"), before)
			self.assertEqual(notify.call_count, 0)
			doc.submit()
			self.assertEqual(notify.call_count, 1)
		self.assertTrue(doc.name.startswith("RCPT-"))
		self.assertEqual(get_term_outstanding(self.s["a"], "_Test T2"), before - 50000)

	def test_cancel_reverses_and_submitted_is_immutable(self):
		doc = pay(self.s["a"], "_Test T1", 10000)
		doc.amount_paid = 1
		self.assertRaises(frappe.UpdateAfterSubmitError, doc.save)
		doc.reload()
		before = get_term_outstanding(self.s["a"], "_Test T1")
		doc.cancel()
		self.assertEqual(get_term_outstanding(self.s["a"], "_Test T1"), before + 10000)

	def test_zero_amount_and_parent_refused(self):
		self.assertRaises(frappe.ValidationError, pay, self.s["a"], "_Test T1", 0)
		with as_user(PARENT_1):
			doc = frappe.get_doc(
				{
					"doctype": "Fee Payment",
					"student": self.s["a"],
					"term": "_Test T1",
					"amount_paid": 1,
					"payment_date": frappe.utils.today(),
					"payment_method": "Cash",
					"status": "Partial",
				}
			)
			self.assertRaises(frappe.PermissionError, doc.insert)
