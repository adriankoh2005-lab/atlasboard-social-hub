# myapp/templatetags/url_helpers.py
from django import template
from django.urls import reverse
from urllib.parse import urlencode

register = template.Library()

@register.simple_tag
def build_tag_url(tag_id, current_tags, search_query, sort_by, date_from='', date_to=''):
    tags = current_tags.copy()
    tag_id_str = str(tag_id)
    if tag_id_str in tags:
        tags.remove(tag_id_str)
    else:
        tags.append(tag_id_str)
    
    params = []
    for t in tags:
        params.append(('tag', t))
    if search_query:
        params.append(('search', search_query))
    if sort_by:
        params.append(('sort', sort_by))
    if date_from:
        params.append(('date_from', date_from))
    if date_to:
        params.append(('date_to', date_to))
    return '?' + urlencode(params)


@register.simple_tag
def sidebar_item_url(item):
    name = str(getattr(item, 'name', item)).strip().lower()
    mapping = {
        'home': 'index',
        'help': 'help_page',
        'admin center': 'admin_center_page',
        'dashboard': 'dashboard_page',
        'profile': 'profile_page',
        'friends': 'friends_page',
        'chat': 'chat_hub_page',
        'ai helper': 'ai_helper_page',
        'settings': 'settings_page',
        'reports': 'reports_page',
        'collections': 'collections_page',
        'favourites': 'favorites_page',
        'favorites': 'favorites_page',
    }
    route_name = mapping.get(name)
    if route_name:
        return reverse(route_name)

    item_id = getattr(item, 'id', None)
    if item_id:
        return reverse('sidebar_item_detail', args=[item_id])
    return reverse('index')
