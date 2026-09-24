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
				frappe.confirm(__("Hide these results from parents?"), () => call("unpublish_exam_results", "Results unpublished"));
			});
		} else {
			frm.add_custom_button(__("Publish Results"), () => {
				frappe.confirm(__("Publish these results to parents and notify them?"), () =>
					call("publish_exam_results", "Results published; parents are being notified")
				);
			}).addClass("btn-primary");
		}

		frm.add_custom_button(__("Recompute Term Results"), () => call("recompute_term_results", "Term results recomputed"));
	},
});
