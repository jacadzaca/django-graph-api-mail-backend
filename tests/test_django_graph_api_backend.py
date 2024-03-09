from datetime import datetime, timedelta

import pytest
from requests import RequestException
from django.core.mail.message import EmailMessage

from tests.conftest import MockResponse, MockSession
from django_graph_api_mail_backend.graph_api_mail_backend import GraphAPIMailBackend


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
    mock_http_session = MockSession(
        fail_token_access=True,
    )
    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    with pytest.raises(ValueError):
        backend.open()


def test_open_returns_false_when_retriving_token_fails_and_fail_silently_on():
    mock_http_session = MockSession(
        fail_token_access=True,
    )
    backend = GraphAPIMailBackend(
        fail_silently=True,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    assert not backend.open()


def test_send_messages_returns_0_when_cannot_open_connection_and_fail_silently_on(
    example_message: EmailMessage,
):
    mock_http_session = MockSession(
        fail_token_access=True,
    )
    backend = GraphAPIMailBackend(
        fail_silently=True,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    sent_emails_count = backend.send_messages([example_message])
    assert sent_emails_count == 0


def test_send_messages_refreshes_token_if_it_has_expired(
    example_message: EmailMessage,
):
    mock_http_session = MockSession()
    start = datetime(year=2002, month=7, day=22, hour=12, minute=00, second=00)
    time_moments = iter([
        start,
        start + timedelta(seconds=mock_http_session.expires_in_seconds // 3),
        start + timedelta(seconds=mock_http_session.expires_in_seconds // 2),
        # token should be considered expired here
        start + timedelta(seconds=mock_http_session.expires_in_seconds),
        # the last one's for _refresh_token to get it's timestmap
        start + timedelta(seconds=mock_http_session.expires_in_seconds),
    ])
    def get_now():
        return next(time_moments)

    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        get_now=get_now,
        create_session=lambda: mock_http_session,
    )
    backend.send_messages([example_message] * 3)
    assert mock_http_session.times_token_refreshed == 1


def test_send_messages_returns_count_of_succesfuly_sent_emails(
    example_message: EmailMessage,
):
    mock_http_session = MockSession(
        max_email_sents=2,
    )
    backend = GraphAPIMailBackend(
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    to_send = [example_message] * 3
    successfully_sent_count = backend.send_messages(to_send)
    assert successfully_sent_count == len(to_send) - 1


def test_send_messages_raises_value_error_when_refresh_token_fails_and_fails_silently_off(
    example_message: EmailMessage,
):
    mock_http_session = MockSession(
        fail_token_refresh=True,
        expires_in_seconds=0,
    )
    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    with pytest.raises(ValueError):
        backend.send_messages([example_message])


def test_open_swallows_requests_exceptions_when_fail_silently_on():
    mock_http_session = MockSession(
        raise_request_exception_on_post=True,
    )
    backend = GraphAPIMailBackend(
        fail_silently=True,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    assert not backend.open()


@pytest.mark.parametrize('fail_sent_mail, fail_token_refresh', [
    (False, True),
    (True, False),
])
def test_send_messages_swallows_requests_exceptions_when_fail_silently_on(
    example_message: EmailMessage,
    fail_sent_mail: bool,
    fail_token_refresh: bool,
):
    mock_http_session = MockSession(
        raise_request_exception_on_sent_mail=fail_sent_mail,
        fail_token_refresh=fail_token_refresh,
        # set so token is refreshed so to test case when refreshing token fails
        expires_in_seconds=0,
    )
    backend = GraphAPIMailBackend(
        fail_silently=True,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    successfully_sent_count = backend.send_messages([example_message])
    assert successfully_sent_count == 0


def test_send_messages_tries_to_send_all_messages_when_fail_silently_on(
    example_message: EmailMessage,
):
    mock_http_session = MockSession(
        raise_request_exception_on_sent_mail=True,
    )
    backend = GraphAPIMailBackend(
        fail_silently=True,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    to_send = [example_message] * 3
    backend.send_messages(to_send)
    # the - 1 is there to account for token acqusition request
    assert (mock_http_session.post_call_count - 1) == len(to_send)


@pytest.mark.parametrize('expected_exception, fail_sent_mail, fail_token_refresh', [
    (ValueError, False, True),
    (RequestException, True, False),
])
def test_send_messages_raises_exception_on_error_when_fail_silently_off(
    expected_exception: type[Exception],
    fail_sent_mail: bool,
    fail_token_refresh: bool,
    example_message: EmailMessage,
):
    mock_http_session = MockSession(
        raise_request_exception_on_sent_mail=fail_sent_mail,
        fail_token_refresh=fail_token_refresh,
        # set so token is refreshed so to test case when refreshing token fails
        expires_in_seconds=0,
    )
    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    with pytest.raises(expected_exception):
        backend.send_messages([example_message])


def test_emails_without_recipients_are_not_sent(
    example_message: EmailMessage,
):
    example_message.to = [] 
    example_message.cc = [] 
    example_message.bcc = [] 
    mock_http_session = MockSession()
    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    sent_emails_count = backend.send_messages([example_message])
    assert sent_emails_count == 0


def test_email_is_extracted_from_from_email_in_name_form(
    example_message: EmailMessage,
):
    example_message.from_email = f'Fred <{example_message.from_email}>'
    mock_http_session = MockSession()
    backend = GraphAPIMailBackend(
        fail_silently=False,
        client_id=mock_http_session.client_id,
        client_secret=mock_http_session.client_secret,
        tenant_id=mock_http_session.tenant_id,
        create_session=lambda: mock_http_session,
    )
    backend.send_messages([example_message])

