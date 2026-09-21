frappe.ui.form.on('Exam Result', {
    onload: function(frm) {
        if (frm.is_new()) {
            frappe.db.get_value('Teacher', {user: frappe.session.user}, 'name', (r) => {
                if (r && r.name) {
                    frm.set_value('teacher', r.name);
                }
            });
        }
    },

    student: function(frm) {
        apply_subject_filter(frm);
    },

    exam: function(frm) {
        apply_subject_filter(frm);
    }
});

function apply_subject_filter(frm) {
    if (!frm.doc.exam || !frm.doc.student) {
        return;
    }

    frappe.db.get_value('Exam', frm.doc.exam, 'class', (exam_data) => {
        if (!exam_data || !exam_data.class) return;

        let student_class = exam_data.class;

        frappe.db.get_value('Student', frm.doc.student, 'combination', (student_data) => {
            let student_combination = student_data ? student_data.combination : null;

            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Class Subject Mapping',
                    filters: { class: student_class },
                    fields: ['subject', 'subject_scope', 'combination'],
                    limit_page_length: 0
                },
                callback: function(response) {
                    let mappings = response.message || [];

                    let allowed_subjects = mappings
                        .filter(row => {
                            if (row.subject_scope === 'All Combinations') return true;
                            if (row.subject_scope === 'Specific Combination'
                                && row.combination === student_combination) return true;
                            return false;
                        })
                        .map(row => row.subject);

                    frm.set_query('subject', function() {
                        return {
                            filters: {
                                name: ['in', allowed_subjects]
                            }
                        };
                    });
                }
            });
        });
    });
}