"""
Tests for lists_app: models, section assigner, API, WebSocket, secret-URL access.
"""

import asyncio
import json

from channels.testing import WebsocketCommunicator
from django.test import TestCase, Client, override_settings

from lists_app.models import AccessToken, GroceryList, Item, Section, SectionKeyword
from lists_app.services.section_assigner import (
    assign_section,
    _match_keywords,
    _normalize,
)


class SectionModelTest(TestCase):
    def test_sections_seeded(self):
        self.assertGreaterEqual(Section.objects.count(), 10)
        autre = Section.objects.get(name_slug="autre")
        self.assertEqual(autre.label_fr, "Autre")

    def test_section_ordering(self):
        sections = list(Section.objects.all())
        for i in range(len(sections) - 1):
            self.assertLessEqual(sections[i].position, sections[i + 1].position)


class GroceryListModelTest(TestCase):
    def test_create_list(self):
        gl = GroceryList.objects.create(name="Test list")
        self.assertIsNotNone(gl.id)
        self.assertFalse(gl.archived)
        self.assertEqual(gl.name, "Test list")

    def test_list_ordering(self):
        GroceryList.objects.create(name="A", position=1)
        GroceryList.objects.create(name="B", position=0)
        qs = GroceryList.objects.all()
        self.assertEqual(qs[0].name, "B")
        self.assertEqual(qs[1].name, "A")


class AccessTokenModelTest(TestCase):
    def test_create_auto_generates_token(self):
        t = AccessToken.objects.create(label="Test link")
        self.assertIsNotNone(t.token)
        self.assertEqual(len(t.token), 43)  # 32 bytes url-safe base64
        self.assertFalse(t.revoked)
        self.assertEqual(t.label, "Test link")

    def test_revoked_default_false(self):
        t = AccessToken.objects.create()
        self.assertFalse(t.revoked)

    def test_str_uses_label_when_set(self):
        t = AccessToken.objects.create(label="Marie's phone")
        self.assertEqual(str(t), "Marie's phone")

    def test_str_uses_token_preview_when_no_label(self):
        t = AccessToken.objects.create(token="abcd1234xyz")
        self.assertEqual(str(t), "abcd1234…")


class ItemModelTest(TestCase):
    def setUp(self):
        self.section = Section.objects.first()
        self.grocery_list = GroceryList.objects.create(name="Test")

    def test_create_item(self):
        item = Item.objects.create(
            grocery_list=self.grocery_list,
            name="Lait",
            section=self.section,
            quantity="2",
            position=0,
        )
        self.assertIsNotNone(item.id)
        self.assertEqual(item.name, "Lait")
        self.assertEqual(item.quantity, "2")
        self.assertFalse(item.checked)


class SectionAssignerTest(TestCase):
    def test_normalize(self):
        self.assertEqual(_normalize("  Lait  "), "lait")
        self.assertEqual(_normalize(""), "")

    def test_match_keywords(self):
        self.assertEqual(_match_keywords("lait"), "produits_laitiers_oeufs")
        self.assertEqual(_match_keywords("poulet"), "viande_volaille")
        self.assertEqual(_match_keywords("xyzunknown"), None)

    def test_assign_section(self):
        section = assign_section("lait")
        self.assertIsNotNone(section)
        self.assertEqual(section.name_slug, "produits_laitiers_oeufs")
        section2 = assign_section("  Poulet  ")
        self.assertEqual(section2.name_slug, "viande_volaille")
        section3 = assign_section("something unknown")
        self.assertIsNotNone(section3)
        self.assertEqual(section3.name_slug, "autre")

    def test_assign_section_db_keyword(self):
        """Keyword stored in DB is used for assignment."""
        epicerie = Section.objects.get(name_slug="epicerie")
        SectionKeyword.objects.get_or_create(
            keyword="nouille", defaults={"section": epicerie}
        )
        section = assign_section("nouille")
        self.assertIsNotNone(section)
        self.assertEqual(section.name_slug, "epicerie")


class GateViewTest(TestCase):
    """Tests for /enter/<token>/ (secret URL gate)."""

    def test_valid_token_sets_session_and_redirects_to_root(self):
        t = AccessToken.objects.create(token="valid-token-123", label="Test")
        client = Client()
        response = client.get("/enter/valid-token-123/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        self.assertEqual(client.session.get("secret_url_token_id"), t.id)

    def test_invalid_token_redirects_to_auth_required_revoked(self):
        client = Client()
        response = client.get("/enter/nonexistent-token/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/required/", response.url)
        self.assertIn("revoked=1", response.url)

    def test_revoked_token_redirects_to_auth_required_revoked(self):
        AccessToken.objects.create(token="revoked-token", revoked=True)
        client = Client()
        response = client.get("/enter/revoked-token/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/required/", response.url)
        self.assertIn("revoked=1", response.url)


class AuthRequiredViewTest(TestCase):
    """Tests for /auth/required/ page."""

    def test_auth_required_returns_200(self):
        client = Client()
        response = client.get("/auth/required/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Accès restreint", content)
        self.assertIn("lien secret", content)

    def test_auth_required_revoked_shows_revoked_message(self):
        client = Client()
        response = client.get("/auth/required/?revoked=1")
        self.assertEqual(response.status_code, 200)
        self.assertIn("révoqué", response.content.decode("utf-8"))


@override_settings(SECRET_URL_AUTH_REQUIRED=True)
class SecretURLMiddlewareTest(TestCase):
    """Tests for SecretURLRequiredMiddleware when auth is required."""

    def test_no_session_redirects_to_auth_required(self):
        client = Client()
        response = client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/auth/required/")

    def test_no_session_api_redirects_to_auth_required(self):
        client = Client()
        response = client.get("/api/lists/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/auth/required/")

    def test_valid_token_in_session_allows_request(self):
        AccessToken.objects.create(token="middleware-test-token")
        client = Client()
        client.get("/enter/middleware-test-token/")  # set session
        response = client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_revoked_token_redirects_and_flushes_session(self):
        t = AccessToken.objects.create(token="will-revoke", label="Revoke me")
        client = Client()
        client.get("/enter/will-revoke/")  # set session
        t.revoked = True
        t.save()
        response = client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("revoked=1", response.url)
        self.assertNotIn("secret_url_token_id", client.session)

    def test_skip_paths_not_redirected(self):
        """Paths in skip list (e.g. /auth/required/) are not redirected by middleware."""
        client = Client()
        response = client.get("/auth/required/")
        self.assertEqual(response.status_code, 200)


@override_settings(SECRET_URL_AUTH_REQUIRED=False)
class ApiListsTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_list_lists_empty(self):
        response = self.client.get("/api/lists/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("lists", data)
        self.assertEqual(data["lists"], [])

    def test_create_list(self):
        response = self.client.post(
            "/api/lists/",
            data=json.dumps({"name": "Ma liste"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertIn("id", data)
        self.assertEqual(data["name"], "Ma liste")

    def test_get_list_not_found(self):
        response = self.client.get("/api/lists/00000000-0000-0000-0000-000000000000/")
        self.assertEqual(response.status_code, 404)

    def test_get_list_detail(self):
        gl = GroceryList.objects.create(name="Test")
        response = self.client.get(f"/api/lists/{gl.id}/")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["name"], "Test")
        self.assertIn("sections", data)

    def test_patch_list_archive(self):
        gl = GroceryList.objects.create(name="Test")
        response = self.client.patch(
            f"/api/lists/{gl.id}/",
            data=json.dumps({"archived": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        gl.refresh_from_db()
        self.assertTrue(gl.archived)

    def test_delete_list(self):
        gl = GroceryList.objects.create(name="Test")
        response = self.client.delete(f"/api/lists/{gl.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(GroceryList.objects.filter(pk=gl.id).exists())


@override_settings(SECRET_URL_AUTH_REQUIRED=False)
class ApiItemsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.grocery_list = GroceryList.objects.create(name="Test")
        self.section = Section.objects.get(name_slug="produits_laitiers_oeufs")

    def test_create_item(self):
        response = self.client.post(
            f"/api/lists/{self.grocery_list.id}/items/",
            data=json.dumps({"name": "Lait"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertEqual(data["name"], "Lait")
        self.assertEqual(Item.objects.filter(grocery_list=self.grocery_list).count(), 1)

    def test_create_item_empty_name_fails(self):
        response = self.client.post(
            f"/api/lists/{self.grocery_list.id}/items/",
            data=json.dumps({"name": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_item_checked(self):
        item = Item.objects.create(
            grocery_list=self.grocery_list, name="X", section=self.section
        )
        response = self.client.patch(
            f"/api/lists/{self.grocery_list.id}/items/{item.id}/",
            data=json.dumps({"checked": True}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertTrue(item.checked)

    def test_delete_item(self):
        item = Item.objects.create(
            grocery_list=self.grocery_list, name="X", section=self.section
        )
        response = self.client.delete(
            f"/api/lists/{self.grocery_list.id}/items/{item.id}/"
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Item.objects.filter(pk=item.id).exists())


@override_settings(SECRET_URL_AUTH_REQUIRED=False)
class WebSocketTest(TestCase):
    def test_connect_invalid_list_id_rejected(self):
        from grocery_project.asgi import application as ws_application

        async def run():
            communicator = WebsocketCommunicator(
                ws_application, "/ws/list/00000000-0000-0000-0000-000000000000/"
            )
            connected, _ = await communicator.connect()
            return connected

        connected = asyncio.run(run())
        self.assertFalse(connected)

    def test_connect_nonexistent_list_rejected(self):
        from grocery_project.asgi import application as ws_application

        async def run():
            communicator = WebsocketCommunicator(
                ws_application,
                "/ws/list/12345678-1234-1234-1234-123456789abc/",
            )
            connected, _ = await communicator.connect()
            return connected

        connected = asyncio.run(run())
        self.assertFalse(connected)

    @override_settings(SECRET_URL_AUTH_REQUIRED=True)
    def test_connect_without_secret_url_session_rejected(self):
        """With SECRET_URL_AUTH_REQUIRED=True, WebSocket is rejected when session has no token."""
        from grocery_project.asgi import application as ws_application

        gl = GroceryList.objects.create(name="Test list")

        async def run():
            communicator = WebsocketCommunicator(ws_application, f"/ws/list/{gl.id}/")
            connected, _ = await communicator.connect()
            return connected

        connected = asyncio.run(run())
        self.assertFalse(connected)
