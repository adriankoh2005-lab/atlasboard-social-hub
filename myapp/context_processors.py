from django.db.models import Count

from .models import DirectMessage, Friendship, UserPresence


def tab_session_seed(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'session_seed': False}
    return {'session_seed': bool(request.session.pop('tab_session_seed', False))}


def friends_panel(request):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {'friends_panel_items': [], 'chat_unread_total': 0}

    UserPresence.objects.get_or_create(user=request.user)
    friendships = Friendship.objects.filter(user=request.user).select_related('friend', 'friend__presence')
    friend_ids = [relation.friend_id for relation in friendships]

    unread_map = {}
    if friend_ids:
        unread_rows = (
            DirectMessage.objects.filter(
                receiver=request.user,
                is_read=False,
                sender_id__in=friend_ids,
            )
            .exclude(hidden_for=request.user)
            .values('sender_id')
            .annotate(total=Count('id'))
        )
        unread_map = {row['sender_id']: row['total'] for row in unread_rows}

    items = []
    for relation in friendships:
        presence = getattr(relation.friend, 'presence', None)
        unread_count = unread_map.get(relation.friend_id, 0)
        items.append(
            {
                'id': relation.friend.id,
                'username': relation.friend.username,
                'is_online': bool(presence and presence.is_online),
                'unread_count': unread_count,
            }
        )

    items.sort(key=lambda item: (item['unread_count'] == 0, not item['is_online'], item['username'].lower()))
    chat_unread_total = sum(item['unread_count'] for item in items)
    return {'friends_panel_items': items, 'chat_unread_total': chat_unread_total}


def ui_theme_mode(request):
    theme_mode = request.COOKIES.get('ui_theme_mode') or request.session.get('settings_theme_mode') or 'light'
    if theme_mode not in {'light', 'dark'}:
        theme_mode = 'light'
    return {'ui_theme_mode': theme_mode}
