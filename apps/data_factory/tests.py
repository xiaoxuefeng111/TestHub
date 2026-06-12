from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.data_factory import views as data_factory_views
from apps.data_factory.models import DataFactoryRecord
from apps.data_factory.views import DataFactoryViewSet, _filter_queryset_by_tag


class DataFactoryTagFilterTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = get_user_model().objects.create_user(
            username='data_factory_sqlite_user',
            password='password123'
        )
        cache.clear()

    def test_list_filters_records_by_tag(self):
        matched = DataFactoryRecord.objects.create(
            user=self.user,
            tool_name='matched_record',
            tool_category='string',
            tool_scenario='string',
            input_data={'text': 'hello'},
            output_data={'result': 'ok'},
            tags=['login', 'smoke'],
        )
        DataFactoryRecord.objects.create(
            user=self.user,
            tool_name='unmatched_record',
            tool_category='string',
            tool_scenario='string',
            input_data={'text': 'world'},
            output_data={'result': 'ok'},
            tags=['payment'],
        )
        DataFactoryRecord.objects.create(
            user=self.user,
            tool_name='null_tags_record',
            tool_category='string',
            tool_scenario='string',
            input_data={'text': 'noop'},
            output_data={'result': 'ok'},
            tags=None,
        )

        request = self.factory.get('/api/data-factory/', {'tags__contains': 'login'})
        force_authenticate(request, user=self.user)

        response = DataFactoryViewSet.as_view({'get': 'list'})(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual([item['id'] for item in response.data['results']], [matched.id])

    def test_tag_helper_keeps_contains_lookup_for_mysql(self):
        queryset = mock.Mock()
        sentinel = object()
        queryset.filter.return_value = sentinel

        with mock.patch.object(data_factory_views.connection, 'vendor', 'mysql'):
            result = _filter_queryset_by_tag(queryset, 'login')

        queryset.filter.assert_called_once_with(tags__contains='login')
        self.assertIs(result, sentinel)
