"""
Models for lists_app: Section, GroceryList, Item, AccessToken.
"""

import secrets
import uuid

from django.db import models


class Section(models.Model):
    """Store section (e.g. Fruits & Légumes). French labels, slug for assignment."""

    name_slug = models.SlugField(max_length=80, unique=True)
    label_fr = models.CharField(max_length=120)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.label_fr


class SectionKeyword(models.Model):
    """Keyword (normalized) mapping to a section. Used for auto-assignment; learned from LLM."""

    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="keywords"
    )
    keyword = models.CharField(max_length=200, unique=True, db_index=True)

    class Meta:
        ordering = ["keyword"]

    def __str__(self):
        return f"{self.keyword} → {self.section.label_fr}"


class GroceryList(models.Model):
    """A single grocery list. One URL = one list."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    archived = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-archived", "position", "-created_at"]

    def __str__(self):
        return self.name


class Item(models.Model):
    """An item on a grocery list. Belongs to a list and a section."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grocery_list = models.ForeignKey(
        GroceryList, on_delete=models.CASCADE, related_name="items"
    )
    name = models.CharField(max_length=200)
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="items")
    quantity = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    checked = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["section", "position", "id"]
        indexes = [
            models.Index(fields=["grocery_list", "section"]),
        ]

    def __str__(self):
        return self.name


class AccessToken(models.Model):
    """Secret URL token for app access. Admin generates; visiting the URL grants a session until revoked."""

    token = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    label = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.label or (self.token[:8] + "…" if self.token else "—")
