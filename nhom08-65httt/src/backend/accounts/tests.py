from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase

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
