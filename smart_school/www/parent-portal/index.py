from smart_school.portal_utils import get_logged_in_guardian, get_children, get_notifications

def get_context(context):
    guardian = get_logged_in_guardian()
    children = get_children(guardian)

    context.guardian = guardian
    context.children = children
    context.notifications = get_notifications(children)
    context.no_cache = 1
