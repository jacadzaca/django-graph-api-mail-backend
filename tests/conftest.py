import collections
from typing import Any

import pytest


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

    def json(self):
        return self.response

