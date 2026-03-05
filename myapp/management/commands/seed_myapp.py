from django.core.management.base import BaseCommand

from myapp.models import Card, SidebarItem, Tag


class Command(BaseCommand):
    help = 'Seed sample sidebar items, tags, and cards for myapp.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing myapp data before seeding.',
        )

    def handle(self, *args, **options):
        if options['reset']:
            Card.objects.all().delete()
            Tag.objects.all().delete()
            SidebarItem.objects.all().delete()
            self.stdout.write(self.style.WARNING('Existing myapp data deleted.'))

        for name in ['Home', 'Profile', 'Dashboard', 'Friends', 'Chat', 'Collections', 'Favourites', 'Reports', 'Admin Center', 'Settings', 'Help']:
            SidebarItem.objects.get_or_create(name=name)

        cards = [
            {
                'title': 'Django Basics',
                'description': 'Build views, URLs, and templates with Django.',
                'category': 'Backend',
                'tags': ['Python', 'Django'],
            },
            {
                'title': 'Responsive UI Patterns',
                'description': 'Use layout utilities and breakpoints for mobile-ready pages.',
                'category': 'Frontend',
                'tags': ['Frontend'],
            },
            {
                'title': 'API Testing Workflow',
                'description': 'Write predictable request/response tests for core flows.',
                'category': 'Testing',
                'tags': ['Python', 'Testing', 'API'],
            },
            {
                'title': 'SQLite Quickstart',
                'description': 'Model data and run migrations with SQLite in development.',
                'category': 'Database',
                'tags': ['Database', 'Django'],
            },
            {
                'title': 'Design System Tokens',
                'description': 'Create reusable color, spacing, and typography tokens for consistency.',
                'category': 'Frontend',
                'tags': ['Frontend', 'Design'],
            },
            {
                'title': 'Async Task Queue Intro',
                'description': 'Move long-running jobs into background workers for better responsiveness.',
                'category': 'Backend',
                'tags': ['Python', 'API', 'Performance'],
            },
            {
                'title': 'Schema Migration Checklist',
                'description': 'Safe migration steps for schema changes in shared environments.',
                'category': 'Database',
                'tags': ['Database', 'DevOps'],
            },
            {
                'title': 'CI Pipeline Health',
                'description': 'Monitor flaky tests, run coverage, and enforce quality gates.',
                'category': 'Testing',
                'tags': ['Testing', 'DevOps'],
            },
            {
                'title': 'Caching Strategy Notes',
                'description': 'Evaluate local cache, Redis, and cache invalidation tactics.',
                'category': 'Backend',
                'tags': ['Performance', 'Python'],
            },
            {
                'title': 'Accessibility Audit Pass',
                'description': 'Improve keyboard navigation, focus states, and color contrast.',
                'category': 'Frontend',
                'tags': ['Frontend', 'UX'],
            },
            {
                'title': 'Release Readiness Report',
                'description': 'Summarize blockers, known risks, and launch confidence level.',
                'category': 'Reports',
                'tags': ['Reports', 'Planning'],
            },
            {
                'title': 'Sprint Burndown Snapshot',
                'description': 'Track completed scope against sprint commitments over time.',
                'category': 'Reports',
                'tags': ['Reports', 'Analytics'],
            },
            {
                'title': 'User Persona Notes',
                'description': 'Capture audience pain points and goals for product decisions.',
                'category': 'Profile',
                'tags': ['UX', 'Product'],
            },
            {
                'title': 'Account Security Tips',
                'description': 'Best practices for passwords, MFA, and account recovery.',
                'category': 'Profile',
                'tags': ['Security', 'Guides'],
            },
            {
                'title': 'Default Settings Guide',
                'description': 'Recommended default preferences for first-time users.',
                'category': 'Settings',
                'tags': ['Guides', 'Product'],
            },
            {
                'title': 'Notification Rules',
                'description': 'Configure alerts by event type and urgency level.',
                'category': 'Settings',
                'tags': ['Settings', 'Product'],
            },
            {
                'title': 'Starter Card Collection',
                'description': 'A curated starter set of cards for onboarding.',
                'category': 'Collections',
                'tags': ['Collections', 'Guides'],
            },
            {
                'title': 'Django Learning Path',
                'description': 'Recommended progression from fundamentals to deployment.',
                'category': 'Collections',
                'tags': ['Collections', 'Django', 'Learning'],
            },
            {
                'title': 'Favorite: Query Optimization',
                'description': 'Keep this handy reference for reducing expensive queries.',
                'category': 'Favourites',
                'tags': ['Favourites', 'Database', 'Performance'],
            },
            {
                'title': 'Favorite: UI Layout Cheatsheet',
                'description': 'Personal reference for grid/flex patterns I reuse often.',
                'category': 'Favourites',
                'tags': ['Favourites', 'Frontend', 'Design'],
            },
            {
                'title': 'Help Center Overview',
                'description': 'Start here to understand pages, flows, and app conventions.',
                'category': 'Help',
                'tags': ['Help', 'Guides'],
            },
            {
                'title': 'Import JSON Examples',
                'description': 'Sample payloads for bulk importing cards safely.',
                'category': 'Help',
                'tags': ['Help', 'API', 'Guides'],
            },
            {
                'title': 'Dashboard KPI Baseline',
                'description': 'Baseline counts and trends for monitoring growth.',
                'category': 'Dashboard',
                'tags': ['Dashboard', 'Analytics'],
            },
            {
                'title': 'Weekly Ops Summary',
                'description': 'High-level operational summary across engineering tasks.',
                'category': 'Dashboard',
                'tags': ['Dashboard', 'Reports'],
            },
            {
                'title': 'Theme Palette Options',
                'description': 'Evaluate calm, contrast-rich palettes for the interface.',
                'category': 'Design',
                'tags': ['Design', 'Frontend'],
            },
            {
                'title': 'Roadmap Planning Board',
                'description': 'Collect upcoming initiatives and their priority scores.',
                'category': 'Planning',
                'tags': ['Planning', 'Product'],
            },
            {
                'title': 'API Contract Notes',
                'description': 'Document request/response structures shared with frontend.',
                'category': 'API',
                'tags': ['API', 'Backend'],
            },
            {
                'title': 'Data Backup Routine',
                'description': 'Regular backup checklist for local and remote environments.',
                'category': 'DevOps',
                'tags': ['DevOps', 'Database', 'Security'],
            },
            {
                'title': 'News Trend Monitor',
                'description': 'Track major weekly headlines and categorize by topic.',
                'category': 'News',
                'tags': ['News', 'Reports'],
            },
            {
                'title': 'Sports Match Digest',
                'description': 'Collect key results and upcoming fixtures in one card.',
                'category': 'Sports',
                'tags': ['Sports', 'Reports'],
            },
            {
                'title': 'Business Signals Brief',
                'description': 'Monitor market sentiment and emerging business signals.',
                'category': 'Business',
                'tags': ['Business', 'Analytics'],
            },
            {
                'title': 'Education Resource Pack',
                'description': 'Curated references for learning paths and tutorials.',
                'category': 'Education',
                'tags': ['Education', 'Learning'],
            },
            {
                'title': 'Technology Radar',
                'description': 'Shortlist promising tools and frameworks worth evaluating.',
                'category': 'Technology',
                'tags': ['Technology', 'Planning'],
            },
            {
                'title': 'Quarterly Goal Snapshot',
                'description': 'Review quarter goals and current progress status.',
                'category': 'Planning',
                'tags': ['Planning', 'Reports'],
            },
            {
                'title': 'Content QA Checklist',
                'description': 'Checklist for reviewing content quality before publishing.',
                'category': 'Testing',
                'tags': ['Testing', 'Guides'],
            },
            {
                'title': 'Frontend Animation Notes',
                'description': 'Patterns for subtle motion and page-load transitions.',
                'category': 'Frontend',
                'tags': ['Frontend', 'Design'],
            },
            {
                'title': 'Backend Service Blueprint',
                'description': 'Reference architecture for service boundaries and contracts.',
                'category': 'Backend',
                'tags': ['Backend', 'API'],
            },
            {
                'title': 'Favourites: Sprint Template',
                'description': 'Reusable sprint planning format used by the team.',
                'category': 'Favourites',
                'tags': ['Favourites', 'Planning'],
            },
            {
                'title': 'Favourites: SQL Snippets',
                'description': 'Handy SQL examples saved for frequent troubleshooting.',
                'category': 'Favourites',
                'tags': ['Favourites', 'Database'],
            },
            {
                'title': 'Profile Completion Tips',
                'description': 'Improve profile clarity with practical field suggestions.',
                'category': 'Profile',
                'tags': ['Profile', 'Guides'],
            },
            {
                'title': 'Settings Migration Notes',
                'description': 'How settings changes affect existing user sessions.',
                'category': 'Settings',
                'tags': ['Settings', 'DevOps'],
            },
            {
                'title': 'Reports Export Rules',
                'description': 'Define naming conventions and retention for generated reports.',
                'category': 'Reports',
                'tags': ['Reports', 'API'],
            },
            {
                'title': 'Collection Curation Plan',
                'description': 'Plan periodic updates to keep collections relevant.',
                'category': 'Collections',
                'tags': ['Collections', 'Planning'],
            },
            {
                'title': 'Dashboard Alert Thresholds',
                'description': 'Set sensible alert limits for operational metrics.',
                'category': 'Dashboard',
                'tags': ['Dashboard', 'Analytics'],
            },
            {
                'title': 'Help FAQ Starters',
                'description': 'Starter answers for frequent user onboarding questions.',
                'category': 'Help',
                'tags': ['Help', 'Guides'],
            },
            {
                'title': 'Security Review Cadence',
                'description': 'Recommended schedule for recurring security checks.',
                'category': 'Security',
                'tags': ['Security', 'Planning'],
            },
            {
                'title': 'API Pagination Pattern',
                'description': 'Consistent approach for paginated list endpoints.',
                'category': 'API',
                'tags': ['API', 'Backend', 'Guides'],
            },
            {
                'title': 'Database Index Priorities',
                'description': 'Identify high-impact index opportunities from query usage.',
                'category': 'Database',
                'tags': ['Database', 'Performance', 'Analytics'],
            },
        ]

        tags = {}
        for card in cards:
            for tag_name in card['tags']:
                if tag_name not in tags:
                    tags[tag_name], _ = Tag.objects.get_or_create(name=tag_name)

        created = 0
        updated = 0

        for item in cards:
            card, was_created = Card.objects.update_or_create(
                title=item['title'],
                defaults={
                    'description': item['description'],
                    'category': item['category'],
                },
            )
            card.tags.set([tags[name] for name in item['tags']])
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seed complete. Cards created: {created}, updated: {updated}, total cards: {Card.objects.count()}.'
            )
        )
