import urllib.request
import urllib.error
import urllib.parse
import base64
import json
import time
import ssl
from typing import Optional, Any
from snipglide.models.api_request import ApiResponse
from snipglide.utils.logger import logger

_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB safety limit


class ApiClientService:
    """Core network execution service for REST API Tester."""

    @staticmethod
    def build_final_url(
        base_url: str,
        params: list[dict[str, Any]],
        auth_type: str = "none",
        auth_data: Optional[dict[str, str]] = None
    ) -> str:
        """
        Combines base URL with query parameters and optional query-based API key.
        Handles existing query parameters in base_url gracefully.
        """
        url = base_url.strip() if base_url else ""
        if not url:
            return ""

        # Ensure scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urllib.parse.urlparse(url)
        existing_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query_list: list[tuple[str, str]] = list(existing_params)

        for p in params or []:
            if p.get("enabled", True):
                k = str(p.get("key", "")).strip()
                v = str(p.get("value", ""))
                if k:
                    query_list.append((k, v))

        # Query-based API Key
        if auth_type == "api_key" and auth_data:
            add_to = auth_data.get("add_to", "header")
            if add_to == "query":
                k = auth_data.get("key", "").strip()
                v = auth_data.get("value", "")
                if k:
                    query_list.append((k, v))

        new_query = urllib.parse.urlencode(query_list)
        reconstructed = urllib.parse.urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        ))
        return reconstructed

    @staticmethod
    def build_headers(
        headers: list[dict[str, Any]],
        auth_type: str = "none",
        auth_data: Optional[dict[str, str]] = None,
        body_type: str = "none"
    ) -> dict[str, str]:
        """
        Builds dictionary of request headers, including content-type and authentication.
        """
        out: dict[str, str] = {
            "User-Agent": "SnipGlide-Pro-ApiTester/2.0",
            "Accept": "*/*"
        }

        # Content-Type defaults
        if body_type == "json":
            out["Content-Type"] = "application/json; charset=utf-8"
        elif body_type == "form_urlencoded":
            out["Content-Type"] = "application/x-www-form-urlencoded"
        elif body_type == "raw":
            out["Content-Type"] = "text/plain; charset=utf-8"

        # User headers
        for h in headers or []:
            if h.get("enabled", True):
                k = str(h.get("key", "")).strip()
                v = str(h.get("value", ""))
                if k:
                    out[k] = v

        # Authentication headers
        if auth_data:
            if auth_type == "bearer":
                token = auth_data.get("token", "").strip()
                if token:
                    out["Authorization"] = f"Bearer {token}"
            elif auth_type == "basic":
                user = auth_data.get("username", "")
                pw = auth_data.get("password", "")
                encoded = base64.b64encode(f"{user}:{pw}".encode("utf-8")).decode("ascii")
                out["Authorization"] = f"Basic {encoded}"
            elif auth_type == "api_key":
                if auth_data.get("add_to", "header") == "header":
                    k = auth_data.get("key", "").strip()
                    v = auth_data.get("value", "")
                    if k:
                        out[k] = v

        return out

    @staticmethod
    def prepare_body(body_type: str, body_content: str) -> Optional[bytes]:
        """Prepares raw bytes payload from body type and text content."""
        if not body_type or body_type == "none" or not body_content:
            return None
        return body_content.encode("utf-8")

    @staticmethod
    def execute_request(
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        body_bytes: Optional[bytes] = None,
        timeout: float = 15.0
    ) -> ApiResponse:
        """
        Executes HTTP request synchronously. Should be called inside a QThread worker.
        Returns clean ApiResponse without raising uncaught exceptions.
        """
        clean_method = method.upper().strip()
        headers = headers or {}

        if not url:
            return ApiResponse(is_error=True, error_message="URL cannot be empty.")

        # SSL Context (Standard verify with fallback)
        ssl_ctx = ssl.create_default_context()

        req = urllib.request.Request(
            url=url,
            data=body_bytes if clean_method in ("POST", "PUT", "PATCH", "DELETE") else None,
            headers=headers,
            method=clean_method
        )

        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as response:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                raw_data = response.read(_MAX_RESPONSE_BYTES + 1)

                is_truncated = False
                if len(raw_data) > _MAX_RESPONSE_BYTES:
                    raw_data = raw_data[:_MAX_RESPONSE_BYTES]
                    is_truncated = True

                content_type = response.headers.get("Content-Type", "text/plain")
                resp_headers = dict(response.headers)
                charset = response.headers.get_content_charset() or "utf-8"

                try:
                    body_text = raw_data.decode(charset, errors="replace")
                except Exception:
                    body_text = raw_data.decode("utf-8", errors="replace")

                if is_truncated:
                    body_text += "\n\n[⚠️ Response was truncated at 5MB limit]"

                return ApiResponse(
                    status_code=response.status,
                    status_text=response.reason or "OK",
                    headers=resp_headers,
                    body=body_text,
                    response_time_ms=round(duration_ms, 2),
                    response_size_bytes=len(raw_data),
                    content_type=content_type,
                    is_error=False,
                )

        except urllib.error.HTTPError as e:
            try:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                raw_err_data = e.read(_MAX_RESPONSE_BYTES)
                charset = e.headers.get_content_charset() or "utf-8" if e.headers else "utf-8"
                body_text = raw_err_data.decode(charset, errors="replace")
                content_type = e.headers.get("Content-Type", "text/plain") if e.headers else "text/plain"

                return ApiResponse(
                    status_code=e.code,
                    status_text=e.reason or "HTTP Error",
                    headers=dict(e.headers) if e.headers else {},
                    body=body_text,
                    response_time_ms=round(duration_ms, 2),
                    response_size_bytes=len(raw_err_data),
                    content_type=content_type,
                    is_error=False,  # An HTTP 4xx or 5xx is still a valid HTTP response to display
                )
            finally:
                try:
                    e.close()
                except Exception:
                    pass

        except urllib.error.URLError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            reason = str(e.reason)
            err_msg = f"Network Connection Failed: {reason}"
            if "getaddrinfo failed" in reason.lower() or "nameresolution" in reason.lower():
                err_msg = f"DNS Resolution Error: Could not resolve host for URL '{url}'"
            elif "timed out" in reason.lower():
                err_msg = f"Request Timed Out after {timeout} seconds."
            elif "connection refused" in reason.lower():
                err_msg = "Connection Refused: Target server rejected connection or is offline."
            elif "certificate" in reason.lower():
                err_msg = f"SSL Certificate Error: {reason}"

            return ApiResponse(
                is_error=True,
                error_message=err_msg,
                response_time_ms=round(duration_ms, 2),
            )

        except TimeoutError:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ApiResponse(
                is_error=True,
                error_message=f"Request Timed Out after {timeout} seconds.",
                response_time_ms=round(duration_ms, 2),
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ApiResponse(
                is_error=True,
                error_message=f"Request Error: {str(e)}",
                response_time_ms=round(duration_ms, 2),
            )

    @staticmethod
    def generate_curl_command(
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        body_content: str = ""
    ) -> str:
        """Generates standard cURL command line representation."""
        parts = ["curl", "-X", method.upper(), f'"{url}"']
        for k, v in (headers or {}).items():
            parts.append(f'-H "{k}: {v}"')
        if body_content and method.upper() in ("POST", "PUT", "PATCH", "DELETE"):
            # Escape quotes
            escaped = body_content.replace('"', '\\"').replace("\n", "\\n")
            parts.append(f'-d "{escaped}"')
        return " ".join(parts)

    @staticmethod
    def sanitize_headers_for_display(headers: dict[str, str]) -> dict[str, str]:
        """Masks sensitive authentication tokens for secure display/logging."""
        masked = {}
        sensitive_keys = {"authorization", "x-api-key", "api-key", "token", "apikey", "secret"}
        for k, v in headers.items():
            if k.lower() in sensitive_keys:
                if len(v) > 8:
                    masked[k] = v[:4] + "..." + v[-4:]
                else:
                    masked[k] = "******"
            else:
                masked[k] = v
        return masked
