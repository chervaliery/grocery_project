from django.contrib import admin

from .models import GroceryList, Item, Section, SectionKeyword


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name_slug", "label_fr", "position")
    search_fields = ("name_slug", "label_fr")
    list_editable = ("position",)
    ordering = ("position", "id")


@admin.register(SectionKeyword)
class SectionKeywordAdmin(admin.ModelAdmin):
    list_display = ("keyword", "section")
    search_fields = ("keyword",)
    list_filter = ("section",)
    ordering = ("keyword",)


class ItemInline(admin.TabularInline):
    model = Item
    extra = 0
    fields = ("name", "section", "quantity", "notes", "checked", "position")
    ordering = ("section", "position")
    show_change_link = True


@admin.register(GroceryList)
class GroceryListAdmin(admin.ModelAdmin):
    list_display = ("name", "id", "created_at", "archived", "position")
    list_filter = ("archived",)
    search_fields = ("name",)
    ordering = ("-archived", "position", "-created_at")
    inlines = [ItemInline]
    readonly_fields = ("id", "created_at")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("name", "grocery_list", "section", "checked", "position")
    list_filter = ("section", "checked", "grocery_list")
    search_fields = ("name", "notes")
    ordering = ("grocery_list", "section", "position")
    readonly_fields = ("id",)
    list_select_related = ("grocery_list", "section")
