from django import template
from urllib.parse import urlencode, parse_qs

register = template.Library()

@register.filter
def remove_param(url, param):
    """
    Remove a parameter from a URL query string
    """
    if not url:
        return ''
    
    # Parse the query string
    params = parse_qs(url)
    
    # Remove the specified parameter
    if param in params:
        del params[param]
    
    # Rebuild the query string
    return urlencode(params, doseq=True)

@register.filter
def status_badge_class(status):
    status_classes = {
        'pending': 'warning',
        'active': 'success',
        'completed': 'info',
        'cancelled': 'danger'
    }
    return status_classes.get(status.lower(), 'secondary') 