from smart_school.portal_utils import get_logged_in_guardian, get_children, get_notification_count

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)

    context.guardian = guardian
    context.children = children
    context.notification_count = get_notification_count(children)
    context.no_cache = 1
