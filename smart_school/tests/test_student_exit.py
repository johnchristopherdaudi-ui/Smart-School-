"""Students who leave: exit_date, fees only for terms that started before they left (earlier debts remain),
the same rule in the defaulters report, the Outstanding Fees card and the portal, and no risk prediction."""

import frappe
from frappe.utils import add_days, getdate, today

from smart_school import reports, tasks
from smart_school.fees import get_fee_statement, get_term_outstanding
from smart_school.patches import set_student_exit_dates
from smart_school.tests.factory import (
	ACCOUNTANT,
	FEES,
	PARENT_1,
	SchoolTestCase,
	as_user,
	call,
	enforce_roles,
	make_student,
	no_commit,
	pay,
)

DEFAULTERS = "smart_school.an_intergrated_academic_management_system.report.fee_collection_and_defaulters.fee_collection_and_defaulters"


def term_start(term):
	return getdate(frappe.db.get_value("Term", term, "start_date"))


def leave(student, status="Dropped", exit_date=None):
	doc = frappe.get_doc("Student", student)
	doc.status = status
	doc.exit_date = exit_date
	doc.save()
	return doc


class TestStudentExit(SchoolTestCase):
	def test_exit_date_is_filled_kept_and_cleared(self):
		student = make_student("_Test Exit Dates", "_Test FORM 1", "Female")
		frappe.db.set_value("Student", student, {"risk_score": 70, "risk_level": "High"})

		doc = leave(student)
		self.assertEqual(getdate(doc.exit_date), getdate(today()))
		self.assertEqual((doc.risk_score, doc.risk_level), (0, None))  # no risk prediction after leaving

		doc.exit_date = add_days(today(), -30)  # the date can be corrected
		doc.save()
		self.assertEqual(getdate(doc.exit_date), getdate(add_days(today(), -30)))

		doc.status = "Active"
		doc.save()
		self.assertIsNone(doc.exit_date)

		doc.admission_date = today()
		doc.status = "Transferred"
		doc.exit_date = add_days(today(), -1)
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_fees_stop_at_exit_and_earlier_debts_remain(self):
		student = make_student("_Test Exit Fees", "_Test FORM 1", "Male")
		pay(student, "_Test T1", FEES["_Test T1"])
		pay(student, "_Test T3", 100000)  # paid early for a term that starts after the student leaves
		leave(student, exit_date=add_days(term_start("_Test T2"), 5))  # left during Term 2

		statement = get_fee_statement(student)
		rows = {r.term: r for r in statement.rows}
		self.assertEqual((rows["_Test T1"].amount_due, rows["_Test T1"].remaining), (FEES["_Test T1"], 0))
		self.assertEqual(rows["_Test T2"].amount_due, FEES["_Test T2"])  # started before leaving: charged
		self.assertEqual(rows["_Test T3"].amount_due, 0)  # started after leaving: not charged
		# the early payment for Term 3 becomes credit and pays the Term 2 debt
		self.assertEqual(rows["_Test T2"].remaining, FEES["_Test T2"] - 100000)
		self.assertEqual(statement.balance, FEES["_Test T2"] - 100000)
		self.assertEqual(get_term_outstanding(student, "_Test T3"), 0)

		# A payment recorded for a term after leaving is all credit
		payment = pay(student, "_Test T3", 50000)
		self.assertEqual((payment.status, payment.balance, payment.overpayment), ("Paid", 0, 50000))
		self.assertEqual(get_fee_statement(student).balance, FEES["_Test T2"] - 150000)

	def test_student_who_leaves_before_any_term_owes_nothing(self):
		student = make_student("_Test Exit Early", "_Test FORM 1", "Male")
		leave(student, "Transferred", exit_date=term_start("_Test T1"))
		self.assertEqual(get_fee_statement(student).rows, [])

	def test_defaulters_report_card_and_portal_use_the_same_rule(self):
		owes = make_student("_Test Exit Owes", "_Test FORM 1", "Female")
		leave(owes, exit_date=add_days(term_start("_Test T2"), 5))
		cleared = make_student("_Test Exit Cleared", "_Test FORM 1", "Male")
		pay(cleared, "_Test T1", FEES["_Test T1"])
		leave(cleared, "Transferred", exit_date=add_days(term_start("_Test T1"), 5))
		debt = FEES["_Test T1"] + FEES["_Test T2"]
		self.assertEqual(get_fee_statement(owes).balance, debt)

		with as_user(ACCOUNTANT), enforce_roles():
			_, rows = frappe.get_attr(DEFAULTERS + ".execute")({})
			card = reports.get_outstanding_fees()
		by_student = {r["student"]: r for r in rows}
		self.assertEqual(
			(by_student[owes]["student_status"], by_student[owes]["outstanding"]), ("Dropped", debt)
		)
		self.assertNotIn(cleared, by_student)  # left without debt: not listed
		everyone = sum(get_fee_statement(s).balance for s in frappe.get_all("Student", pluck="name"))
		self.assertEqual(card["value"], everyone)

		# Portal: the parent can still pay the debt from before leaving, not a term after it
		guardian = frappe.get_doc("Guardian", {"email": PARENT_1})
		guardian.append("students", {"student": owes, "relationship": "Mother"})
		guardian.save(ignore_permissions=True)
		frappe.db.set_single_value("Smart School Settings", "enable_demo_payments", 1)
		request = dict(student=owes, provider="M-Pesa", phone_number="0754 123 456")
		create = "smart_school.portal_utils.create_payment_request"
		with as_user(PARENT_1), no_commit():
			self.assertRaises(frappe.ValidationError, call, create, term="_Test T3", **request)
			call(create, term="_Test T2", amount="1000", **request)

	def test_students_who_left_get_no_risk_prediction(self):
		student = make_student("_Test Exit Risk", "_Test FORM 1", "Male")
		self.assertIsNotNone(tasks.calculate_risk_score(student))
		leave(student)
		self.assertIsNone(tasks.calculate_risk_score(student))
		tasks.calculate_all_risk_scores()
		self.assertEqual(frappe.db.get_value("Student", student, ["risk_score", "risk_level"]), (0, None))

	def test_patch_fills_exit_dates_from_history(self):
		changed = make_student("_Test Exit Patch Changed", "_Test FORM 1", "Male")
		leave(changed)
		imported = make_student("_Test Exit Patch Imported", "_Test FORM 1", "Female")
		frappe.db.set_value("Student", imported, "status", "Dropped")  # as a Data Import would leave it
		for student in (changed, imported):
			frappe.db.set_value("Student", student, "exit_date", None)

		set_student_exit_dates.execute()
		self.assertEqual(frappe.db.get_value("Student", changed, "exit_date"), getdate(today()))
		self.assertEqual(
			frappe.db.get_value("Student", imported, "exit_date"),
			getdate(frappe.db.get_value("Student", imported, "creation")),
		)
