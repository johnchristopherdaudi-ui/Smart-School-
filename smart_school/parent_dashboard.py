"""Parent portal dashboard: cards, trend and gentle alerts for one child.

Results come only from published exams (get_portal_results). No risk score is shown to parents:
the alerts describe facts in plain Swahili and suggest what to do."""

import frappe
from frappe.utils import add_days, flt, nowdate

from smart_school.fees import get_fee_statement
from smart_school.portal_utils import get_announcements
from smart_school.results import get_grade, get_portal_results, get_subject_scores
from smart_school.tasks import get_current_term

ATTENDANCE_ALERT_BELOW = 90  # % of recorded days attended
MIN_DAYS_FOR_ATTENDANCE_ALERT = 5
DECLINE_ALERT_POINTS = 5


def get_dashboard(student):
	first_name = (student.full_name or "").split()[0].title() if student.full_name else "Mwanafunzi"
	data = frappe._dict(alerts=[])

	# Results: latest fully published term and the trend of published terms
	published = [t for t in get_portal_results(student.name) if t.summary]
	data.trend_labels = [t.term_name for t in published]
	data.trend_values = [t.summary.average for t in published]
	data.latest = published[-1] if published else None

	if data.latest:
		scores = get_subject_scores(student.name, data.latest.term)[0]
		failed = sorted(s for s, score in scores.items() if get_grade(score)[0] == "F")
		if failed:
			data.alerts.append(
				frappe._dict(
					kind="results",
					text=(
						f"{first_name} ana {'somo 1' if len(failed) == 1 else f'masomo {len(failed)}'} yenye alama ya F kwenye "
						f"matokeo ya {data.latest.term_name}: {', '.join(failed)}. Tunashauri kuongea na walimu wa masomo haya."
					),
				)
			)
		if len(published) >= 2:
			drop = flt(published[-2].summary.average) - flt(data.latest.summary.average)
			if drop >= DECLINE_ALERT_POINTS:
				data.alerts.append(
					frappe._dict(
						kind="results",
						text=(
							f"Wastani wa {first_name} umeshuka kutoka {published[-2].summary.average} hadi "
							f"{data.latest.summary.average} ukilinganisha na muhula uliopita. Mhimize na umfuatilie kwa karibu."
						),
					)
				)

	# Attendance and discipline of the current term
	term = get_current_term()
	statuses = (
		frappe.get_all("Attendance", filters={"student": student.name, "term": term.name}, pluck="status")
		if term
		else []
	)
	attended = statuses.count("Present") + statuses.count("Late")
	data.attendance = frappe._dict(
		term_name=frappe.get_cached_value("Term", term.name, "term_name") if term else None,
		days=len(statuses),
		absent=statuses.count("Absent"),
		rate=flt(attended / len(statuses) * 100, 1) if statuses else None,
	)
	if (
		data.attendance.rate is not None
		and len(statuses) >= MIN_DAYS_FOR_ATTENDANCE_ALERT
		and data.attendance.rate < ATTENDANCE_ALERT_BELOW
	):
		data.alerts.append(
			frappe._dict(
				kind="attendance",
				text=(
					f"Mahudhurio ya {first_name} muhula huu ni {data.attendance.rate:g}% "
					f"(hakuhudhuria siku {data.attendance.absent}). Tafadhali fuatilia."
				),
			)
		)

	if term and frappe.db.count(
		"Discipline Record", {"student": student.name, "date": ["between", [term.start_date, term.end_date]]}
	):
		data.alerts.append(
			frappe._dict(
				kind="discipline",
				text=(
					f"Kuna taarifa ya nidhamu kuhusu {first_name} muhula huu. Tafadhali angalia ukurasa wa Nidhamu."
				),
			)
		)

	# Fees
	statement = get_fee_statement(student.name)
	data.fees = frappe._dict(balance=statement.balance, credit=statement.credit)
	if statement.balance > 0:
		data.alerts.append(
			frappe._dict(kind="fees", text=f"Kuna deni la ada la {statement.balance:,.0f} TZS.")
		)

	# Announcements of the last 30 days
	recent = get_announcements(
		[student.current_class] if student.current_class else [], since=add_days(nowdate(), -30)
	)
	data.announcements = frappe._dict(count=len(recent), latest=recent[0].title if recent else None)

	if not data.alerts:
		data.alerts.append(
			frappe._dict(
				kind="ok", text=f"Hakuna jambo la kuhofia kwa sasa. Endelea kumtia moyo {first_name}!"
			)
		)
	return data
