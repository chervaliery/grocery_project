from django.db import models

class GroceryList(models.Model):
    name = models.CharField(max_length=200, default="My List")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.id})"


class Section(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name
        }

    def __str__(self):
        return self.name


class Item(models.Model):
    grocery_list = models.ForeignKey(GroceryList, related_name='items', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    checked = models.BooleanField(default=False)
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)

    def to_dict(self):
        return {
            "id": self.id,
            "grocery_list_id": self.grocery_list_id,
            "name": self.name,
            "checked": self.checked,
            "section": self.section.to_dict() if self.section else None,
            "updated_at": self.updated_at.isoformat(),
        }

    def __str__(self):
        return self.name