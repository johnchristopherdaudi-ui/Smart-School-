// Copyright (c) 2026, john daudi and contributors
// For license information, please see license.txt

frappe.ui.form.on("Student Promotion Tool", {
	refresh(frm) {
		frm.disable_save();

		frm.add_custom_button(__("Get Students"), () => {
			if (!frm.doc.from_class || !frm.doc.academic_year) {
				frappe.msgprint(__("Select the class and the academic year first"));
				return;
			}
			frm.call("get_students").then(() => frm.refresh_fields());
		});

		if ((frm.doc.students || []).length) {
			frm.add_custom_button(__("Promote"), () => {
				frappe.confirm(
					__("Record {0} and move students to {1}? Students marked Repeat stay in {2}.", [
						frm.doc.academic_year, frm.doc.to_class, frm.doc.from_class,
					]),
					() => frm.call("promote").then((r) => {
						const c = r.message;
						frappe.msgprint(__("Promoted: {0}, Graduated: {1}, Repeating: {2}, Skipped: {3}",
							[c.promoted, c.graduated, c.repeating, c.skipped]));
						frm.reload_doc();
					})
				);
			}).addClass("btn-primary");
		}
	},
});
