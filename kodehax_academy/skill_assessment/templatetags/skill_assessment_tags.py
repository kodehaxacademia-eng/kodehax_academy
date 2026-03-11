from django import template


register = template.Library()


@register.filter
def get_item(value, key):
    try:
        return value[key]
    except Exception:
        return None


@register.filter
def field_name(prefix, value):
    return f"{prefix}{value}"
