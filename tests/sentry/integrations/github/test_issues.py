from __future__ import absolute_import

import responses

from mock import patch
from exam import fixture
from django.test import RequestFactory

from sentry.integrations.github.integration import GitHubIntegration
from sentry.models import Integration
from sentry.testutils import TestCase
from sentry.utils import json


class GitHubIssueBasicTest(TestCase):
    @fixture
    def request(self):
        return RequestFactory()

    def setUp(self):
        self.user = self.create_user()
        self.organization = self.create_organization(owner=self.user)
        model = Integration.objects.create(
            provider='github',
            external_id='github_external_id',
            name='getsentry',
        )
        model.add_organization(self.organization.id)
        self.integration = GitHubIntegration(model, self.organization.id)

    @responses.activate
    @patch('sentry.integrations.github.client.get_jwt', return_value='jwt_token_1')
    def test_create_issue(self, mock_get_jwt):
        responses.add(
            responses.POST,
            'https://api.github.com/installations/github_external_id/access_tokens',
            json={'token': 'token_1', 'expires_at': '2018-10-11T22:14:10Z'}
        )

        responses.add(
            responses.POST,
            'https://api.github.com/repos/getsentry/sentry/issues',
            json={'number': 321, 'title': 'hello', 'body': 'This is the description'}
        )

        form_data = {
            'repo': 'getsentry/sentry',
            'title': 'hello',
            'description': 'This is the description',
        }

        assert self.integration.create_issue(form_data) == {
            'key': 321,
            'description': 'This is the description',
            'title': 'hello',
            'repo': 'getsentry/sentry',
        }
        request = responses.calls[0].request
        assert request.headers['Authorization'] == 'Bearer jwt_token_1'

        request = responses.calls[1].request
        assert request.headers['Authorization'] == 'token token_1'
        payload = json.loads(request.body)
        assert payload == {'body': 'This is the description', 'assignee': None, 'title': 'hello'}

    @responses.activate
    @patch('sentry.integrations.github.client.get_jwt', return_value='jwt_token_1')
    def test_link_issue(self, mock_get_jwt):
        issue_id = 321
        responses.add(
            responses.POST,
            'https://api.github.com/installations/github_external_id/access_tokens',
            json={'token': 'token_1', 'expires_at': '2018-10-11T22:14:10Z'}
        )

        responses.add(
            responses.GET,
            'https://api.github.com/repos/getsentry/sentry/issues/321',
            json={'number': issue_id, 'title': 'hello', 'body': 'This is the description'}
        )

        responses.add(
            responses.POST,
            'https://api.github.com/repos/getsentry/sentry/issues/321/comments',
            json={'body': 'hello'}
        )

        data = {
            'repo': 'getsentry/sentry',
            'externalIssue': issue_id,
            'comment': 'hello',
        }

        assert self.integration.get_issue(issue_id, data=data) == {
            'key': issue_id,
            'description': 'This is the description',
            'title': 'hello',
            'repo': 'getsentry/sentry',
        }
        request = responses.calls[0].request
        assert request.headers['Authorization'] == 'Bearer jwt_token_1'

        request = responses.calls[1].request
        assert request.headers['Authorization'] == 'token token_1'

        request = responses.calls[-1].request
        assert request.headers['Authorization'] == 'token token_1'
        payload = json.loads(request.body)
        assert payload == {'body': 'hello'}
