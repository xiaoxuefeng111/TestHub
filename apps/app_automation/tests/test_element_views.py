import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.app_automation.models import AppElement
from apps.app_automation.views import element_views
from apps.app_automation.views.element_views import AppElementViewSet, _search_queryset_by_name_or_tag


class AppElementSearchTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            username='app_element_sqlite_user',
            password='password123'
        )

    def test_list_search_matches_name_or_exact_tag(self):
        AppElement.objects.create(
            name='login_button',
            element_type='image',
            tags=['smoke'],
            config={},
            created_by=self.user,
            is_active=True,
        )
        AppElement.objects.create(
            name='dashboard_button',
            element_type='image',
            tags=['login', 'home'],
            config={},
            created_by=self.user,
            is_active=True,
        )
        AppElement.objects.create(
            name='payment_button',
            element_type='image',
            tags=['payment'],
            config={},
            created_by=self.user,
            is_active=True,
        )

        request = self.factory.get('/api/app-automation/elements/', {'search': 'login'})
        force_authenticate(request, user=self.user)

        response = AppElementViewSet.as_view({'get': 'list'})(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)
        self.assertSetEqual(
            {item['name'] for item in response.data['results']},
            {'login_button', 'dashboard_button'},
        )

    def test_search_helper_keeps_mysql_json_contains_path(self):
        queryset = mock.Mock()
        sentinel = object()
        queryset.extra.return_value = sentinel

        with mock.patch.object(element_views.connection, 'vendor', 'mysql'):
            result = _search_queryset_by_name_or_tag(queryset, 'login')

        queryset.extra.assert_called_once_with(
            where=["name LIKE %s OR JSON_CONTAINS(tags, %s)"],
            params=['%login%', json.dumps('login')],
        )
        self.assertIs(result, sentinel)
