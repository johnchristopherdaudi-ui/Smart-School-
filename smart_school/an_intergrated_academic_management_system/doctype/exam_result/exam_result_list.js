frappe.listview_settings['Exam Result'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__('Upload Wide CSV'), function() {
            let d = new frappe.ui.Dialog({
                title: 'Import Wide Format Results',
                fields: [
                    {
                        label: 'Exam',
                        fieldname: 'exam',
                        fieldtype: 'Link',
                        options: 'Exam',
                        reqd: 1
                    },
                    {
                        fieldname: 'info',
                        fieldtype: 'HTML',
                        options: '<p>CSV format: first column = Student Full Name, remaining columns = Subject names, values = Marks.</p>'
                    },
                    {
                        label: 'CSV File',
                        fieldname: 'file_url',
                        fieldtype: 'Attach',
                        reqd: 1
                    }
                ],
                primary_action_label: 'Upload',
                primary_action(values) {
                    frappe.show_progress('Importing...', 50, 100, 'Processing CSV');

                    frappe.db.get_value('Exam', values.exam, 'class', (r) => {
                        frappe.call({
                            method: 'smart_school.api.import_wide_format_csv',
                            args: {
                                file_url: values.file_url,
                                exam: values.exam,
                                class_name: r.class
                            },
                            callback: function(res) {
                                frappe.hide_progress();
                                let msg = `Created: ${res.message.created}, Skipped: ${res.message.skipped}`;
                                if (res.message.not_found && res.message.not_found.length > 0) {
                                    msg += `<br><br>Students not found:<br>${res.message.not_found.join('<br>')}`;
                                }
                                frappe.msgprint(msg);
                                listview.refresh();
                                d.hide();
                            }
                        });
                    });
                }
            });
            d.show();
        });
    }
};