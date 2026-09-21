frappe.ui.form.on('Student', {
    current_class: function(frm) {
        frm.set_query('current_section', function() {
            return { filters: { class: frm.doc.current_class } };
        });
        frm.set_value('current_section', '');
    },
    refresh: function(frm) {
        frm.set_query('current_section', function() {
            return { filters: { class: frm.doc.current_class } };
        });
    }
});