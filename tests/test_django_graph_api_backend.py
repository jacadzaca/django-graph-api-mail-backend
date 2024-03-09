from datetime import datetime, timedelta

import pytest
from django.conf import settings
from requests import RequestException
from django.core.mail.message import EmailMessage

from tests.conftest import MockResponse
from django_graph_api_mail_backend.graph_api_mail_backend import GraphAPIMailBackend
import django_graph_api_mail_backend.graph_api_mail_backend as graph_api_mail_backend

# needed in order to insttiate EmailMessage objects
settings.configure(DEFAULT_CHARSET='utf-8')


class SessionFailingOnAccessingToken:
    def post(self, *_, **__) -> MockResponse:
        return MockResponse(
            response={},
            is_ok=False,
        )


@pytest.mark.parametrize('missing_field', [
    'client_id',
    'client_secret',
    'tenant_id',
])
def test_graph_api_backend_must_be_constructed_with_client_id_client_secret_and_tenant_id(missing_field):
    active_driectory_secrets = {
        'client_id': '123',
        'client_secret': 'asdf123',
        'tenant_id': 'test123',
    }
    active_driectory_secrets.pop(missing_field)
    with pytest.raises(AttributeError):
        GraphAPIMailBackend(**active_driectory_secrets)


def test_open_raises_value_error_when_retriving_token_fails_and_fails_silently_off():
    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id='123-456-789',
        client_secret='asdf123',
        tenant_id='abcd-efgh-hijk',
        create_session=SessionFailingOnAccessingToken,
    )
    with pytest.raises(ValueError):
        backend.open()


def test_open_returns_false_when_retriving_token_fails_and_fail_silently_on():
    backend = GraphAPIMailBackend(
        fail_silently=True,
        client_id='123-456-789',
        client_secret='asdf123',
        tenant_id='abcd-efgh-hijk',
        create_session=SessionFailingOnAccessingToken,
    )
    assert not backend.open()


def test_send_messages_returns_0_when_cannot_open_connection_and_fail_silently_on():
    tenant_id = 'abcd-efgh-hijk',
    backend = GraphAPIMailBackend(
        fail_silently=True,
        client_id='123-456-789',
        client_secret='asdf123',
        tenant_id=tenant_id,
        create_session=SessionFailingOnAccessingToken,
    )
    sent_emails_count = backend.send_messages([
        EmailMessage(
            subject='Some email subject',
            body="Some email body",
            from_email='from_me@example.com',
            to=['recipient1@example.com', 'recipient2@example.com'],
            bcc=['bcc-recipient1@example.com', 'bcc-recipient2@example.com'],
            cc=['cc-recipient1@example.com', 'cc-recipient2@example.com'],
            reply_to=['replayto1@example.com', 'replayto2@example.com'],
        ),
    ])
    assert sent_emails_count == 0


def test_send_messages_refreshes_token_if_it_has_expired():
    tenant_id = 'abcd-efgh-hijk',
    expires_in_seconds = 3736
    access_token = 'abcd123'
    refresh_token = 'refresh-abcd123'
    from_email = 'from_me@example.com'

    times_token_refreshed = 0
    class SessionReturningToken:
        def post(self, url, data, *_, **__) -> MockResponse:
            if url == graph_api_mail_backend.construct_token_endpoint(tenant_id):
                if data['grant_type'] == 'client_credentials':
                    return MockResponse(
                        response={
                            'expires_in': expires_in_seconds,
                            'access_token': access_token,
                            'refresh_token': refresh_token,
                        }
                    )
                elif data['grant_type'] == 'refresh_token':
                    nonlocal times_token_refreshed
                    times_token_refreshed += 1
                    return MockResponse(
                        response={
                            'expires_in': expires_in_seconds,
                            'access_token': access_token,
                            'refresh_token': refresh_token,
                        }
                    )
                else:
                    raise ValueError(f'improper grant_type in request to {url} with payload {data}')
            elif graph_api_mail_backend.construct_send_email_endpoint(from_email):
                return MockResponse(
                    is_ok=True,
                    status_code=200,
                )
            else:
                raise ValueError('not get/refresh token endpoint')
    
    start = datetime(year=2002, month=7, day=22, hour=12, minute=00, second=00)
    time_moments = iter([
        start,
        start + timedelta(seconds=expires_in_seconds // 3),
        start + timedelta(seconds=expires_in_seconds // 2),
        start + timedelta(seconds=expires_in_seconds),
        # the last one's for _refresh_token to get it's timestmap
        start + timedelta(seconds=expires_in_seconds),
    ])
    def get_now():
        return next(time_moments)

    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id='123-456-789',
        client_secret='asdf123',
        tenant_id=tenant_id,
        get_now=get_now,
        create_session=SessionReturningToken,
    )
    backend.send_messages([
        EmailMessage(
            subject='Some email subject',
            body="Some email body",
            from_email=from_email,
            to=['recipient1@example.com', 'recipient2@example.com'],
            bcc=['bcc-recipient1@example.com', 'bcc-recipient2@example.com'],
            cc=['cc-recipient1@example.com', 'cc-recipient2@example.com'],
            reply_to=['replayto1@example.com', 'replayto2@example.com'],
        ),
    ] * 3)

    assert times_token_refreshed == 1


def test_send_messages_returns_count_of_succesfuly_sent_emails():
    tenant_id = 'tenatn-id-abcd'
    from_email = 'from@example.com'
    class SessionFailingOneEmailSent:
        def __init__(self):
            self.post_count = 0

        def post(self, url, data, *_, **__):
            if url == graph_api_mail_backend.construct_send_email_endpoint(from_email):
                self.post_count += 1
                if self.post_count == 1:
                    return MockResponse(
                        is_ok=False,
                        status_code=500,
                    )
                else:
                    return MockResponse(
                        is_ok=True,
                        status_code=200,
                    )
            elif url == graph_api_mail_backend.construct_token_endpoint(tenant_id):
                return MockResponse(
                    response={
                        'expires_in': 3675,
                        'access_token': 'access_token',
                        'refresh_token': 'refrest-token',
                    }
                )
            else:
                raise ValueError(f'Not send email endpoint nor acces token endpoint: {url}')

    backend = GraphAPIMailBackend(
        client_id='123-456-789',
        client_secret='asdf123',
        tenant_id=tenant_id,
        create_session=SessionFailingOneEmailSent,
    )
    to_send = [
        EmailMessage(
            subject='Some email subject',
            body="Some email body",
            from_email=from_email,
            to=['recipient1@example.com', 'recipient2@example.com'],
            bcc=['bcc-recipient1@example.com', 'bcc-recipient2@example.com'],
            cc=['cc-recipient1@example.com', 'cc-recipient2@example.com'],
            reply_to=['replayto1@example.com', 'replayto2@example.com'],
        ),
    ] * 3
    successfully_sent_count = backend.send_messages(to_send)
    assert successfully_sent_count == len(to_send) - 1


def test_send_messages_raises_value_error_when_refresh_token_fails_and_fails_silently_off():
    class SessionFailingOnRefreshingToken:
        def __init__(self):
            self.post_count = 0

        def post(self, *_, **__):
            if self.post_count > 0:
                return MockResponse(is_ok=False)
            else:
                self.post_count += 1
                return MockResponse(
                    is_ok=True,
                    response={
                        'expires_in': 0,
                        'access_token': 'access_token',
                        'refresh_token': 'refrest-token',
                    }
                )

    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id='123-456-789',
        client_secret='asdf123',
        tenant_id='tenant-asdf',
        create_session=SessionFailingOnRefreshingToken,
    )
    with pytest.raises(ValueError):
        backend.send_messages([
            EmailMessage(
                subject='Some email subject',
                body="Some email body",
                from_email='from@example.com',
                to=['recipient1@example.com', 'recipient2@example.com'],
                bcc=['bcc-recipient1@example.com', 'bcc-recipient2@example.com'],
                cc=['cc-recipient1@example.com', 'cc-recipient2@example.com'],
                reply_to=['replayto1@example.com', 'replayto2@example.com'],
            )
        ])


def test_open_swallows_requests_exceptions_when_fail_silently_on():
    class SessionThrowingException:
        def post(self, url, data, *_, **__):
            raise RequestException('some problem occured')
    backend = GraphAPIMailBackend(
        fail_silently=True,
        client_id='123-456-789',
        client_secret='asdf123',
        tenant_id='abcd-efgh-hijk',
        create_session=SessionThrowingException,
    )
    assert not backend.open()

