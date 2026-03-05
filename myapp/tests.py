import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Card, DirectMessage, Friendship, SidebarItem, Tag


class AuthFlowTests(TestCase):
    def test_login_page_renders(self):
        response = self.client.get(reverse('login_page'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'myapp/login.html')

    def test_register_creates_user_and_redirects_to_index(self):
        response = self.client.post(
            reverse('register_page'),
            {
                'username': 'newuser',
                'email': 'new@example.com',
                'password1': 'StrongPass123!',
                'password2': 'StrongPass123!',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('index'))
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_index_requires_login(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login_page'), response.url)


class CardPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ['Home', 'Help', 'Dashboard', 'Profile', 'Settings', 'Reports', 'Collections', 'Favorites', 'Admin Center']:
            SidebarItem.objects.create(name=name)

        cls.user1 = User.objects.create_user(username='alice', password='pass12345')
        cls.user2 = User.objects.create_user(username='bob', password='pass12345')
        cls.admin = User.objects.create_user(username='admin', password='pass12345', is_staff=True)
        cls.tag = Tag.objects.create(name='General')

        cls.card = Card.objects.create(
            title='Alice Post',
            description='Owned by Alice',
            category='General',
            owner=cls.user1,
        )
        cls.card.tags.add(cls.tag)

    def test_add_card_sets_owner(self):
        self.client.login(username='alice', password='pass12345')
        response = self.client.post(
            reverse('add_card'),
            {
                'title': 'My New Post',
                'description': 'Body',
                'category': 'News',
                'tags': 'General, News',
            },
        )
        self.assertEqual(response.status_code, 302)
        post = Card.objects.get(title='My New Post')
        self.assertEqual(post.owner, self.user1)

    def test_owner_can_edit_own_card(self):
        self.client.login(username='alice', password='pass12345')
        response = self.client.post(
            reverse('edit_card', args=[self.card.id]),
            {
                'title': 'Alice Post Updated',
                'description': 'Updated text',
                'category': 'General',
                'tags': 'General',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.card.refresh_from_db()
        self.assertEqual(self.card.title, 'Alice Post Updated')

    def test_non_owner_cannot_edit_card(self):
        self.client.login(username='bob', password='pass12345')
        response = self.client.post(
            reverse('edit_card', args=[self.card.id]),
            {
                'title': 'Hacked',
                'description': 'Nope',
                'category': 'General',
                'tags': 'General',
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_non_owner_cannot_delete_card(self):
        self.client.login(username='bob', password='pass12345')
        response = self.client.post(reverse('delete_card', args=[self.card.id]))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Card.objects.filter(id=self.card.id).exists())

    def test_admin_can_delete_any_card(self):
        self.client.login(username='admin', password='pass12345')
        response = self.client.post(reverse('delete_card', args=[self.card.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Card.objects.filter(id=self.card.id).exists())


class AdminCenterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ['Home', 'Help', 'Dashboard', 'Profile', 'Settings', 'Reports', 'Collections', 'Favorites', 'Admin Center']:
            SidebarItem.objects.create(name=name)
        cls.admin = User.objects.create_user(username='admin', password='pass12345', is_staff=True)
        cls.normal = User.objects.create_user(username='normal', password='pass12345')
        cls.normal2 = User.objects.create_user(username='normal2', password='pass12345')
        cls.card = Card.objects.create(title='Normal Post', description='Body', category='General', owner=cls.normal)

    def test_admin_center_only_for_admin(self):
        self.client.login(username='normal', password='pass12345')
        denied = self.client.get(reverse('admin_center_page'))
        self.assertEqual(denied.status_code, 302)

        self.client.login(username='admin', password='pass12345')
        allowed = self.client.get(reverse('admin_center_page'))
        self.assertEqual(allowed.status_code, 200)
        self.assertTemplateUsed(allowed, 'myapp/admin_center.html')

    def test_admin_can_promote_user(self):
        self.client.login(username='admin', password='pass12345')
        response = self.client.post(reverse('promote_user_admin', args=[self.normal2.id]))
        self.assertEqual(response.status_code, 302)
        self.normal2.refresh_from_db()
        self.assertTrue(self.normal2.is_staff)

    def test_non_admin_cannot_promote_user(self):
        self.client.login(username='normal', password='pass12345')
        response = self.client.post(reverse('promote_user_admin', args=[self.normal2.id]))
        self.assertEqual(response.status_code, 302)
        self.normal2.refresh_from_db()
        self.assertFalse(self.normal2.is_staff)

    def test_index_hides_admin_center_for_non_admin(self):
        self.client.login(username='normal', password='pass12345')
        response = self.client.get(reverse('index'))
        self.assertNotContains(response, reverse('admin_center_page'))

        self.client.login(username='admin', password='pass12345')
        response_admin = self.client.get(reverse('index'))
        self.assertContains(response_admin, reverse('admin_center_page'))


class AppFeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ['Home', 'Help', 'Dashboard', 'Profile', 'Settings', 'Reports', 'Collections', 'Favorites', 'Admin Center']:
            SidebarItem.objects.create(name=name)
        cls.admin = User.objects.create_user(username='admin', password='pass12345', is_staff=True)
        cls.user = User.objects.create_user(username='user', password='pass12345')

        cls.tag_python = Tag.objects.create(name='Python')
        cls.tag_django = Tag.objects.create(name='Django')

        card1 = Card.objects.create(title='Django Basics', description='Learn Django framework', category='Backend', owner=cls.user)
        card1.tags.set([cls.tag_python, cls.tag_django])
        card1.created_at = timezone.now() - timedelta(days=45)
        card1.save(update_fields=['created_at'])

        card2 = Card.objects.create(title='API Testing', description='Test client assertions', category='Testing', owner=cls.admin)
        card2.tags.set([cls.tag_python])
        card2.created_at = timezone.now() - timedelta(days=2)
        card2.save(update_fields=['created_at'])

    def test_search_filter_and_sort_work_for_logged_in_user(self):
        self.client.login(username='user', password='pass12345')
        response = self.client.get(reverse('index'), {'search': 'Django', 'sort': 'title'})
        self.assertEqual(response.status_code, 200)
        titles = [card.title for card in response.context['cards']]
        self.assertEqual(titles, ['Django Basics'])
        self.assertContains(response, 'Clear Filters')

    def test_default_sort_comes_from_settings(self):
        self.client.login(username='user', password='pass12345')
        session = self.client.session
        session['settings_default_sort'] = 'title'
        session.save()

        response = self.client.get(reverse('index'))
        self.assertEqual(response.context['sort_by'], 'title')

    def test_help_page_available_for_logged_in_user(self):
        self.client.login(username='user', password='pass12345')
        response = self.client.get(reverse('help_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Getting Started')

    def test_home_date_filter_works(self):
        self.client.login(username='user', password='pass12345')
        recent_from = (timezone.now() - timedelta(days=7)).date().isoformat()
        response = self.client.get(reverse('index'), {'date_from': recent_from})
        self.assertEqual(response.status_code, 200)
        titles = [card.title for card in response.context['cards']]
        self.assertIn('API Testing', titles)
        self.assertNotIn('Django Basics', titles)

    def test_export_import_admin_only(self):
        self.client.login(username='user', password='pass12345')
        denied_export = self.client.get(reverse('export_cards_json'))
        self.assertEqual(denied_export.status_code, 302)

        self.client.login(username='admin', password='pass12345')
        allowed_export = self.client.get(reverse('export_cards_json'))
        self.assertEqual(allowed_export.status_code, 200)
        payload = json.dumps(
            [
                {
                    'title': 'Imported',
                    'description': 'From json',
                    'category': 'General',
                    'tags': ['Python'],
                }
            ]
        )
        allowed_import = self.client.post(reverse('import_cards_json'), {'payload': payload})
        self.assertEqual(allowed_import.status_code, 302)
        self.assertTrue(Card.objects.filter(title='Imported').exists())


class ChatShareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ['Home', 'Profile', 'Dashboard', 'Friends', 'Chat', 'Collections', 'Favourites', 'Reports', 'Settings', 'Help']:
            SidebarItem.objects.create(name=name)
        cls.user = User.objects.create_user(username='user', password='pass12345')
        cls.friend = User.objects.create_user(username='friend', password='pass12345')
        cls.other = User.objects.create_user(username='other', password='pass12345')
        cls.card = Card.objects.create(
            title='Shareable Post',
            description='Something useful to share',
            category='General',
            owner=cls.user,
        )
        Friendship.objects.create(user=cls.user, friend=cls.friend)
        Friendship.objects.create(user=cls.friend, friend=cls.user)

    def test_share_card_creates_direct_message(self):
        self.client.login(username='user', password='pass12345')
        response = self.client.post(reverse('share_card_to_chat', args=[self.card.id]), {'friend_id': self.friend.id})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('chat_hub_page'), response.url)
        self.assertTrue(
            DirectMessage.objects.filter(sender=self.user, receiver=self.friend, body__icontains='Shareable Post').exists()
        )

    def test_share_card_denied_for_non_friend(self):
        self.client.login(username='user', password='pass12345')
        response = self.client.post(reverse('share_card_to_chat', args=[self.card.id]), {'friend_id': self.other.id})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DirectMessage.objects.filter(sender=self.user, receiver=self.other).exists())


class ChatDeleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ['Home', 'Profile', 'Dashboard', 'Friends', 'Chat', 'Collections', 'Favourites', 'Reports', 'Settings', 'Help']:
            SidebarItem.objects.create(name=name)
        cls.sender = User.objects.create_user(username='sender', password='pass12345')
        cls.receiver = User.objects.create_user(username='receiver', password='pass12345')
        cls.other = User.objects.create_user(username='other', password='pass12345')
        Friendship.objects.create(user=cls.sender, friend=cls.receiver)
        Friendship.objects.create(user=cls.receiver, friend=cls.sender)

    def test_sender_delete_removes_message_for_both(self):
        msg = DirectMessage.objects.create(sender=self.sender, receiver=self.receiver, body='hello all')
        self.client.login(username='sender', password='pass12345')
        response = self.client.post(reverse('delete_chat_message', args=[msg.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DirectMessage.objects.filter(id=msg.id).exists())

    def test_receiver_delete_hides_only_for_receiver(self):
        msg = DirectMessage.objects.create(sender=self.sender, receiver=self.receiver, body='hello receiver')
        self.client.login(username='receiver', password='pass12345')
        response = self.client.post(reverse('delete_chat_message', args=[msg.id]))
        self.assertEqual(response.status_code, 302)
        msg.refresh_from_db()
        self.assertTrue(msg.hidden_for.filter(id=self.receiver.id).exists())
        self.assertFalse(msg.hidden_for.filter(id=self.sender.id).exists())

        self.client.login(username='receiver', password='pass12345')
        receiver_view = self.client.get(reverse('chat_hub_page'), {'friend': self.sender.id})
        self.assertNotContains(receiver_view, 'hello receiver')

        self.client.login(username='sender', password='pass12345')
        sender_view = self.client.get(reverse('chat_hub_page'), {'friend': self.receiver.id})
        self.assertContains(sender_view, 'hello receiver')

    def test_non_participant_cannot_delete_message(self):
        msg = DirectMessage.objects.create(sender=self.sender, receiver=self.receiver, body='protected')
        self.client.login(username='other', password='pass12345')
        response = self.client.post(reverse('delete_chat_message', args=[msg.id]))
        self.assertEqual(response.status_code, 403)


class CardDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for name in ['Home', 'Profile', 'Dashboard', 'Friends', 'Chat', 'Collections', 'Favourites', 'Reports', 'Settings', 'Help']:
            SidebarItem.objects.create(name=name)
        cls.user = User.objects.create_user(username='reader', password='pass12345')
        cls.card = Card.objects.create(
            title='Detail Card',
            description='Detail content',
            category='General',
            owner=cls.user,
        )

    def test_card_detail_requires_login(self):
        response = self.client.get(reverse('card_detail', args=[self.card.id]))
        self.assertEqual(response.status_code, 302)

    def test_card_detail_renders_for_logged_in_user(self):
        self.client.login(username='reader', password='pass12345')
        response = self.client.get(reverse('card_detail', args=[self.card.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Detail Card')
