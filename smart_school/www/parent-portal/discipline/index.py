import frappe
from smart_school.portal_utils import get_portal_guardian, get_children, get_notifications

# Options are English on the desk; parents read them in Swahili
INCIDENT_LABELS = {
    "Fighting": "Mapigano",
    "Bullying": "Uonevu",
    "Truancy": "Utoro",
    "Lateness": "Kuchelewa",
    "Disrespect to Staff": "Utovu wa nidhamu kwa walimu",
    "Exam Malpractice": "Udanganyifu katika mitihani",
    "Property Damage": "Uharibifu wa mali",
    "Theft": "Wizi",
    "Uniform Violation": "Kukiuka sare",
    "Prohibited Items": "Vitu visivyoruhusiwa",
    "Other": "Mengineyo",
}
SEVERITY_LABELS = {"Minor": "Ndogo", "Moderate": "Wastani", "Serious": "Kubwa"}

def get_context(context):
    guardian = get_portal_guardian()
    children = get_children(guardian)
    if not children:
        frappe.throw("No children linked to this account")

    selected_id = frappe.form_dict.get("student") or children[0].name
    selected_student = next((c for c in children if c.name == selected_id), children[0])

    records = frappe.get_all(
        "Discipline Record",
        filters={"student": selected_student.name},
        fields=["date", "incident_type", "severity", "action_taken"],
        order_by="date desc"
    )
    for r in records:
        r.severity_class = (r.severity or "").lower()
        r.incident_label = INCIDENT_LABELS.get(r.incident_type, r.incident_type)
        r.severity_label = SEVERITY_LABELS.get(r.severity, r.severity)

    context.guardian = guardian
    context.children = children
    context.selected_student = selected_student
    context.records = records
    notif_data = get_notifications(guardian, children)
    context.notifications = notif_data["items"]
    context.unseen_count = notif_data["unseen_count"]
    context.no_cache = 1
