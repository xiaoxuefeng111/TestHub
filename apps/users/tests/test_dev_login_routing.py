from django.test import SimpleTestCase
from django.urls import resolve

from apps.users.views import dev_login_view


class DevLoginRoutingTests(SimpleTestCase):
    def test_dev_login_routes_resolve_to_dev_login_view(self):
        for path in ('/api/auth/dev-login/', '/api/users/dev-login/'):
            with self.subTest(path=path):
                self.assertIs(resolve(path).func, dev_login_view)
