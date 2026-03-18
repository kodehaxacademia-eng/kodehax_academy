import re
from django import template

register = template.Library()

@register.filter(name='assignment_summary')
def assignment_summary(value, assignment_type):
    """
    If the assignment is a coding assignment, strips out everything starting
    from '### Problem' to only show the initial instructions/preamble.
    Otherwise, returns the text as is.
    """
    if not value:
        return ""
        
    if assignment_type == 'code':
        # Split by the first '### Problem' heading
        parts = re.split(r'(?i)###\s+Problem', value, maxsplit=1)
        if parts:
            return parts[0].strip()
            
    return value
