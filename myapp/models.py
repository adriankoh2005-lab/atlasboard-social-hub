from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# Sidebar item model
class SidebarItem(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

# Tag model
class Tag(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

# Card model
class Card(models.Model):
    title = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=50)
    tags = models.ManyToManyField(Tag)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cards')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class UserPresence(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='presence')
    is_online = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} presence'


class Friendship(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships')
    friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_of')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'friend'], name='unique_friend_pair'),
        ]

    def __str__(self):
        return f'{self.user.username} -> {self.friend.username}'


class DirectMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_direct_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_direct_messages')
    body = models.TextField(max_length=1000)
    hidden_for = models.ManyToManyField(User, blank=True, related_name='hidden_direct_messages')
    delivered_at = models.DateTimeField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at', 'id']

    def __str__(self):
        return f'{self.sender.username} -> {self.receiver.username}'
