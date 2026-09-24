import re

import frappe

INCIDENT_KEYWORDS = [
	("Fighting", r"fight|pigan"),
	("Bullying", r"bull|onea"),
	("Truancy", r"truan|absent|skip|toro"),
	("Lateness", r"late|chelew"),
	("Disrespect to Staff", r"disrespect|rude|insult|matusi"),
	("Exam Malpractice", r"cheat|malpractice|udanganyifu"),
	("Property Damage", r"damage|broke|destroy|haribu"),
	("Theft", r"theft|steal|stole|wizi|iba"),
	("Uniform Violation", r"uniform|sare"),
	("Prohibited Items", r"phone|simu|drug|alcohol|pombe|cigar|smok|sigara"),
]
SEVERITY_KEYWORDS = [
	("Minor", r"low|minor|ndogo"),
	("Serious", r"high|serious|severe|kubwa"),
	("Moderate", r"medium|moderate|wastani"),
]


def execute():
	"""incident_type and severity became Select fields. Map the old free text onto the new options
	and keep the original wording in description."""
	incident_options = frappe.get_meta("Discipline Record").get_field("incident_type").options.split("\n")
	for r in frappe.get_all("Discipline Record", fields=["name", "incident_type", "severity", "description"]):
		text = (r.incident_type or "").strip()
		values = {}

		if text not in incident_options:
			values["incident_type"] = next(
				(option for option, pattern in INCIDENT_KEYWORDS if re.search(pattern, text, re.I)), "Other"
			)
			if text and not r.description:
				values["description"] = text

		severity = (r.severity or "").strip()
		if severity not in ("Minor", "Moderate", "Serious"):
			values["severity"] = next(
				(option for option, pattern in SEVERITY_KEYWORDS if re.search(pattern, severity, re.I)),
				"Moderate",
			)

		if values:
			frappe.db.set_value("Discipline Record", r.name, values, update_modified=False)
