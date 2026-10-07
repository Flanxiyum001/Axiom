"""Nebius Storage S3-compatible client with AWS Signature V4 signing.

This module provides a minimal S3-compatible client for Nebius Object Storage
that implements AWS Signature Version 4 (SigV4) for request authentication.
It uses only Python standard library and httpx (already a project dependency).

No external S3 libraries (boto3, botocore) are required.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import httpx2 as httpx

if TYPE_CHECKING:
    from axiom.config import Settings

logger = logging.getLogger(__name__)


class NebiusStorageError(Exception):
    """Base exception for Nebius Storage errors."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NebiusStorageAuthError(NebiusStorageError):
    """Authentication/authorization error (401, 403)."""

    def __init__(self, message: str = "Authentication failed", status_code: Optional[int] = None) -> None:
        super().__init__(message, status_code)


class NebiusStorageNotFoundError(NebiusStorageError):
    """Object not found error (404)."""

    def __init__(self, message: str = "Object not found", status_code: Optional[int] = None) -> None:
        super().__init__(message, status_code)


class NebiusStorageConfigError(NebiusStorageError):
    """Configuration error (missing credentials, invalid endpoint, etc.)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass(frozen=True)
class _SigV4Components:
    """Components needed for SigV4 signing."""
    access_key_id: str
    secret_access_key: str
    region: str
    service: str = "s3"


def _sha256_hex(data: bytes) -> str:
    """Return SHA256 hex digest of data."""
    return hashlib.sha256(data).hexdigest()


def _hmac_sha256(key: bytes, data: str) -> bytes:
    """Return HMAC-SHA256 of data with key."""
    return hmac.new(key, data.encode("utf-8"), hashlib.sha256).digest()


def _derive_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    """Derive the AWS SigV4 signing key."""
    k_date = _hmac_sha256(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    k_signing = _hmac_sha256(k_service, "aws4_request")
    return k_signing


def _uri_encode_component(component: str) -> str:
    """URI encode a single path component per AWS SigV4 rules.

    AWS SigV4 requires encoding every byte except unreserved characters:
    A-Z, a-z, 0-9, '-', '.', '_', '~'
    Space must be encoded as %20 (not +).
    """
    # AWS SigV4 encoding: encode everything except unreserved chars
    # unreserved = ALPHA / DIGIT / "-" / "." / "_" / "~"
    safe_chars = "-_.~"
    return urllib.parse.quote(component, safe=safe_chars)


def _uri_encode_path(path: str) -> str:
    """URI encode a full path per AWS SigV4 rules.

    Encodes each path segment individually, preserving '/' separators.
    This ensures the canonical URI matches the actual request URI.
    """
    if not path:
        return ""
    # Split by '/', encode each segment, then rejoin
    segments = path.split("/")
    encoded_segments = [_uri_encode_component(seg) for seg in segments]
    return "/".join(encoded_segments)


def _canonical_request(
    method: str,
    path: str,
    query_params: dict[str, str],
    headers: dict[str, str],
    signed_headers: str,
    payload_hash: str,
) -> str:
    """Construct the canonical request per AWS SigV4 spec."""
    # Canonical URI: absolute path, URI-encoded per RFC 3986
    # Encode each path segment individually to preserve '/' separators
    canonical_uri = _uri_encode_path(path)

    # Canonical Query String: sorted by key, URI-encoded
    if query_params:
        sorted_params = sorted(query_params.items())
        canonical_query = "&".join(
            f"{_uri_encode_component(k)}={_uri_encode_component(v)}"
            for k, v in sorted_params
        )
    else:
        canonical_query = ""

    # Canonical Headers: sorted by lowercase header name, each trimmed
    canonical_headers_lines = []
    for header_name in sorted(signed_headers.split(";")):
        header_value = headers[header_name]
        # Trim whitespace and replace multiple spaces with single space
        header_value = " ".join(header_value.split())
        canonical_headers_lines.append(f"{header_name.lower()}:{header_value}")
    canonical_headers = "\n".join(canonical_headers_lines) + "\n"

    # Signed Headers: semicolon-separated list of lowercase header names
    # (already in signed_headers parameter)

    # Canonical Request
    canonical_request = "\n".join([
        method,
        canonical_uri,
        canonical_query,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])
    return canonical_request


def _string_to_sign(
    algorithm: str,
    amz_date: str,
    credential_scope: str,
    canonical_request: str,
) -> str:
    """Construct the string to sign per AWS SigV4 spec."""
    hashed_canonical = _sha256_hex(canonical_request.encode("utf-8"))
    return "\n".join([
        algorithm,
        amz_date,
        credential_scope,
        hashed_canonical,
    ])


def _build_authorization_header(
    components: _SigV4Components,
    amz_date: str,
    date_stamp: str,
    signed_headers: str,
    signature: str,
) -> str:
    """Build the Authorization header value."""
    credential_scope = f"{date_stamp}/{components.region}/{components.service}/aws4_request"
    return (
        f"AWS4-HMAC-SHA256 Credential={components.access_key_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )


class NebiusStorageClient:
    """Minimal S3-compatible client for Nebius Object Storage.

    Supports GET object operations with AWS Signature V4 authentication.
    Uses httpx for HTTP transport with support for testable transport injection.
    """

    def __init__(
        self,
        *,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region: str = "us-east-1",
        timeout: float = 60.0,
        transport: Optional[httpx.BaseTransport] = None,
        settings: Optional["Settings"] = None,
    ) -> None:
        """Initialize the Nebius Storage client.

        Args:
            access_key_id: AWS/Nebius access key ID. If not provided, reads from
                NEBIUS_S3_ACCESS_KEY_ID env var or settings.nebius_s3_access_key_id.
            secret_access_key: AWS/Nebius secret access key. If not provided, reads from
                NEBIUS_S3_SECRET_ACCESS_KEY env var or settings.nebius_s3_secret_access_key.
            endpoint_url: S3 endpoint URL (e.g., "https://storage.nebius.com").
                If not provided, reads from NEBIUS_S3_ENDPOINT_URL env var or
                settings.nebius_s3_endpoint_url. Defaults to Nebius default.
            region: AWS region for signing. Defaults to "us-east-1".
            timeout: Request timeout in seconds. Defaults to 60.0.
            transport: Optional httpx transport for testing (e.g., httpx.MockTransport).
            settings: Optional Axiom Settings instance for config fallback.

        Raises:
            NebiusStorageConfigError: If credentials or endpoint are not configured.
        """
        # Resolve credentials with fallback priority: explicit > env > settings
        self._access_key_id = (
            access_key_id
            or os.environ.get("NEBIUS_S3_ACCESS_KEY_ID")
            or (settings.nebius_s3_access_key_id if settings else None)
        )
        self._secret_access_key = (
            secret_access_key
            or os.environ.get("NEBIUS_S3_SECRET_ACCESS_KEY")
            or (settings.nebius_s3_secret_access_key if settings else None)
        )

        # Resolve endpoint URL
        self._endpoint_url = (
            endpoint_url
            or os.environ.get("NEBIUS_S3_ENDPOINT_URL")
            or (settings.nebius_s3_endpoint_url if settings else None)
            or "https://storage.nebius.com"
        ).rstrip("/")

        self._region = region
        self._timeout = timeout

        # Validate required configuration
        if not self._access_key_id or not self._secret_access_key:
            raise NebiusStorageConfigError(
                "Nebius S3 credentials not configured. "
                "Provide access_key_id and secret_access_key, or set "
                "NEBIUS_S3_ACCESS_KEY_ID and NEBIUS_S3_SECRET_ACCESS_KEY environment variables."
            )

        if not self._endpoint_url:
            raise NebiusStorageConfigError("Nebius S3 endpoint URL not configured.")

        # Create httpx client with optional custom transport
        self._client = httpx.Client(
            timeout=httpx.Timeout(self._timeout),
            transport=transport,
        )

        # SigV4 components
        self._sigv4 = _SigV4Components(
            access_key_id=self._access_key_id,
            secret_access_key=self._secret_access_key,
            region=self._region,
        )

        logger.debug(
            "NebiusStorageClient initialized: endpoint=%s, region=%s",
            self._endpoint_url,
            self._region,
        )

    def __repr__(self) -> str:
        """Return a safe representation without exposing secrets."""
        return (
            f"NebiusStorageClient("
            f"endpoint_url={self._endpoint_url!r}, "
            f"region={self._region!r}, "
            f"access_key_id={self._access_key_id[:4] if self._access_key_id else None}..., "
            f"timeout={self._timeout})"
        )

    def get_object(self, bucket: str, key: str) -> bytes:
        """Download an object from Nebius Object Storage.

        Args:
            bucket: Bucket name.
            key: Object key (path within bucket).

        Returns:
            Object content as bytes.

        Raises:
            NebiusStorageNotFoundError: If object does not exist (404).
            NebiusStorageAuthError: If authentication fails (401, 403).
            NebiusStorageError: For other HTTP errors or network issues.
        """
        if not bucket or not key:
            raise NebiusStorageConfigError("Bucket and key must be non-empty.")

        # Build request URL using path-style addressing for compatibility
        # Path-style: https://endpoint/bucket/key
        # Encode bucket and key components separately to preserve '/' separators
        encoded_bucket = _uri_encode_component(bucket)
        encoded_path = _uri_encode_path(f"/{bucket}/{key}")
        # Remove leading slash for URL construction
        url_path = encoded_path.lstrip("/")
        url = f"{self._endpoint_url}/{url_path}"

        # Prepare request components for signing
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")

        # Headers to sign
        headers_to_sign = {
            "host": urllib.parse.urlparse(self._endpoint_url).netloc,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
        }
        signed_headers = ";".join(sorted(headers_to_sign.keys()))

        # Empty payload for GET
        payload_hash = "UNSIGNED-PAYLOAD"

        # Build canonical request
        canonical_req = _canonical_request(
            method="GET",
            path=f"/{bucket}/{key}",
            query_params={},
            headers=headers_to_sign,
            signed_headers=signed_headers,
            payload_hash=payload_hash,
        )

        # Build string to sign
        credential_scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        string_to_sign = _string_to_sign(
            algorithm="AWS4-HMAC-SHA256",
            amz_date=amz_date,
            credential_scope=credential_scope,
            canonical_request=canonical_req,
        )

        # Derive signing key and calculate signature
        signing_key = _derive_signing_key(
            self._secret_access_key,
            date_stamp,
            self._region,
            "s3",
        )
        signature = hmac.new(
            signing_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        # Build Authorization header
        authorization = _build_authorization_header(
            self._sigv4,
            amz_date,
            date_stamp,
            signed_headers,
            signature,
        )

        # Final request headers
        request_headers = {
            **headers_to_sign,
            "Authorization": authorization,
        }

        # Log request (without sensitive data)
        logger.debug(
            "GET %s (bucket=%s, key=%s)",
            url,
            bucket,
            key,
        )

        try:
            response = self._client.get(url, headers=request_headers)
        except httpx.RequestError as e:
            logger.error("Request failed: %s", e)
            raise NebiusStorageError(f"Network error: {e}") from e

        # Handle response
        if response.status_code == 200:
            logger.debug("Successfully retrieved object: bucket=%s, key=%s", bucket, key)
            return response.content

        # Error handling - never include secrets in error messages
        if response.status_code == 404:
            raise NebiusStorageNotFoundError(
                f"Object not found: bucket={bucket}, key={key}",
                status_code=404,
            )
        if response.status_code in (401, 403):
            raise NebiusStorageAuthError(
                f"Authentication failed (status={response.status_code})",
                status_code=response.status_code,
            )

        # Other errors
        error_msg = f"Request failed with status {response.status_code}"
        try:
            error_body = response.text[:500]  # Limit error body size
            if error_body:
                error_msg += f": {error_body}"
        except Exception:
            pass

        raise NebiusStorageError(error_msg, status_code=response.status_code)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> "NebiusStorageClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()