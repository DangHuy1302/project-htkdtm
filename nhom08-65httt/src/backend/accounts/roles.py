from dataclasses import dataclass

from django.contrib.auth.models import Group, Permission
from django.db import transaction

ADMIN_GROUP = "Admin"
ANALYST_GROUP = "Analyst"

_MARKET_READ_MODELS = (
    "source",
    "priceseries",
    "collectionrun",
    "priceobservation",
    "exchangerateobservation",
)
_MARKET_ADMIN_CRUD_MODELS = ("source", "priceseries")
_MARKET_ADMIN_READ_ONLY_MODELS = (
    "rawdocument",
    "collectionrun",
    "qualityissue",
    "priceobservation",
    "exchangerateobservation",
)


def _model_perms(
    app_label: str, models: tuple[str, ...], actions: tuple[str, ...]
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (app_label, model, f"{action}_{model}")
        for model in models
        for action in actions
    )


# Base Django/Wagtail permissions per role. Business API endpoints and object-level
# checks (plans, alerts, news, raw/quality-issue filtering) must still enforce
# authorization explicitly in their own views and services.
ROLE_PERMISSIONS: dict[str, tuple[tuple[str, str, str], ...]] = {
    ADMIN_GROUP: (
        ("wagtailadmin", "admin", "access_admin"),
        ("auth", "user", "view_user"),
        ("auth", "user", "add_user"),
        ("auth", "user", "change_user"),
        ("auth", "group", "view_group"),
        *_model_perms("market", _MARKET_ADMIN_CRUD_MODELS, ("view", "add", "change", "delete")),
        *_model_perms("market", _MARKET_ADMIN_READ_ONLY_MODELS, ("view",)),
    ),
    ANALYST_GROUP: (
        *_model_perms("market", _MARKET_READ_MODELS, ("view",)),
    ),
}


@dataclass(frozen=True)
class GroupSyncResult:
    """Summary of creating or updating a role group."""

    name: str
    created: bool
    permission_count: int


def resolve_permissions(specs: tuple[tuple[str, str, str], ...]) -> list[Permission]:
    """Resolve (app_label, model, codename) specs into Permission instances."""
    app_labels = {app for app, _, _ in specs}
    models = {model for _, model, _ in specs}
    codenames = {code for _, _, code in specs}
    lookup = {
        (perm.content_type.app_label, perm.content_type.model, perm.codename): perm
        for perm in Permission.objects.select_related("content_type").filter(
            content_type__app_label__in=app_labels,
            content_type__model__in=models,
            codename__in=codenames,
        )
    }
    missing = [spec for spec in specs if spec not in lookup]
    if missing:
        formatted = ", ".join(f"{app}.{code}" for app, _, code in missing)
        raise LookupError(
            f"Missing Django/Wagtail permissions ({formatted}). Run migrate before initializing groups."
        )
    return [lookup[spec] for spec in specs]


@transaction.atomic
def ensure_default_groups() -> list[GroupSyncResult]:
    """Idempotently create and synchronize the Admin and Analyst groups."""
    results: list[GroupSyncResult] = []
    for group_name, perm_specs in ROLE_PERMISSIONS.items():
        group, created = Group.objects.get_or_create(name=group_name)
        permissions = resolve_permissions(perm_specs)
        group.permissions.set(permissions)
        results.append(
            GroupSyncResult(
                name=group.name,
                created=created,
                permission_count=len(permissions),
            )
        )
    return results
