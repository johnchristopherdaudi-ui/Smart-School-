import frappe
from frappe.model.document import Document
from smart_school.fees import get_class_for_term
from smart_school.notifications import send_notification


class FeePayment(Document):
    def validate(self):
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
        amount_due = self.amount_due or 0

        all_payments = frappe.get_all(
            "Fee Payment",
            filters={
                "student": self.student,
                "term": self.term,
                "name": ["!=", self.name]
            },
            fields=["amount_paid"]
        )

        total_paid_before = sum([p.amount_paid or 0 for p in all_payments])
        total_paid_including_this = total_paid_before + (self.amount_paid or 0)

        difference = amount_due - total_paid_including_this

        if difference > 0:
            self.balance = difference
            self.overpayment = 0
        else:
            self.balance = 0
            self.overpayment = abs(difference)

        if total_paid_including_this <= 0:
            self.status = "Unpaid"
        elif total_paid_including_this >= amount_due:
            self.status = "Paid"
        else:
            self.status = "Partial"

    def on_update(self):
        self.notify_guardian()

    def notify_guardian(self):
        message = f"Payment of {self.amount_paid} received. Balance remaining: {self.balance}."
        send_notification(self.student, message, "Fee Payment")