import json
import re
from difflib import SequenceMatcher, get_close_matches
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone

from .forms import (
    CardCreateForm,
    CardImportForm,
    CardUpdateForm,
    LoginForm,
    RegisterForm,
    SidebarItemForm,
)
from .models import Card, SidebarItem, Tag
from .models import DirectMessage, Friendship, UserPresence
from .services.card_io import import_cards, serialize_cards

DEFAULT_SIDEBAR_ITEMS = [
    'Home',
    'Profile',
    'Dashboard',
    'Friends',
    'Chat',
    'Collections',
    'Favourites',
    'Reports',
    'Admin Center',
    'Settings',
    'AI Helper',
    'Help',
]

SIDEBAR_ORDER = {
    'home': 0,
    'profile': 10,
    'dashboard': 20,
    'friends': 30,
    'chat': 35,
    'collections': 40,
    'favourites': 50,
    'favorites': 50,
    'reports': 60,
    'admin center': 70,
    'settings': 900,
    'ai helper': 950,
    'help': 999,
}


THEME_COOKIE_KEY = 'ui_theme_mode'
REMEMBERED_USERS_COOKIE_KEY = 'atlas_remembered_users'
REMEMBERED_USERS_COOKIE_SALT = 'atlas-remembered-users-v1'
REMEMBERED_USERS_COOKIE_MAX_AGE = 60 * 60 * 24 * 365
AI_HELPER_SESSION_KEY = 'atlas_ai_helper_history'
AI_HELPER_CONTEXT_KEY = 'atlas_ai_helper_context'


def _is_admin(user):
    return user.is_staff or user.is_superuser


def _normalize_theme_mode(value):
    value = str(value or '').strip().lower()
    return value if value in {'light', 'dark'} else 'light'


def _theme_mode_for_request(request):
    return _normalize_theme_mode(request.COOKIES.get(THEME_COOKIE_KEY) or request.session.get('settings_theme_mode'))


def _set_theme_cookie(response, theme_mode):
    response.set_cookie(
        THEME_COOKIE_KEY,
        _normalize_theme_mode(theme_mode),
        samesite='Lax',
    )
    return response


def _load_remembered_usernames(request):
    try:
        raw = request.get_signed_cookie(
            REMEMBERED_USERS_COOKIE_KEY,
            default='[]',
            salt=REMEMBERED_USERS_COOKIE_SALT,
        )
        payload = json.loads(raw)
    except Exception:
        payload = []

    usernames = []
    seen = set()
    for value in payload if isinstance(payload, list) else []:
        username = str(value).strip()
        if not username:
            continue
        lowered = username.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        usernames.append(username[:150])
    return usernames


def _set_remembered_usernames_cookie(response, usernames):
    cleaned = []
    seen = set()
    for value in usernames:
        username = str(value).strip()
        if not username:
            continue
        lowered = username.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned.append(username[:150])
        if len(cleaned) >= 10:
            break

    response.set_signed_cookie(
        REMEMBERED_USERS_COOKIE_KEY,
        json.dumps(cleaned),
        salt=REMEMBERED_USERS_COOKIE_SALT,
        max_age=REMEMBERED_USERS_COOKIE_MAX_AGE,
        samesite='Lax',
    )
    return response


def _remember_username_for_device(response, request, username):
    existing = _load_remembered_usernames(request)
    filtered = [value for value in existing if value.lower() != username.strip().lower()]
    merged = [username.strip()] + filtered
    return _set_remembered_usernames_cookie(response, merged)


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not _is_admin(request.user):
            messages.error(request, 'Admin access required.')
            return redirect('index')
        return view_func(request, *args, **kwargs)

    return _wrapped


def _sidebar_items_for_user(user):
    SidebarItem.objects.filter(name__iexact='Favorites').update(name='Favourites')
    for name in DEFAULT_SIDEBAR_ITEMS:
        SidebarItem.objects.get_or_create(name=name)

    items = list(SidebarItem.objects.all())
    if not _is_admin(user):
        items = [item for item in items if item.name.strip().lower() != 'admin center']

    items.sort(key=lambda item: (SIDEBAR_ORDER.get(item.name.strip().lower(), 500), item.name.lower()))
    return items


def _normalize_tag_names(tags_text):
    if not tags_text:
        return []
    values = [tag.strip() for tag in str(tags_text).split(',')]
    names = []
    seen = set()
    for value in values:
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        names.append(value)
    return names


def _tag_objects_from_text(tags_text):
    names = _normalize_tag_names(tags_text)
    return [Tag.objects.get_or_create(name=name)[0] for name in names]


def _ensure_presence(user):
    presence, _ = UserPresence.objects.get_or_create(user=user)
    return presence


def _filtered_cards(search_query, sort_by, tag_filters, date_from, date_to):
    cards = Card.objects.select_related('owner').prefetch_related('tags').all()

    if search_query:
        cards = cards.filter(
            Q(title__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__icontains=search_query)
            | Q(owner__username__icontains=search_query)
        )

    if tag_filters:
        tag_ids = [int(tid) for tid in tag_filters if tid.isdigit()]
        for tid in tag_ids:
            cards = cards.filter(tags__id=tid)
        cards = cards.distinct()

    parsed_date_from = parse_date(date_from) if date_from else None
    parsed_date_to = parse_date(date_to) if date_to else None
    if parsed_date_from:
        cards = cards.filter(created_at__date__gte=parsed_date_from)
    if parsed_date_to:
        cards = cards.filter(created_at__date__lte=parsed_date_to)

    if sort_by == 'title':
        cards = cards.order_by('title')
    elif sort_by == 'category':
        cards = cards.order_by('category', 'title')
    else:
        sort_by = 'newest'
        cards = cards.order_by('-created_at', '-id')

    return cards, sort_by, parsed_date_from, parsed_date_to


def _ai_helper_history(request):
    history = request.session.get(AI_HELPER_SESSION_KEY, [])
    if not isinstance(history, list):
        history = []

    cleaned = []
    for row in history[-20:]:
        if not isinstance(row, dict):
            continue
        role = str(row.get('role', '')).strip().lower()
        text = str(row.get('text', '')).strip()
        if role not in {'user', 'assistant'} or not text:
            continue
        cleaned.append({'role': role, 'text': text[:1200]})
    return cleaned


def _ai_helper_reply_text(request, message_text):
    text = str(message_text or '').strip()
    lowered = text.lower()
    if not lowered:
        return {'text': 'Ask me anything about AtlasBoard features, navigation, filters, admin tools, or chat.'}

    context = request.session.get(AI_HELPER_CONTEXT_KEY, {})
    if not isinstance(context, dict):
        context = {}
    last_route_name = str(context.get('last_route_name', '')).strip()
    last_route_path = str(context.get('last_route_path', '')).strip()

    tokens = re.findall(r"[a-z0-9']+", lowered)

    def _has_intent(keywords, cutoff=0.78):
        # Direct phrase detection first for multi-word hints.
        if any(keyword in lowered for keyword in keywords if ' ' in keyword):
            return True

        single_keywords = [keyword for keyword in keywords if ' ' not in keyword]
        if any(keyword in tokens for keyword in single_keywords):
            return True

        for token in tokens:
            if len(token) < 3:
                continue
            if single_keywords and get_close_matches(token, single_keywords, n=1, cutoff=cutoff):
                return True
        return False

    route_hints = [
        ('Home', reverse('index'), ['home', 'homepage']),
        ('Dashboard', reverse('dashboard_page'), ['dashboard', 'dashbord', 'dashbaord']),
        ('Profile', reverse('profile_page'), ['profile', 'profle']),
        ('Settings', reverse('settings_page'), ['settings', 'setting', 'setings']),
        ('Friends', reverse('friends_page'), ['friends', 'frends', 'friend']),
        ('Chat', reverse('chat_hub_page'), ['chat', 'message', 'messaging']),
        ('AI Helper', reverse('ai_helper_page'), ['ai', 'helper', 'assistant', 'bot', 'chatbot']),
        ('Collections', reverse('collections_page'), ['collections', 'collection']),
        ('Favourites', reverse('favorites_page'), ['favourite', 'favorite', 'favourites', 'favorites']),
        ('Reports', reverse('reports_page'), ['reports', 'report']),
        ('Admin Center', reverse('admin_center_page'), ['admin center', 'admin', 'moderation', 'moderate']),
        ('Help', reverse('help_page'), ['help', 'guide', 'tutorial']),
    ]
    route_map = {name.lower(): path for name, path, _ in route_hints}

    nav_intent = _has_intent(
        [
            'open',
            'go',
            'go to',
            'goto',
            'navigate',
            'take me',
            'bring me',
            'show me',
            'where is',
            'when is',
            'there',
            'that page',
            'this page',
        ]
    )

    greeting_words = {'hi', 'hello', 'hey', 'yo', 'sup', 'morning', 'afternoon', 'evening'}
    if any(token in greeting_words for token in tokens) and len(tokens) <= 6 and not nav_intent:
        return {
            'text': (
                'Hi. I can help with navigation and usage tips. '
                'Try: "open dashboard", "where is settings", or "how to filter by date".'
            )
        }

    if _has_intent(['thanks', 'thank you', 'thx', 'tq']):
        return {'text': 'You are welcome. If needed, I can navigate you directly to any section.'}

    if _has_intent(['what can you do', 'help me', 'features', 'capabilities']):
        return {
            'text': (
                'I can open pages, explain filters/search/date tools, clarify edit/save behavior, and guide '
                'admin/chat/theme settings. Example: "open friends", "how to filter by date", "is edit auto-saved?".'
            )
        }

    if nav_intent and _has_intent(['there', 'that page', 'this page']) and last_route_name and last_route_path:
        return {
            'text': f'Taking you back to {last_route_name} now.',
            'navigate_to': last_route_path,
            'navigate_label': last_route_name,
        }

    if _has_intent(['save', 'autosave', 'auto save', 'cancel', 'edit mode', 'edit', 'undo']):
        return {
            'text': (
                'Edits are not auto-saved when you close edit mode. Use Save buttons to apply changes; turning edit '
                'mode off cancels unsaved edits. Admin tables also support Undo while editing.'
            )
        }

    matched_route = None
    for name, path, keywords in route_hints:
        if _has_intent(keywords):
            matched_route = (name, path)
            break

    if matched_route:
        name, path = matched_route
        if name == 'Admin Center' and not _is_admin(request.user):
            return {
                'text': 'Admin Center is restricted to admin accounts. I can take you to Help or Dashboard instead.'
            }
        if nav_intent:
            prefix = 'Looks like you meant "where is". ' if 'when is' in lowered and 'where is' not in lowered else ''
            return {
                'text': f'{prefix}Taking you to {name} now.',
                'navigate_to': path,
                'navigate_label': name,
                'context': {'last_route_name': name, 'last_route_path': path},
            }
        return {'text': f'Open {name} at {path}. If you want, I can explain the main actions there.'}

    if nav_intent:
        suggestion_names = ', '.join([name.lower() for name, _, _ in route_hints if name != 'Admin Center'])
        return {
            'text': (
                f'I could not match that destination. Try one of these: {suggestion_names}.'
            )
        }

    if _has_intent(['filter', 'search', 'sort', 'date', 'find', 'lookup']):
        return {
            'text': (
                'Use Home or Collections: type in Search, pick Sort, choose Date From/To, and apply tags from the '
                'sidebar. Use Clear Filters to reset quickly.'
            )
        }

    if _has_intent(['admin', 'moderate', 'moderation', 'user role', 'post moderation', 'administrator']):
        admin_hint = 'As admin, use Admin Center table toggles, edit rows, then press Save for each section.'
        if not _is_admin(request.user):
            admin_hint += ' Your current account is not admin, so that page is restricted.'
        return {'text': admin_hint}

    if _has_intent(['dark mode', 'theme', 'light mode', 'mode']):
        return {
            'text': (
                'Change theme in Settings, or use the Dark Mode quick button on the right side below the Friends panel.'
            )
        }

    if _has_intent(['remember me', 'login', 'password', 'signin', 'sign in']):
        return {
            'text': 'Use Remember me at login to keep session longer. Browser autofill handles password suggestions securely.'
        }

    if _has_intent(['count', 'total', 'stats', 'how many', 'numbers', 'summary']):
        return {
            'text': (
                f"Current totals: posts {Card.objects.count()}, tags {Tag.objects.count()}, users {User.objects.count()}."
                ' Open Dashboard for more detail.'
            )
        }

    known_terms = [
        'home',
        'dashboard',
        'profile',
        'settings',
        'friends',
        'chat',
        'ai helper',
        'collections',
        'favourites',
        'reports',
        'admin center',
        'help',
        'filter',
        'search',
        'sort',
        'date',
        'admin',
        'dark mode',
        'theme',
        'remember me',
        'login',
        'password',
        'stats',
        'save',
        'edit mode',
        'autosave',
    ]
    best_match = None
    best_score = 0.0
    for token in tokens:
        for term in known_terms:
            score = SequenceMatcher(None, token, term).ratio()
            if score > best_score:
                best_score = score
                best_match = term

    if best_match and best_score >= 0.7:
        if best_match in route_map:
            guessed_path = route_map[best_match]
            guessed_name = best_match.title()
            return {
                'text': f'I think you meant "{guessed_name}". Want me to open it?',
                'navigate_to': guessed_path,
                'navigate_label': guessed_name,
                'context': {'last_route_name': guessed_name, 'last_route_path': guessed_path},
            }
        return {
            'text': (
                f'I might have misunderstood that. Did you mean "{best_match}"? '
                'Try asking in short form, for example: "How do I filter by date?"'
            )
        }

    return {
        'text': (
            "I couldn't clearly detect the intent. Please rephrase with a short request. "
            'Examples: "open dashboard", "where is settings", "how does remember me work".'
        )
    }


def login_page(request):
    if request.user.is_authenticated:
        return redirect('index')
    remembered_usernames = _load_remembered_usernames(request)

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            remember_me = bool(request.POST.get('remember_me'))
            if remember_me:
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)
            _ensure_presence(user)
            request.session['tab_session_seed'] = True
            theme_mode = _normalize_theme_mode(request.COOKIES.get(THEME_COOKIE_KEY))
            request.session['settings_theme_mode'] = theme_mode
            messages.success(request, 'Logged in successfully.')
            response = redirect('index')
            return _remember_username_for_device(response, request, user.username)
    else:
        form = LoginForm(request)

    return render(
        request,
        'myapp/login.html',
        {'form': form, 'page_title': 'Login', 'remembered_usernames': remembered_usernames},
    )


def register_page(request):
    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            if User.objects.count() == 1:
                user.is_staff = True
                user.save(update_fields=['is_staff'])
            login(request, user)
            _ensure_presence(user)
            request.session['tab_session_seed'] = True
            theme_mode = _normalize_theme_mode(request.COOKIES.get(THEME_COOKIE_KEY))
            request.session['settings_theme_mode'] = theme_mode
            messages.success(request, 'Account created. Welcome to AtlasBoard.')
            response = redirect('index')
            return _remember_username_for_device(response, request, user.username)
    else:
        form = RegisterForm()

    return render(request, 'myapp/register.html', {'form': form, 'page_title': 'Register'})


@login_required
def logout_page(request):
    logout(request)
    return redirect('login_page')


@login_required
def index(request):
    _ensure_presence(request.user)
    sidebar_items = _sidebar_items_for_user(request.user)
    tags = Tag.objects.all().order_by('name')

    search_query = request.GET.get('search', '').strip()
    default_sort = request.session.get('settings_default_sort', 'newest')
    sort_by = request.GET.get('sort', default_sort).strip()
    tag_filters = request.GET.getlist('tag')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    cards, sort_by, parsed_date_from, parsed_date_to = _filtered_cards(
        search_query,
        sort_by,
        tag_filters,
        date_from,
        date_to,
    )

    context = {
        'sidebar_items': sidebar_items,
        'tags': tags,
        'cards': cards,
        'search_query': search_query,
        'sort_by': sort_by,
        'tag_filters': tag_filters,
        'date_from': parsed_date_from.isoformat() if parsed_date_from else '',
        'date_to': parsed_date_to.isoformat() if parsed_date_to else '',
        'card_form': CardCreateForm(),
        'import_form': CardImportForm(),
        'current_section': 'home',
    }
    return render(request, 'myapp/index.html', context)


@login_required
def help_page(request):
    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Help',
        'page_description': 'Quick introduction and practical guide to using AtlasBoard.',
        'current_section': 'help',
        'help_sections': [
            (
                'Home',
                'Use search, sorting, tag filters, and date range filters to find posts quickly. Turn on the Edit Cards toggle on the search row, update fields, and press Save. Turning edit mode off cancels unsaved edits.',
            ),
            (
                'Card Detail',
                'Click a card title to open the full post page, including tags, timestamps, and related posts.',
            ),
            (
                'Dashboard',
                'See totals and your latest content updates at a glance.',
            ),
            (
                'Profile',
                'Update your display name and account details.',
            ),
            (
                'Friends',
                'Add friends by username and quickly check online/offline status.',
            ),
            (
                'Chat',
                'Choose a friend and open a conversation from the Chat page. Use close chatbox, share cards into chat, and track status ticks (sent, delivered, read).',
            ),
            (
                'AI Helper',
                'Use the AI quick button to open the chatbox. It supports greetings, typo-tolerant requests, follow-up commands like "go there", and direct navigation such as "open dashboard" or "where is settings".',
            ),
            (
                'Unread Alerts',
                'Chat shows red dot notifications for unread messages in sidebar and friend lists.',
            ),
            (
                'Delete Messages',
                'Delete for me hides only for you. Delete for all (sender only) removes the message for both users.',
            ),
            (
                'Settings',
                'Choose your default post sort and theme (Light or Dark), then save app preferences.',
            ),
            (
                'Quick Theme Toggle',
                'Use the Dark Mode quick button in the right panel, below the Friends box, to switch instantly from any page.',
            ),
            (
                'Theme Persistence',
                'Theme mode persists during the current open browser session, including logout/login. After closing browser windows and reopening, it resets to normal light.',
            ),
            (
                'Remember Me',
                'On login, check Remember me to keep account session longer. Leave it unchecked to end session on browser close. This device remembers previously used usernames, and browser autofill shows native account/password suggestions.',
            ),
            (
                'Session Security',
                'For safety, login is tab-scoped. Opening a new browser session can require signing in again.',
            ),
            (
                'Reports',
                'View post totals grouped by category for quick insights.',
            ),
            (
                'Collections',
                'Browse and search all posts in a focused list page.',
            ),
            (
                'Favourites',
                'Shows posts tagged or categorized as Favourites.',
            ),
            (
                'Admin Center',
                'For admins: manage users and moderate posts using separate table edit toggles, explicit Save buttons, Undo controls, and author/search filters.',
            ),
        ],
    }
    return render(request, 'myapp/help.html', context)


@login_required
def ai_helper_page(request):
    history = _ai_helper_history(request)
    if not history:
        history = [
            {
                'role': 'assistant',
                'text': (
                    'Hi, I am AtlasBoard AI Helper. Ask me about pages, filters, chat, admin tools,'
                    ' dark mode, or login settings.'
                ),
            }
        ]
        request.session[AI_HELPER_SESSION_KEY] = history

    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'AI Helper',
        'page_description': 'Ask for quick guidance about app features and usage.',
        'current_section': 'ai helper',
        'ai_history': history,
    }
    return render(request, 'myapp/ai_helper.html', context)


@login_required
def ai_helper_reply(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    message_text = request.POST.get('message', '').strip()
    if not message_text:
        return JsonResponse({'ok': False, 'error': 'Message cannot be empty.'}, status=400)

    history = _ai_helper_history(request)
    history.append({'role': 'user', 'text': message_text[:1200]})
    assistant_payload = _ai_helper_reply_text(request, message_text)
    assistant_text = str(assistant_payload.get('text', '') if isinstance(assistant_payload, dict) else assistant_payload).strip()
    navigate_to = str(assistant_payload.get('navigate_to', '') if isinstance(assistant_payload, dict) else '').strip()
    navigate_label = str(assistant_payload.get('navigate_label', '') if isinstance(assistant_payload, dict) else '').strip()
    context_update = assistant_payload.get('context', {}) if isinstance(assistant_payload, dict) else {}
    if not assistant_text:
        assistant_text = 'I could not generate a reply. Please try again.'
    history.append({'role': 'assistant', 'text': assistant_text[:1200]})
    request.session[AI_HELPER_SESSION_KEY] = history[-20:]
    if isinstance(context_update, dict) and context_update:
        merged_context = request.session.get(AI_HELPER_CONTEXT_KEY, {})
        if not isinstance(merged_context, dict):
            merged_context = {}
        merged_context.update(
            {
                'last_route_name': str(context_update.get('last_route_name', merged_context.get('last_route_name', '')))[:100],
                'last_route_path': str(context_update.get('last_route_path', merged_context.get('last_route_path', '')))[:255],
            }
        )
        request.session[AI_HELPER_CONTEXT_KEY] = merged_context

    return JsonResponse(
        {
            'ok': True,
            'reply': assistant_text,
            'navigate_to': navigate_to,
            'navigate_label': navigate_label,
        }
    )


@login_required
def dashboard_page(request):
    stats = {
        'Total Posts': Card.objects.count(),
        'Total Tags': Tag.objects.count(),
        'Total Users': User.objects.count(),
        'My Posts': Card.objects.filter(owner=request.user).count(),
    }
    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Dashboard',
        'page_description': 'Overview of your content and app data.',
        'stats': stats,
        'cards': Card.objects.select_related('owner').order_by('-created_at')[:8],
        'current_section': 'dashboard',
    }
    return render(request, 'myapp/dashboard.html', context)


@login_required
def profile_page(request):
    if request.method == 'POST':
        display_name = request.POST.get('display_name', '').strip()
        if display_name:
            request.user.first_name = display_name
            request.user.save(update_fields=['first_name'])
            messages.success(request, 'Profile display name updated.')
        else:
            messages.error(request, 'Display name cannot be empty.')
        return redirect('profile_page')

    display_name = request.user.first_name or request.user.username
    role = 'Admin' if _is_admin(request.user) else 'User'
    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Profile',
        'page_description': 'Profile area for account-related information.',
        'display_name': display_name,
        'info_rows': [
            ('Username', request.user.username),
            ('Display Name', display_name),
            ('Role', role),
            ('Joined', request.user.date_joined.strftime('%Y-%m-%d')),
        ],
        'current_section': 'profile',
    }
    return render(request, 'myapp/profile.html', context)


@login_required
def settings_page(request):
    current_theme_mode = _theme_mode_for_request(request)
    if request.method == 'POST':
        sort_choice = request.POST.get('default_sort', 'newest').strip()
        if sort_choice not in {'newest', 'title', 'category'}:
            sort_choice = 'newest'
        theme_mode = _normalize_theme_mode(request.POST.get('theme_mode', current_theme_mode))

        request.session['settings_default_sort'] = sort_choice
        request.session['settings_sidebar_tips'] = bool(request.POST.get('sidebar_tips'))
        request.session['settings_theme_mode'] = theme_mode
        messages.success(request, 'Settings saved.')
        response = redirect('settings_page')
        return _set_theme_cookie(response, theme_mode)

    default_sort = request.session.get('settings_default_sort', 'newest')
    sidebar_tips = request.session.get('settings_sidebar_tips', True)
    theme_mode = current_theme_mode
    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Settings',
        'page_description': 'Settings section for app configuration and preferences.',
        'show_page_edit_toggle': False,
        'default_sort': default_sort,
        'sidebar_tips': sidebar_tips,
        'theme_mode': theme_mode,
        'info_rows': [
            ('Theme', theme_mode.title()),
            ('Default Sort', default_sort.title()),
            ('Sidebar Tips', 'Enabled' if sidebar_tips else 'Disabled'),
        ],
        'current_section': 'settings',
    }
    return render(request, 'myapp/settings.html', context)


def set_theme_mode(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    raw_theme_mode = request.POST.get('theme_mode', '').strip().lower()
    if raw_theme_mode not in {'light', 'dark'}:
        return JsonResponse({'ok': False, 'error': 'Invalid theme mode'}, status=400)
    theme_mode = _normalize_theme_mode(raw_theme_mode)

    request.session['settings_theme_mode'] = theme_mode
    response = JsonResponse({'ok': True, 'theme_mode': theme_mode})
    return _set_theme_cookie(response, theme_mode)


@login_required
def reports_page(request):
    category_totals = Card.objects.values('category').annotate(total=Count('id')).order_by('-total', 'category')
    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Reports',
        'page_description': 'Post totals grouped by category.',
        'report_rows': category_totals,
        'current_section': 'reports',
    }
    return render(request, 'myapp/reports.html', context)


@login_required
def collections_page(request):
    query = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    cards = Card.objects.select_related('owner').order_by('category', 'title')
    if query:
        cards = cards.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(category__icontains=query)
            | Q(owner__username__icontains=query)
        )

    parsed_date_from = parse_date(date_from) if date_from else None
    parsed_date_to = parse_date(date_to) if date_to else None
    if parsed_date_from:
        cards = cards.filter(created_at__date__gte=parsed_date_from)
    if parsed_date_to:
        cards = cards.filter(created_at__date__lte=parsed_date_to)

    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Collections',
        'page_description': 'Browse and search all posts.',
        'cards': cards,
        'query': query,
        'date_from': parsed_date_from.isoformat() if parsed_date_from else '',
        'date_to': parsed_date_to.isoformat() if parsed_date_to else '',
        'current_section': 'collections',
    }
    return render(request, 'myapp/collections.html', context)


@login_required
def friends_page(request):
    query = request.GET.get('q', '').strip()

    friend_ids = Friendship.objects.filter(user=request.user).values_list('friend_id', flat=True)
    friends = User.objects.filter(id__in=friend_ids).select_related('presence').order_by('username')

    people = User.objects.exclude(id=request.user.id).exclude(id__in=friend_ids).order_by('username')
    if query:
        people = people.filter(username__icontains=query)

    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Friends',
        'page_description': 'Manage your friend list and see who is online.',
        'current_section': 'friends',
        'friends': friends,
        'people': people[:40],
        'query': query,
    }
    return render(request, 'myapp/friends.html', context)


@login_required
def favorites_page(request):
    favorite_cards = Card.objects.select_related('owner').filter(
        Q(tags__name__iexact='favorites')
        | Q(tags__name__iexact='favourites')
        | Q(category__iexact='favorites')
        | Q(category__iexact='favourites')
    ).distinct()
    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Favourites',
        'page_description': 'Your favourite posts.',
        'cards': favorite_cards,
        'current_section': 'favourites',
    }
    return render(request, 'myapp/favorites.html', context)


@login_required
def chat_hub_page(request):
    friend_ids = list(Friendship.objects.filter(user=request.user).values_list('friend_id', flat=True))
    friends = User.objects.filter(id__in=friend_ids).select_related('presence').order_by('username')

    selected_friend = None
    chat_messages = DirectMessage.objects.none()
    selected_friend_id_raw = request.GET.get('friend', '').strip()

    if selected_friend_id_raw.isdigit():
        candidate = friends.filter(id=int(selected_friend_id_raw)).first()
        if candidate:
            selected_friend = candidate

    # Receiver reached the app, mark incoming messages as delivered.
    DirectMessage.objects.filter(receiver=request.user, delivered_at__isnull=True).exclude(hidden_for=request.user).update(
        delivered_at=timezone.now()
    )

    if request.method == 'POST':
        friend_id = request.POST.get('friend_id', '').strip()
        text = request.POST.get('message', '').strip()

        if not friend_id.isdigit():
            messages.error(request, 'Choose a friend to chat with.')
            return redirect('chat_hub_page')

        selected_friend = friends.filter(id=int(friend_id)).first()
        if not selected_friend:
            messages.error(request, 'You can only chat with users in your friend list.')
            return redirect('chat_hub_page')

        if not text:
            messages.error(request, 'Message cannot be empty.')
            return redirect(f"{redirect('chat_hub_page').url}?friend={selected_friend.id}")

        DirectMessage.objects.create(sender=request.user, receiver=selected_friend, body=text)
        return redirect(f"{redirect('chat_hub_page').url}?friend={selected_friend.id}")

    if selected_friend:
        DirectMessage.objects.filter(
            sender=selected_friend,
            receiver=request.user,
            is_read=False,
        ).exclude(hidden_for=request.user).update(
            delivered_at=timezone.now(),
            is_read=True,
            read_at=timezone.now(),
        )

        chat_messages = DirectMessage.objects.filter(
            (Q(sender=request.user, receiver=selected_friend)) | (Q(sender=selected_friend, receiver=request.user))
        ).exclude(hidden_for=request.user).select_related('sender', 'receiver')

    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Chat',
        'page_description': 'Choose a friend and chat in real time style view.',
        'current_section': 'chat',
        'friends': friends,
        'selected_friend': selected_friend,
        'chat_messages': chat_messages,
    }
    return render(request, 'myapp/chat_hub.html', context)


@login_required
def delete_chat_message(request, message_id):
    if request.method != 'POST':
        return redirect('chat_hub_page')

    message = get_object_or_404(DirectMessage.objects.select_related('sender', 'receiver'), pk=message_id)
    if request.user.id not in {message.sender_id, message.receiver_id}:
        return HttpResponseForbidden('You do not have permission to delete this message.')

    other_user_id = message.receiver_id if request.user.id == message.sender_id else message.sender_id
    scope = request.POST.get('scope', '').strip().lower()

    if request.user.id == message.sender_id and scope == 'for_me':
        message.hidden_for.add(request.user)
        messages.success(request, 'Message deleted for you.')
    elif request.user.id == message.sender_id:
        message.delete()
        messages.success(request, 'Message deleted for everyone.')
    else:
        message.hidden_for.add(request.user)
        messages.success(request, 'Message deleted for you.')

    return redirect(f"{reverse('chat_hub_page')}?friend={other_user_id}")


@login_required
def chat_page(request, friend_id):
    return redirect(f"{redirect('chat_hub_page').url}?friend={friend_id}")


@login_required
def add_card(request):
    if request.method != 'POST':
        return redirect('index')

    form = CardCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Could not add post. Please check form values.')
        return redirect('index')

    data = form.cleaned_data
    card = Card.objects.create(
        title=data['title'].strip(),
        description=data['description'].strip(),
        category=data['category'].strip(),
        owner=request.user,
    )
    card.tags.set(_tag_objects_from_text(data.get('tags', '')))

    messages.success(request, 'Post created.')
    return redirect('index')


@login_required
def card_detail(request, card_id):
    card = get_object_or_404(Card.objects.select_related('owner').prefetch_related('tags'), pk=card_id)
    related_cards = Card.objects.select_related('owner').filter(category__iexact=card.category).exclude(pk=card.id)[:6]

    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': card.title,
        'page_description': 'Post details',
        'current_section': 'home',
        'card': card,
        'related_cards': related_cards,
    }
    return render(request, 'myapp/card_detail.html', context)


@login_required
def edit_card(request, card_id):
    card = get_object_or_404(Card.objects.prefetch_related('tags'), pk=card_id)
    can_manage = _is_admin(request.user) or (card.owner_id == request.user.id)
    if not can_manage:
        return HttpResponseForbidden('You do not have permission to edit this post.')

    if request.method == 'POST':
        form = CardUpdateForm(request.POST, instance=card)
        if form.is_valid():
            updated_card = form.save()
            updated_card.tags.set(_tag_objects_from_text(form.cleaned_data.get('tags', '')))
            messages.success(request, 'Post updated.')
            return redirect('index')
    else:
        form = CardUpdateForm(
            instance=card,
            initial={'tags': ', '.join(card.tags.values_list('name', flat=True))},
        )

    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Edit Post',
        'page_description': 'Update your post details.',
        'current_section': 'home',
        'form': form,
        'card': card,
    }
    return render(request, 'myapp/card_edit.html', context)


@login_required
def delete_card(request, card_id):
    if request.method != 'POST':
        return redirect('index')

    card = get_object_or_404(Card, pk=card_id)
    can_manage = _is_admin(request.user) or (card.owner_id == request.user.id)
    if not can_manage:
        return HttpResponseForbidden('You do not have permission to delete this post.')

    card.delete()
    messages.success(request, 'Post deleted.')
    return redirect('index')


@staff_required
def export_cards_json(request):
    cards = Card.objects.order_by('-created_at', '-id')
    return JsonResponse({'cards': serialize_cards(cards)})


@staff_required
def import_cards_json(request):
    if request.method != 'POST':
        return redirect('index')

    form = CardImportForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Import failed. Submit valid JSON data.')
        return redirect('index')

    try:
        raw_payload = json.loads(form.cleaned_data['payload'])
    except json.JSONDecodeError:
        messages.error(request, 'Import failed. JSON format is invalid.')
        return redirect('index')

    if isinstance(raw_payload, dict):
        cards_payload = raw_payload.get('cards', [])
    elif isinstance(raw_payload, list):
        cards_payload = raw_payload
    else:
        cards_payload = []

    if not isinstance(cards_payload, list):
        messages.error(request, 'Import failed. JSON must contain a list of cards.')
        return redirect('index')

    result = import_cards(
        cards_payload,
        replace_existing=form.cleaned_data.get('replace_existing', False),
    )

    messages.success(
        request,
        (
            'Import complete. '
            f"Created: {result['created']}, updated: {result['updated']}, skipped: {result['skipped']}."
        ),
    )
    return redirect('index')


@staff_required
def admin_center_page(request):
    for user_obj in User.objects.all():
        _ensure_presence(user_obj)
    preferred_usernames = ['Adrian', 'Adrian2005', 'A', 'B', 'C', 'D']
    preferred_map = {user.username: user for user in User.objects.filter(username__in=preferred_usernames)}
    owner_pool = [preferred_map[name] for name in preferred_usernames if name in preferred_map]
    if not owner_pool:
        owner_pool = list(User.objects.order_by('username'))

    ownerless_cards = list(Card.objects.filter(owner__isnull=True).order_by('id'))
    if owner_pool and ownerless_cards:
        for index, card in enumerate(ownerless_cards):
            card.owner = owner_pool[index % len(owner_pool)]
        Card.objects.bulk_update(ownerless_cards, ['owner'])

    card_filter_query = request.GET.get('q', '').strip()
    card_filter_author = request.GET.get('author', '').strip()
    cards = Card.objects.select_related('owner').prefetch_related('tags').order_by('-created_at', '-id')

    if card_filter_query:
        cards = cards.filter(
            Q(title__icontains=card_filter_query)
            | Q(description__icontains=card_filter_query)
            | Q(category__icontains=card_filter_query)
            | Q(owner__username__icontains=card_filter_query)
        )

    if card_filter_author == 'unassigned':
        cards = cards.filter(owner__isnull=True)
    elif card_filter_author.isdigit():
        cards = cards.filter(owner_id=int(card_filter_author))

    card_owner_options = User.objects.order_by('username')

    context = {
        'sidebar_items': _sidebar_items_for_user(request.user),
        'page_title': 'Admin Center',
        'page_description': 'Moderate posts, manage users, and grant admin privileges.',
        'show_page_edit_toggle': False,
        'current_section': 'admin center',
        'users': User.objects.select_related('presence').order_by('username'),
        'cards': cards,
        'card_owner_options': card_owner_options,
        'card_filter_query': card_filter_query,
        'card_filter_author': card_filter_author,
    }
    return render(request, 'myapp/admin_center.html', context)


@staff_required
def promote_user_admin(request, user_id):
    if request.method != 'POST':
        return redirect('admin_center_page')

    user = get_object_or_404(User, pk=user_id)
    if not user.is_staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])
        messages.success(request, f'{user.username} promoted to admin.')
    else:
        messages.info(request, f'{user.username} is already an admin.')
    return redirect('admin_center_page')


@staff_required
def admin_create_user(request):
    if request.method != 'POST':
        return redirect('admin_center_page')

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '').strip()
    role = request.POST.get('role', 'user').strip().lower()

    if not username or not password:
        messages.error(request, 'Username and password are required.')
        return redirect('admin_center_page')

    if User.objects.filter(username=username).exists():
        messages.error(request, 'Username already exists.')
        return redirect('admin_center_page')

    user = User.objects.create_user(username=username, password=password)
    if role == 'admin':
        user.is_staff = True
        user.save(update_fields=['is_staff'])

    messages.success(request, f'User {username} created.')
    return redirect('admin_center_page')


@staff_required
def admin_update_user(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    user = get_object_or_404(User, pk=user_id)
    role = request.POST.get('role', '').strip().lower()
    is_active_raw = request.POST.get('is_active', '1').strip().lower()
    is_active = is_active_raw in {'1', 'true', 'on', 'yes'}
    is_online_raw = request.POST.get('is_online', '0').strip().lower()
    is_online = is_online_raw in {'1', 'true', 'on', 'yes'}

    if role not in {'admin', 'user'}:
        return JsonResponse({'ok': False, 'error': 'Invalid role'}, status=400)

    if user == request.user and role == 'user':
        return JsonResponse({'ok': False, 'error': 'You cannot remove your own admin access.'}, status=400)

    if user.is_superuser and role == 'user':
        return JsonResponse({'ok': False, 'error': 'Superuser role cannot be downgraded here.'}, status=400)

    user.is_staff = role == 'admin' or user.is_superuser
    user.is_active = is_active
    user.save(update_fields=['is_staff', 'is_active'])
    presence = _ensure_presence(user)
    presence.is_online = is_online
    presence.save(update_fields=['is_online', 'updated_at'])

    return JsonResponse(
        {
            'ok': True,
            'username': user.username,
            'is_staff': user.is_staff,
            'is_active': user.is_active,
            'is_online': presence.is_online,
        }
    )


@login_required
def add_friend(request):
    if request.method != 'POST':
        return redirect('index')

    username = request.POST.get('username', '').strip()
    if not username:
        messages.error(request, 'Enter a username to add friend.')
        return redirect(request.META.get('HTTP_REFERER') or 'index')

    friend = User.objects.filter(username__iexact=username).first()
    if not friend:
        messages.error(request, 'User not found.')
        return redirect(request.META.get('HTTP_REFERER') or 'index')

    if friend.id == request.user.id:
        messages.error(request, 'You cannot add yourself as friend.')
        return redirect(request.META.get('HTTP_REFERER') or 'index')

    if Friendship.objects.filter(user=request.user, friend=friend).exists():
        messages.info(request, f'{friend.username} is already your friend.')
        return redirect(request.META.get('HTTP_REFERER') or 'index')

    Friendship.objects.get_or_create(user=request.user, friend=friend)
    Friendship.objects.get_or_create(user=friend, friend=request.user)
    messages.success(request, f'{friend.username} added as friend.')
    return redirect(request.META.get('HTTP_REFERER') or 'index')


@login_required
def remove_friend(request, friend_id):
    if request.method != 'POST':
        return redirect('index')

    friend = get_object_or_404(User, pk=friend_id)
    Friendship.objects.filter(user=request.user, friend=friend).delete()
    Friendship.objects.filter(user=friend, friend=request.user).delete()
    messages.success(request, f'{friend.username} removed from friends.')
    return redirect(request.META.get('HTTP_REFERER') or 'index')


@login_required
def share_card_to_chat(request, card_id):
    if request.method != 'POST':
        return redirect('index')

    card = get_object_or_404(Card, pk=card_id)
    friend_id = request.POST.get('friend_id', '').strip()
    if not friend_id.isdigit():
        messages.error(request, 'Choose a friend to share with.')
        return redirect(request.META.get('HTTP_REFERER') or 'index')

    friend = User.objects.filter(pk=int(friend_id)).first()
    if not friend:
        messages.error(request, 'Friend not found.')
        return redirect(request.META.get('HTTP_REFERER') or 'index')

    if not Friendship.objects.filter(user=request.user, friend=friend).exists():
        messages.error(request, 'You can only share posts with users in your friend list.')
        return redirect(request.META.get('HTTP_REFERER') or 'index')

    description = (card.description or '').strip()
    if len(description) > 180:
        description = f'{description[:177]}...'

    body = (
        f"[Shared Post]\n"
        f"Title: {card.title}\n"
        f"Category: {card.category}\n"
        f"{description}\n"
        f"Post ID: {card.id}"
    )
    DirectMessage.objects.create(sender=request.user, receiver=friend, body=body)

    messages.success(request, f'Shared "{card.title}" with {friend.username}.')
    return redirect(f"{reverse('chat_hub_page')}?friend={friend.id}")


@staff_required
def admin_update_card(request, card_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    card = get_object_or_404(Card, pk=card_id)
    title = request.POST.get('title', '').strip()
    description = request.POST.get('description', '').strip()
    category = request.POST.get('category', '').strip()
    tags_text = request.POST.get('tags', '').strip()
    owner_id_raw = request.POST.get('owner_id', '').strip()

    if not title or not description or not category:
        return JsonResponse({'ok': False, 'error': 'Title, description, and category are required.'}, status=400)

    owner = None
    if owner_id_raw:
        if not owner_id_raw.isdigit():
            return JsonResponse({'ok': False, 'error': 'Invalid owner selection.'}, status=400)
        owner = User.objects.filter(pk=int(owner_id_raw)).first()
        if not owner:
            return JsonResponse({'ok': False, 'error': 'Selected owner was not found.'}, status=400)

    card.title = title
    card.description = description
    card.category = category
    card.owner = owner
    card.save(update_fields=['title', 'description', 'category', 'owner', 'updated_at'])
    card.tags.set(_tag_objects_from_text(tags_text))

    return JsonResponse(
        {
            'ok': True,
            'id': card.id,
            'title': card.title,
            'owner_id': card.owner_id,
            'owner_username': card.owner.username if card.owner else 'Unassigned',
            'category': card.category,
            'tags': ', '.join(card.tags.values_list('name', flat=True)),
            'updated_at': card.updated_at.strftime('%Y-%m-%d %H:%M'),
        }
    )


@staff_required
def admin_delete_card(request, card_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    card = get_object_or_404(Card, pk=card_id)
    card.delete()
    return JsonResponse({'ok': True, 'id': card_id})


@staff_required
def sidebar_items_page(request):
    items = _sidebar_items_for_user(request.user)
    context = {
        'sidebar_items': items,
        'sidebar_form': SidebarItemForm(),
        'current_section': 'admin center',
    }
    return render(request, 'myapp/sidebar_items.html', context)


@login_required
def sidebar_item_detail(request, item_id):
    item = get_object_or_404(SidebarItem, pk=item_id)
    related_cards = Card.objects.select_related('owner').filter(category__iexact=item.name).order_by('-created_at')
    context = {
        'item': item,
        'related_cards': related_cards,
        'sidebar_form': SidebarItemForm(instance=item),
    }
    return render(request, 'myapp/sidebar_item_detail.html', context)


@staff_required
def sidebar_item_add(request):
    if request.method != 'POST':
        return redirect('sidebar_items_page')

    form = SidebarItemForm(request.POST)
    if not form.is_valid():
        messages.error(request, form.errors.get('name', ['Could not add sidebar item.'])[0])
        return redirect('sidebar_items_page')

    item = form.save()
    messages.success(request, f"Sidebar item '{item.name}' added.")
    return redirect('sidebar_items_page')


@staff_required
def sidebar_item_update(request, item_id):
    if request.method != 'POST':
        return redirect('sidebar_items_page')

    item = get_object_or_404(SidebarItem, pk=item_id)
    form = SidebarItemForm(request.POST, instance=item)
    if not form.is_valid():
        messages.error(request, form.errors.get('name', ['Could not update sidebar item.'])[0])
        return redirect('sidebar_items_page')

    form.save()
    messages.success(request, 'Sidebar item updated.')
    return redirect('sidebar_items_page')


@staff_required
def sidebar_item_delete(request, item_id):
    if request.method != 'POST':
        return redirect('sidebar_items_page')

    item = get_object_or_404(SidebarItem, pk=item_id)
    item_name = item.name
    item.delete()
    messages.success(request, f"Sidebar item '{item_name}' deleted.")
    return redirect('sidebar_items_page')
