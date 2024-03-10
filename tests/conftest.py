import collections
from typing import Any

import pytest
from django.conf import settings
from requests import RequestException, HTTPError
from django.core.mail.message import EmailMessage

import django_graph_api_mail_backend.graph_api_mail_backend as graph_api_mail_backend

# needed in order to insttiate EmailMessage objects
settings.configure(DEFAULT_CHARSET='utf-8')


class MockResponse:
    def __init__(
        self,
        content: str = '',
        is_ok: bool = True,
        reason: str = 'OK',
        status_code: int = 200,
        response: dict[str, Any] | None = None
    ):
        self.ok = is_ok
        self.response = response
        self.content = content
        self.reason = reason
        self.status_code = status_code

    def raise_for_status(self):
        if not self.ok:
            raise HTTPError('some error occurred')

    def json(self):
        return self.response


class MockSession:
    def __init__(
        self,
        fail_token_access=False,
        fail_token_refresh=False,
        max_email_sents=None,
        expires_in_seconds=3736,
        access_token='abcd123',
        refresh_token='refresh-abcd123',
        tenant_id='abcd-efgh-hijk',
        client_id='123-456-789',
        client_secret='asdf123',
        raise_request_exception_on_post=False,
        raise_request_exception_on_sent_mail=False,
        raise_request_exception_on_refresh_token=False,
        allowed_from_mails=None
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.max_email_sents = max_email_sents
        self.fail_token_access= fail_token_access
        self.fail_token_refresh = fail_token_refresh
        self.expires_in_seconds = expires_in_seconds
        self.raise_request_exception_on_post = raise_request_exception_on_post
        self.raise_request_exception_on_sent_mail = raise_request_exception_on_sent_mail
        self.times_token_refreshed = 0
        self.post_call_count = 0
        self.sent_emails = 0
        self.allowed_from_mails = allowed_from_mails or {
            graph_api_mail_backend.construct_send_email_endpoint('from_me@example.com'),
        }

    def post(self, url, data, *_, **__):
        self.post_call_count += 1
        if self.raise_request_exception_on_post:
            raise RequestException('some error occurred')
        if url == graph_api_mail_backend.construct_token_endpoint(self.tenant_id):
            # https://learn.microsoft.com/en-us/graph/auth-v2-user?tabs=http#token-response
            if data['grant_type'] == 'client_credentials':
                if self.fail_token_access:
                    return MockResponse(
                        is_ok=False,
                        status_code=500,
                    )
                return MockResponse(
                    response={
                        'expires_in': self.expires_in_seconds,
                        'access_token': self.access_token,
                        'refresh_token': self.refresh_token,
                    }
                )
            # https://learn.microsoft.com/en-us/graph/auth-v2-user?tabs=http#response-1
            elif data['grant_type'] == 'refresh_token':
                self.times_token_refreshed += 1
                if self.fail_token_refresh:
                    return MockResponse(
                        is_ok=False,
                        status_code=500,
                    )
                return MockResponse(
                    response={
                        'expires_in': self.expires_in_seconds,
                        'access_token': self.access_token,
                        'refresh_token': self.refresh_token,
                    }
                )
            else:
                raise ValueError(f'improper grant_type in request to {url} with payload {data}')
        # https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0&tabs=http#response
        elif url in self.allowed_from_mails:
            if self.raise_request_exception_on_sent_mail:
                raise RequestException('some error occurred')
            if self.max_email_sents is not None and self.sent_emails >= self.max_email_sents:
                return MockResponse(
                    is_ok=False,
                    status_code=500,
                )
            self.sent_emails += 1
            return MockResponse(
                is_ok=True,
                status_code=202,
            )
        else:
            raise ValueError(f'{url} is not recognized!')


@pytest.fixture
def example_message():
    return EmailMessage(
        subject='Some email subject',
        body="Some email body",
        from_email='from_me@example.com',
        to=['recipient1@example.com', 'recipient2@example.com'],
        bcc=['bcc-recipient1@example.com', 'bcc-recipient2@example.com'],
        cc=['cc-recipient1@example.com', 'cc-recipient2@example.com'],
        reply_to=['replayto1@example.com', 'replayto2@example.com'],
    )

