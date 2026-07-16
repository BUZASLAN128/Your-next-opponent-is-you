from __future__ import annotations

import json
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from ynoy.errors import AdapterError
from ynoy.policy import is_loopback_url

MAX_LOCAL_HTTP_REQUEST_BYTES = 2 * 1024 * 1024


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        del req, fp, code, msg, headers, newurl
        return None


def post_json(
    endpoint: str,
    payload: object,
    *,
    timeout_seconds: float,
    max_response_bytes: int,
    error_prefix: str,
) -> object:
    raw_request = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(raw_request) > MAX_LOCAL_HTTP_REQUEST_BYTES:
        raise AdapterError(
            f"{error_prefix}_request_too_large",
            "The bounded loopback adapter request is too large.",
        )
    request = Request(
        endpoint,
        method="POST",
        data=raw_request,
        headers={"Content-Type": "application/json"},
    )
    raw_response = _open_bounded(request, timeout_seconds, max_response_bytes, error_prefix)
    if len(raw_response) > max_response_bytes:
        raise AdapterError(
            f"{error_prefix}_response_too_large",
            "The loopback adapter response exceeded its byte limit.",
        )
    try:
        return json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdapterError(
            f"{error_prefix}_schema_invalid",
            "The loopback adapter response was not valid UTF-8 JSON.",
        ) from exc


def _open_bounded(
    request: Request,
    timeout_seconds: float,
    max_response_bytes: int,
    error_prefix: str,
) -> bytes:
    try:
        opener = build_opener(ProxyHandler({}), NoRedirectHandler())
        with opener.open(request, timeout=timeout_seconds) as response:
            if not is_loopback_url(response.geturl()):
                raise AdapterError(
                    f"{error_prefix}_redirect_blocked",
                    "The loopback adapter attempted to leave the local transport boundary.",
                )
            return cast(bytes, response.read(max_response_bytes + 1))
    except AdapterError:
        raise
    except HTTPError as exc:
        if 300 <= exc.code < 400:
            raise AdapterError(
                f"{error_prefix}_redirect_blocked",
                "The loopback adapter refused an HTTP redirect.",
            ) from exc
        raise AdapterError(
            f"{error_prefix}_failed", "The bounded loopback adapter request failed."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AdapterError(
            f"{error_prefix}_failed", "The bounded loopback adapter request failed."
        ) from exc
