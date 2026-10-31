"""
Custom DRF permissions for the catalog domain.

The stock ``DjangoModelPermissions`` leaves ``GET`` ungated (``perms_map["GET"]``
is empty), which would let *any* authenticated user list draft products through
the ``/api/v1/catalog/manage/`` endpoints. Because the manage views intentionally
expose unpublished records, read access must also be permission-checked. The
subclass below maps ``GET``/``HEAD``/``OPTIONS`` to the model's ``view``
permission so that staff need explicit catalog view rights — ``is_staff`` alone
is never sufficient.
"""

from rest_framework.permissions import DjangoModelPermissions


class ManageModelPermissions(DjangoModelPermissions):
    """
    Model-permission enforcement for staff catalog management endpoints.

    Extends ``DjangoModelPermissions`` so that read methods additionally require
    the ``view_<model>`` permission. This ensures draft/unpublished records are
    only visible to users explicitly granted view rights on the catalog models,
    rather than to any logged-in account.
    """

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": [],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }
