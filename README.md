# atlasboard-social-hub
A Django social app with cards, friends, chat, admin moderation, AI helper, filters and responsive UI.

# AtlasBoard Social Hub

A Django web app with feed cards, friends, chat, admin moderation, filters, dark mode, and an in-app AI helper.

## Features
- User login/register with remember-me
- Home feed with search, sort, tag/date filters
- Card create/edit/delete and card detail page
- Friends list with online/offline status
- Direct chat with unread dots and message status ticks
- Share posts to chat
- Admin Center for user/post moderation
- AI Helper chatbox for navigation and usage help
- Light/Dark mode and responsive UI

## Tech Stack
- Python
- Django
- HTML/CSS/JavaScript
- SQLite (default)

## Setup
1. Create and activate virtual environment
2. Install dependencies:
   `pip install -r requirements.txt`
3. Run migrations:
   `python manage.py migrate`
4. (Optional) Create superuser:
   `python manage.py createsuperuser`

## Run
`python manage.py runserver`

Open: `http://127.0.0.1:8000/`

## Notes
- Development server only (not for production).
- Excludes `venv/` and local cache files via `.gitignore`.
- users and passwords (if needed):
   A / a1234567
   B / b1234567
   C / c1234567
   D / d1234567
