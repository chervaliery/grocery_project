from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import GroceryList, Item, Section

@admin.register(GroceryList)
class GroceryListAdmin(admin.ModelAdmin):
    """
    Admin interface for the GroceryList model.
    """
    list_display = ('id', 'name', 'created_at')

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    """
    Admin interface for the Section model.
    """
    list_display = ('id', 'name')

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    """
    Admin interface for the Item model.
    """
    list_display = ('id', 'get_grocery_list', 'name', 'get_section', 'checked', 'updated_at')

    def get_grocery_list(self, obj):
        link = reverse("admin:lists_app_grocerylist_change", args=[obj.grocery_list.pk])
        return format_html(f'<a href="{link}">{obj.grocery_list.name}</a>')

    def get_section(self, obj):
        if obj.section:
            link = reverse("admin:lists_app_section_change", args=[obj.section.pk])
            return format_html(f'<a href="{link}">{obj.section.name}</a>')
        return format_html('-')