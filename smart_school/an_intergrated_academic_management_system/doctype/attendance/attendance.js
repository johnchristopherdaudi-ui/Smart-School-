frappe.ui.form.on('Attendance', {
    class: function(frm) {
        frm.set_value('student', '');

        frm.set_query('student', function() {
            return {
                filters: {
                    current_class: frm.doc.class
                }
            };
        });
    }
});