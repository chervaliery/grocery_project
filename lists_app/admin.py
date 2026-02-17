from django.contrib import admin
from django.contrib import messages

from .models import AccessToken, GroceryList, Item, Section, SectionKeyword


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


def revoke_tokens_action(modeladmin, request, queryset):
    n = queryset.update(revoked=True)
    modeladmin.message_user(request, f"{n} lien(s) révoqué(s).", messages.SUCCESS)


revoke_tokens_action.short_description = "Révoquer les liens sélectionnés"


@admin.register(AccessToken)
class AccessTokenAdmin(admin.ModelAdmin):
    list_display = ("label", "token_preview", "created_at", "revoked")
    list_editable = ("revoked",)
    list_filter = ("revoked",)
    search_fields = ("label", "token")
    ordering = ("-created_at",)
    readonly_fields = ("token", "created_at", "secret_url")
    actions = [revoke_tokens_action]

    def token_preview(self, obj):
        if not obj.token:
            return "—"
        return obj.token[:8] + "…"

    token_preview.short_description = "Token"

    def secret_url(self, obj):
        if not obj.pk or not obj.token:
            return "—"
        return (
            getattr(self, "_request", None)
            and self._request.build_absolute_uri(f"/enter/{obj.token}/")
            or f"/enter/{obj.token}/"
        )

    secret_url.short_description = "URL à partager"

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj:
            fields.append("secret_url")
        return fields

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self._request = request
        return super().change_view(request, object_id, form_url, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        url = request.build_absolute_uri(f"/enter/{obj.token}/")
        self.message_user(
            request,
            f"Partagez ce lien (à copier maintenant) : {url}",
            messages.SUCCESS,
        )
        return super().response_add(request, obj, post_url_continue)
