import base64
import collections
from typing import Callable
from datetime import datetime, timedelta

from requests import Session
from django.conf import settings
from django.core.mail.message import EmailMessage
from django.core.mail.backends.base import BaseEmailBackend

# expires_in is in seconds
# https://learn.microsoft.com/en-us/graph/auth-v2-user?tabs=http#token-response
GraphAPIAccessToken = collections.namedtuple('GraphAPIAccessToken', ['value', 'expires_in', 'refresh_token', 'access_timestamp'])


def construct_token_endpoint(tenant_id: str):
    return f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'

def construct_send_email_endpoint(from_email: str):
    return f'https://graph.microsoft.com/v1.0/users/{from_email}/sendMail'


# https://learn.microsoft.com/en-us/graph/api/user-sendmail
# reference: https://github.com/django/django/blob/bcccea3ef31c777b73cba41a6255cd866bf87237/django/core/mail/backends/smtp.py
class GraphAPIMailBackend(BaseEmailBackend):
    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        tenant_id: str | None = None,
        fail_silently: bool = False,
        authority: str = None,
        get_now: Callable[[], datetime] = datetime.now,
        create_session: Callable[[], Session] = Session,
    ) -> None:
        super().__init__(fail_silently=fail_silently)
        self._client_id = client_id or settings.ADFS_CLIENT_ID
        self._client_secret = client_secret or settings.ADFS_CLIENT_SECRET
        self._authority = construct_token_endpoint(tenant_id or settings.ADFS_TENANT_ID)
        self._access_token: GraphAPIAccessToken | None = None 
        self._http_session: Session | None = None
        self._create_session = create_session
        self._get_now = get_now

    def open(self) -> bool:
        if self._http_session is not None:
            return False
        self._http_session = self._create_session() 
        try:
            self._access_token = self._retrive_access_token()
        except ValueError:
            if not self.fail_silently:
                raise
            return False
        self._http_session.headers = {
            'Content-Type': 'text/plain',
            'Authorization': f'Bearer {self._access_token.value}',
        }
        return True

    def _retrive_access_token(self) -> GraphAPIAccessToken | None:
        # https://learn.microsoft.com/en-us/graph/auth-v2-user?tabs=http#token-request
        response = self._http_session.post(
            url=self._authority,
            data={
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'grant_type': 'client_credentials',
                'scope': 'https://graph.microsoft.com/.default',
            },
        )
        if response.ok:
            response = response.json()
        else:
            raise ValueError(
                f'Cannot generate ADFS access token. Authority saying: {response.reason} ({response.status_code}) '
                f'Response body: {response.content}'
            )

        # https://learn.microsoft.com/en-us/graph/auth-v2-user?tabs=http#token-response
        return GraphAPIAccessToken(
            value=response['access_token'],
            expires_in=response['expires_in'],
            refresh_token=response['refresh_token'],
            access_timestamp=self._get_now(),
        )

    def _refresh_access_token(self) -> GraphAPIAccessToken:
        # https://learn.microsoft.com/en-us/graph/auth-v2-user?tabs=http#request-1
        response = self._http_session.post(
            url=self._authority,
            data={
                'grant_type': 'refresh_token',
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'refresh_token': self._access_token.refresh_token ,
            },
        )
        if response.ok:
            response = response.json()
        else:
            raise ValueError(
                f'Cannot refresh ADFS access token. Authority saying: {response.reason} ({response.status_code}) '
                f'Response body: {response.content}'
            )
        # https://learn.microsoft.com/en-us/graph/auth-v2-user?tabs=http#response-1
        return GraphAPIAccessToken(
            value=response['access_token'],
            expires_in=response['expires_in'],
            refresh_token=response['refresh_token'],
            access_timestamp=self._get_now(),
        )

    def close(self) -> None:
        self._http_session.close()

    def send_messages(
        self,
        email_messages: list[EmailMessage],
    ) -> int:
        failed_silently = not self.open() and self._access_token is None
        if failed_silently:
            return 0 
        sent_count = 0
        for email_message in email_messages:
            if self._access_token.access_timestamp + timedelta(seconds=self._access_token.expires_in) <= self._get_now():
                self._access_token = self._refresh_access_token()
            response = self._http_session.post(
                url=construct_send_email_endpoint(email_message.from_email),
                data=base64.b64encode(
                    email_message.message().as_bytes(linesep='\r\n')
                ),
            )
            if response.ok:
                sent_count += 1
        return sent_count

