import frappe
from frappe.model.document import Document
from frappe.utils import flt
from smart_school.fees import get_class_for_term, get_fee_statement
from smart_school.notifications import send_notification


class FeePayment(Document):
    def validate(self):
        if flt(self.amount_paid) <= 0:
            frappe.throw("Kiasi kilicholipwa lazima kiwe zaidi ya 0")

        self.set_amount_due()
        self.set_receipt_number()
        self.set_status_and_balance()

    def set_amount_due(self):
        self.amount_due = 0  # default kwanza, itabadilishwa chini kama Fee Structure ikipatikana

        if not self.get("class"):
            self.set("class", get_class_for_term(self.student, self.term))

        fee_structure = frappe.get_all(
            "Fee Structure",
            filters={"class": self.get("class"), "term": self.term},
            fields=["amount"]
        )

        if fee_structure:
            self.amount_due = fee_structure[0].amount
        else:
            frappe.msgprint(
                "Hakuna Fee Structure iliyowekwa kwa class na term hii. "
                "Balance haitohesabika sahihi mpaka Fee Structure iundwe.",
                alert=True
            )

    def set_receipt_number(self):
        if not self.receipt_number:
            self.receipt_number = self.name

    def set_status_and_balance(self):
        """Snapshot at the time of this payment, from the fee statement: submitted payments of this
        term plus credit carried forward from earlier terms."""
        row = next((r for r in get_fee_statement(self.student).rows if r.term == self.term), None)
        outstanding_before = row.remaining if row else flt(self.amount_due)
        paid_before = (row.total_paid + row.credit_applied) if row else 0

        self.balance = max(outstanding_before - flt(self.amount_paid), 0)
        self.overpayment = max(flt(self.amount_paid) - outstanding_before, 0) if self.amount_due else 0

        total_paid_including_this = paid_before + flt(self.amount_paid)
        if total_paid_including_this <= 0:
            self.status = "Unpaid"
        elif total_paid_including_this >= flt(self.amount_due):
            self.status = "Paid"
        else:
            self.status = "Partial"

    def on_submit(self):
        # Once per payment: not for payments submitted by a data patch, nor for an amended copy
        if not frappe.flags.in_patch and not self.amended_from:
            self.notify_guardian()

    def notify_guardian(self):
        message = f"Malipo ya {flt(self.amount_paid):,.0f} TZS yamepokelewa. Salio la muhula huu: {flt(self.balance):,.0f} TZS."
        send_notification(self.student, message, "Fee Payment")
