from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.roles import ADMIN_GROUP, ANALYST_GROUP, ROLE_PERMISSIONS


def _perm_strings(specs: tuple[tuple[str, str, str], ...]) -> set[str]:
    return {f"{app}.{code}" for app, _, code in specs}


class InitGroupsCommandTests(TestCase):
    def test_init_groups_creates_groups_idempotently(self):
        Group.objects.filter(name__in=[ADMIN_GROUP, ANALYST_GROUP]).delete()

        first_out = StringIO()
        call_command("init_groups", stdout=first_out)
        self.assertIn(
            f"group={ADMIN_GROUP} state=created permissions={len(ROLE_PERMISSIONS[ADMIN_GROUP])}",
            first_out.getvalue(),
        )
        self.assertIn(
            f"group={ANALYST_GROUP} state=created permissions={len(ROLE_PERMISSIONS[ANALYST_GROUP])}",
            first_out.getvalue(),
        )

        second_out = StringIO()
        call_command("init_groups", stdout=second_out)
        self.assertIn(
            f"group={ADMIN_GROUP} state=updated permissions={len(ROLE_PERMISSIONS[ADMIN_GROUP])}",
            second_out.getvalue(),
        )
        self.assertIn(
            f"group={ANALYST_GROUP} state=updated permissions={len(ROLE_PERMISSIONS[ANALYST_GROUP])}",
            second_out.getvalue(),
        )
        self.assertEqual(Group.objects.filter(name=ADMIN_GROUP).count(), 1)
        self.assertEqual(Group.objects.filter(name=ANALYST_GROUP).count(), 1)

    def test_group_permissions_match_role_definitions(self):
        call_command("init_groups", stdout=StringIO())

        admin_group = Group.objects.get(name=ADMIN_GROUP)
        analyst_group = Group.objects.get(name=ANALYST_GROUP)

        admin_perms = {
            f"{p.content_type.app_label}.{p.codename}"
            for p in admin_group.permissions.select_related("content_type")
        }
        analyst_perms = {
            f"{p.content_type.app_label}.{p.codename}"
            for p in analyst_group.permissions.select_related("content_type")
        }

        self.assertEqual(admin_perms, _perm_strings(ROLE_PERMISSIONS[ADMIN_GROUP]))
        self.assertEqual(analyst_perms, _perm_strings(ROLE_PERMISSIONS[ANALYST_GROUP]))

    def test_analyst_cannot_access_wagtail_admin_raw_or_quality_issues(self):
        call_command("init_groups", stdout=StringIO())
        User = get_user_model()

        analyst = User.objects.create_user(username="test_analyst")
        analyst.groups.add(Group.objects.get(name=ANALYST_GROUP))

        admin = User.objects.create_user(username="test_admin")
        admin.groups.add(Group.objects.get(name=ADMIN_GROUP))

        self.assertTrue(analyst.has_perm("market.view_priceobservation"))
        self.assertTrue(analyst.has_perm("market.view_exchangerateobservation"))
        self.assertTrue(analyst.has_perm("market.view_collectionrun"))
        self.assertFalse(analyst.has_perm("market.view_rawdocument"))
        self.assertFalse(analyst.has_perm("market.view_qualityissue"))
        self.assertFalse(analyst.has_perm("market.add_source"))
        self.assertFalse(analyst.has_perm("wagtailadmin.access_admin"))
        self.assertFalse(analyst.has_perm("auth.view_user"))

        self.assertTrue(admin.has_perm("wagtailadmin.access_admin"))
        self.assertTrue(admin.has_perm("market.view_rawdocument"))
        self.assertTrue(admin.has_perm("market.view_qualityissue"))
        self.assertTrue(admin.has_perm("market.add_source"))
        self.assertTrue(admin.has_perm("auth.view_user"))

    def test_init_groups_resets_drift_on_rerun(self):
        call_command("init_groups", stdout=StringIO())
        analyst_group = Group.objects.get(name=ANALYST_GROUP)
        raw_perm = Permission.objects.get(
            content_type__app_label="market", codename="view_rawdocument"
        )
        analyst_group.permissions.add(raw_perm)

        call_command("init_groups", stdout=StringIO())
        self.assertFalse(analyst_group.permissions.filter(pk=raw_perm.pk).exists())


class BackendPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("init_groups", stdout=StringIO())
        User = get_user_model()
        cls.admin_group = Group.objects.get(name=ADMIN_GROUP)
        cls.analyst_group = Group.objects.get(name=ANALYST_GROUP)

        cls.admin_user = User.objects.create_user(username="perm_admin")
        cls.admin_user.groups.add(cls.admin_group)

        cls.analyst_user = User.objects.create_user(username="perm_analyst")
        cls.analyst_user.groups.add(cls.analyst_group)

        cls.plain_user = User.objects.create_user(username="perm_plain")

        cls.cms_only_user = User.objects.create_user(username="perm_cms_only")
        cls.cms_only_user.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="wagtailadmin", codename="access_admin"
            )
        )

    def _login_client(self, user=None, *, enforce_csrf=False):
        client = Client(enforce_csrf_checks=enforce_csrf)
        if user is not None:
            client.force_login(user)
        return client

    def test_public_price_and_fx_apis_remain_accessible_without_auth(self):
        api_client = APIClient()
        for url_name in ("price-list", "exchange-rate-list"):
            url = reverse(url_name)
            self.assertEqual(api_client.get(url).status_code, 200)
            api_client.force_authenticate(user=self.analyst_user)
            self.assertEqual(api_client.get(url).status_code, 200)
            api_client.force_authenticate(user=self.admin_user)
            self.assertEqual(api_client.get(url).status_code, 200)
            self.assertEqual(api_client.post(url, {}).status_code, 405)
            api_client.force_authenticate(user=None)

    def test_public_market_pages_remain_accessible(self):
        client = self._login_client()
        for url_name in ("overview", "price-page", "exchange-rate-page"):
            self.assertEqual(client.get(reverse(url_name)).status_code, 200)

    def test_wagtail_admin_blocks_anonymous_plain_and_analyst_users(self):
        cms_url = reverse("wagtailadmin_home")
        login_url = reverse("wagtailadmin_login")

        for user in (None, self.plain_user, self.analyst_user):
            client = self._login_client(user)
            response = client.get(cms_url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], f"{login_url}?next={cms_url}")

        admin_client = self._login_client(self.admin_user)
        self.assertEqual(admin_client.get(cms_url).status_code, 200)

    def test_user_management_blocks_unauthorized_users_on_read_and_write(self):
        User = get_user_model()
        users_index = reverse("wagtailusers_users:index")
        users_add = reverse("wagtailusers_users:add")
        cms_url = reverse("wagtailadmin_home")
        login_url = reverse("wagtailadmin_login")

        for user in (None, self.analyst_user):
            client = self._login_client(user)
            get_resp = client.get(users_index)
            self.assertEqual(get_resp.status_code, 302)
            self.assertEqual(get_resp.headers["Location"], f"{login_url}?next={users_index}")

            post_resp = client.post(users_add, {"username": "blocked_user_1"})
            self.assertEqual(post_resp.status_code, 302)
            self.assertEqual(post_resp.headers["Location"], f"{login_url}?next={users_add}")

        # A user with CMS access but without auth.view_user/add_user is also blocked.
        cms_only_client = self._login_client(self.cms_only_user)
        self.assertEqual(cms_only_client.get(users_index).status_code, 302)
        self.assertEqual(cms_only_client.get(users_index).headers["Location"], cms_url)
        post_cms_only = cms_only_client.post(users_add, {"username": "blocked_user_2"})
        self.assertEqual(post_cms_only.status_code, 302)
        self.assertEqual(post_cms_only.headers["Location"], cms_url)

        self.assertFalse(
            User.objects.filter(username__in=["blocked_user_1", "blocked_user_2"]).exists()
        )

        admin_client = self._login_client(self.admin_user)
        self.assertEqual(admin_client.get(users_index).status_code, 200)
        self.assertEqual(admin_client.get(users_add).status_code, 200)

    def test_group_mutation_is_blocked_even_for_admin_without_add_group_perm(self):
        groups_index = reverse("wagtailusers_groups:index")
        groups_add = reverse("wagtailusers_groups:add")
        cms_url = reverse("wagtailadmin_home")

        analyst_client = self._login_client(self.analyst_user)
        self.assertEqual(analyst_client.get(groups_index).status_code, 302)

        cms_only_client = self._login_client(self.cms_only_user)
        self.assertEqual(cms_only_client.get(groups_index).status_code, 302)
        self.assertEqual(cms_only_client.get(groups_index).headers["Location"], cms_url)

        admin_client = self._login_client(self.admin_user)
        self.assertEqual(admin_client.get(groups_index).status_code, 200)
        add_get = admin_client.get(groups_add)
        self.assertEqual(add_get.status_code, 302)
        self.assertEqual(add_get.headers["Location"], cms_url)

        add_post = admin_client.post(groups_add, {"name": "UnauthorizedGroup"})
        self.assertEqual(add_post.status_code, 302)
        self.assertEqual(add_post.headers["Location"], cms_url)
        self.assertFalse(Group.objects.filter(name="UnauthorizedGroup").exists())

    def test_session_write_without_csrf_token_is_rejected(self):
        csrf_client = self._login_client(self.admin_user, enforce_csrf=True)
        response = csrf_client.post(
            reverse("wagtailusers_users:add"),
            {"username": "csrf_blocked_user"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            get_user_model().objects.filter(username="csrf_blocked_user").exists()
        )
