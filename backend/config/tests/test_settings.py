"""
Guard tests for environment-driven settings.

These catch two classes of configuration error early instead of at first
request time:

1. A ``DATABASE_URL`` with unencoded special characters (e.g. a raw '@' in the
   password), which parses into a truncated password and causes confusing
   authentication failures.
2. A database that is unreachable with the configured credentials.
"""

import re

import pytest
from django.conf import settings
from django.db import connection


class TestDatabaseConfiguration:
    """Verify the parsed database configuration is internally consistent."""

    def test_database_password_has_no_unencoded_at_sign(self):
        """
        A raw '@' inside the password portion of DATABASE_URL is ambiguous:
        URL parsing splits userinfo at the last '@', silently truncating the
        password. Special characters must be percent-encoded ('%40').

        This checks the parsed password against the original environment
        variable so an unencoded URL fails loudly here rather than as a
        mysterious connection error later.
        """
        import os
        from urllib.parse import unquote

        parsed_password = settings.DATABASES["default"].get("PASSWORD")
        env_url = os.environ.get("DATABASE_URL", "")
        if env_url:
            # Isolate the authority section (between "://" and the first "/").
            # An unencoded '@' is the userinfo/host delimiter, and parsers
            # split at the LAST '@'. So two or more unencoded '@' characters
            # make the URL ambiguous and silently truncate the password.
            authority = env_url.split("://", 1)[-1].split("/", 1)[0]
            unencoded_at_count = authority.count("@")
            assert unencoded_at_count <= 1, (
                "DATABASE_URL authority contains {count} unencoded '@' "
                "characters; the password will be truncated during parsing. "
                "Percent-encode special characters (e.g. '@' -> '%40').".format(
                    count=unencoded_at_count
                )
            )

            # Round-trip check: the decoded password from the URL must match
            # the password Django actually parsed.
            userinfo = authority.rsplit("@", 1)[0]
            if ":" in userinfo:
                encoded_password = userinfo.split(":", 1)[1]
            else:
                pytest.skip("DATABASE_URL contains no password to verify.")
            assert unquote(encoded_password) == parsed_password, (
                "DATABASE_URL password was truncated during parsing. "
                "Percent-encode special characters (e.g. '@' -> '%40')."
            )

    def test_database_target_configuration(self):
        """Verify the essential connection parameters were parsed."""
        db = settings.DATABASES["default"]
        assert db["ENGINE"] == "django.db.backends.postgresql"
        assert db["NAME"], "Database name must not be empty."
        assert db["HOST"], "Database host must not be empty."
        assert isinstance(db["PORT"], int) and db["PORT"] > 0

    @pytest.mark.django_db
    def test_database_connection_succeeds(self):
        """Verify PostgreSQL is reachable with the configured credentials."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
