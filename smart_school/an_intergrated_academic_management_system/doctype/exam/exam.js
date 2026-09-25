// Copyright (c) 2026, john daudi and contributors
// For license information, please see license.txt

frappe.ui.form.on("Exam", {
	refresh(frm) {
		if (frm.is_new() || !(frappe.user.has_role("Headmaster") || frappe.user.has_role("System Manager"))) {
			return;
		}

		const call = (method, message) => {
			frappe.call({
				method: `smart_school.results.${method}`,
				args: { exam: frm.doc.name },
				freeze: true,
				callback: () => {
					frappe.show_alert({ message: __(message), indicator: "green" });
					frm.reload_doc();
				},
			});
		};

		if (frm.doc.results_published) {
			frm.add_custom_button(__("Unpublish Results"), () => {
				frappe.confirm(
					__("Hide these results from parents? This is noted on the exam and raises a marks alert."),
					() => call("unpublish_exam_results", "Results unpublished")
				);
			});
		} else {
			const publish = () => call("publish_exam_results", "Results published; parents are being notified");
			frm.add_custom_button(__("Publish Results"), () => check_marks_then_publish(frm, publish)).addClass(
				"btn-primary"
			);
		}

		frm.add_custom_button(__("Recompute Term Results"), () => call("recompute_term_results", "Term results recomputed"));
	},
});

// Marks alerts are a warning before publishing, never a block
function check_marks_then_publish(frm, publish) {
	const confirm_publish = () => frappe.confirm(__("Publish these results to parents and notify them?"), publish);

	frappe.call({
		method: "smart_school.marks_alerts.check_exam",
		args: { exam: frm.doc.name },
		freeze: true,
		freeze_message: __("Checking marks..."),
		callback: (r) => {
			const alerts = r.message || [];
			alerts.length ? show_marks_alerts(frm, alerts, publish) : confirm_publish();
		},
		error: () => frappe.confirm(__("The marks check could not run. Publish these results anyway?"), publish),
	});
}

function show_marks_alerts(frm, alerts, publish) {
	const esc = frappe.utils.escape_html;
	const rows = alerts
		.map(
			(a) => `<tr>
				<td>${esc(__(a.severity))}</td>
				<td><a href="/app/marks-alert/${encodeURIComponent(a.name)}" target="_blank">${esc(__(a.alert_type))}</a></td>
				<td>${esc(a.message || "")}</td>
			</tr>`
		)
		.join("");
	const list_url = `/app/marks-alert?exam=${encodeURIComponent(frm.doc.name)}&status=Open`;

	const dialog = new frappe.ui.Dialog({
		title: __("{0} open marks alert(s)", [alerts.length]),
		size: "extra-large",
		fields: [
			{
				fieldtype: "HTML",
				options: `<p>${__("These marks may need a second look. You can still publish; the open alerts will be noted on the exam.")}
					<a href="${list_url}" target="_blank">${__("Review alerts")}</a></p>
					<table class="table table-bordered small">
						<thead><tr><th>${__("Severity")}</th><th>${__("Alert")}</th><th>${__("Details")}</th></tr></thead>
						<tbody>${rows}</tbody>
					</table>`,
			},
		],
		primary_action_label: __("Publish anyway"),
		primary_action() {
			dialog.hide();
			publish();
		},
		secondary_action_label: __("Cancel"),
		secondary_action() {
			dialog.hide();
		},
	});
	dialog.show();
}
