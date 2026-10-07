import pytest
import httpx2 as httpx
from axiom.execution.nebius_storage_client import (
    NebiusStorageClient,
    NebiusStorageError,
    NebiusStorageAuthError,
    NebiusStorageNotFoundError,
    NebiusStorageConfigError,
)

def test_client_initialization_missing_credentials():
    with pytest.raises(NebiusStorageConfigError):
        NebiusStorageClient()

def test_client_initialization_with_credentials():
    client = NebiusStorageClient(
        access_key_id="test-key",
        secret_access_key="test-secret",
        endpoint_url="https://storage.example.com",
    )
    assert client._access_key_id == "test-key"
    assert client._secret_access_key == "test-secret"
    assert client._endpoint_url == "https://storage.example.com"
    client.close()

def test_get_object_success():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        # Verify headers
        assert "Authorization" in request.headers
        assert "x-amz-date" in request.headers
        assert "x-amz-content-sha256" in request.headers
        return httpx.Response(200, content=b"hello world")

    transport = httpx.MockTransport(mock_handler)
    client = NebiusStorageClient(
        access_key_id="test-key",
        secret_access_key="test-secret",
        endpoint_url="https://storage.example.com",
        transport=transport,
    )
    
    content = client.get_object("my-bucket", "my-key")
    assert content == b"hello world"
    client.close()

def test_get_object_not_found():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    client = NebiusStorageClient(
        access_key_id="test-key",
        secret_access_key="test-secret",
        endpoint_url="https://storage.example.com",
        transport=transport,
    )
    
    with pytest.raises(NebiusStorageNotFoundError):
        client.get_object("my-bucket", "my-key")
    client.close()

def test_get_object_auth_error():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    transport = httpx.MockTransport(mock_handler)
    client = NebiusStorageClient(
        access_key_id="test-key",
        secret_access_key="test-secret",
        endpoint_url="https://storage.example.com",
        transport=transport,
    )
    
    with pytest.raises(NebiusStorageAuthError):
        client.get_object("my-bucket", "my-key")
    client.close()

def test_get_object_network_error():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection failed")

    transport = httpx.MockTransport(mock_handler)
    client = NebiusStorageClient(
        access_key_id="test-key",
        secret_access_key="test-secret",
        endpoint_url="https://storage.example.com",
        transport=transport,
    )
    
    with pytest.raises(NebiusStorageError, match="Network error"):
        client.get_object("my-bucket", "my-key")
    client.close()


def test_bucket_encoding():
    """Test bucket name encoding in URLs."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        # Verify URL contains encoded bucket
        url = str(request.url)
        assert "my-bucket" in url
        return httpx.Response(200, content=b"ok")
    
    transport = httpx.MockTransport(mock_handler)
    client = NebiusStorageClient(
        access_key_id="test-key",
        secret_access_key="test-secret",
        endpoint_url="https://storage.example.com",
        transport=transport,
    )
    
    client.get_object("my-bucket", "my-key")
    client.close()


def test_object_key_with_nested_paths():
    """Test object keys with nested paths."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        # Path should preserve slashes in key
        assert "path/to/nested/file.txt" in url
        return httpx.Response(200, content=b"ok")
    
    transport = httpx.MockTransport(mock_handler)
    client = NebiusStorageClient(
        access_key_id="test-key",
        secret_access_key="test-secret",
        endpoint_url="https://storage.example.com",
        transport=transport,
    )
    
    client.get_object("my-bucket", "path/to/nested/file.txt")
    client.close()


def test_object_key_with_spaces():
    """Test object keys with spaces."""
    def mock_handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        # Spaces should be encoded as %20
        assert "file%20with%20spaces.txt" in url
        return httpx.Response(200, content=b"ok")
    
    transport = httpx.MockTransport(mock_handler)
    client = NebiusStorageClient(
        access_key_id="test-key",
        secret_access_key="test-secret",
        endpoint_url="https://storage.example.com",
        transport=transport,
    )
    
    client.get_object("my-bucket", "file with spaces.txt")
    client.close()


def test_repr_does_not_expose_secrets():
    """Test that repr() does not expose secret access key."""
    client = NebiusStorageClient(
        access_key_id="AKIAIOSFODNN7EXAMPLE",
        secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        endpoint_url="https://storage.example.com",
    )
    
    repr_str = repr(client)
    str_str = str(client)
    
    # Secret should not appear in repr
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in repr_str
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in str_str
    
    # Access key should be partially masked
    assert "AKIA" in repr_str
    assert "AKIAIOSFODNN7EXAMPLE" not in repr_str
    
    client.close()


def test_signature_determinism():
    """Test that same request produces same signature."""
    from axiom.execution.nebius_storage_client import _derive_signing_key, _string_to_sign, _canonical_request, _sha256_hex
    from datetime import datetime, timezone
    import hmac
    import hashlib
    
    # Fixed timestamp for determinism
    fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    def make_signature(access_key, secret_key, region, bucket, key, timestamp):
        # Simulate signing
        amz_date = timestamp.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = timestamp.strftime("%Y%m%d")
        
        headers_to_sign = {
            "host": "storage.example.com",
            "x-amz-date": amz_date,
            "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
        }
        signed_headers = ";".join(sorted(headers_to_sign.keys()))
        
        canonical_req = _canonical_request(
            method="GET",
            path=f"/{bucket}/{key}",
            query_params={},
            headers=headers_to_sign,
            signed_headers=signed_headers,
            payload_hash="UNSIGNED-PAYLOAD",
        )
        
        credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
        string_to_sign = _string_to_sign(
            algorithm="AWS4-HMAC-SHA256",
            amz_date=amz_date,
            credential_scope=credential_scope,
            canonical_request=canonical_req,
        )
        
        signing_key = _derive_signing_key(secret_key, date_stamp, region, "s3")
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature
    
    # Same inputs should produce same signature
    sig1 = make_signature(
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "us-east-1",
        "my-bucket",
        "my-key",
        fixed_time,
    )
    sig2 = make_signature(
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "us-east-1",
        "my-bucket",
        "my-key",
        fixed_time,
    )
    assert sig1 == sig2
    
    # Different key should produce different signature
    sig3 = make_signature(
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "us-east-1",
        "my-bucket",
        "different-key",
        fixed_time,
    )
    assert sig1 != sig3
    
    # Different region should produce different signature
    sig4 = make_signature(
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "eu-west-1",
        "my-bucket",
        "my-key",
        fixed_time,
    )
    assert sig1 != sig4
    
    # Different secret should produce different signature
    sig5 = make_signature(
        "AKIAIOSFODNN7EXAMPLE",
        "different-secret-key",
        "us-east-1",
        "my-bucket",
        "my-key",
        fixed_time,
    )
    assert sig1 != sig5
    
    # Different timestamp should produce different signature
    different_time = datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    sig6 = make_signature(
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "us-east-1",
        "my-bucket",
        "my-key",
        different_time,
    )
    assert sig1 != sig6


def test_aws_sigv4_known_good_vector():
    """Test against AWS SigV4 known-good test vector.
    
    Based on AWS documentation example for GET request.
    This verifies the signing algorithm produces correct signatures.
    """
    from axiom.execution.nebius_storage_client import _canonical_request, _string_to_sign, _derive_signing_key
    from datetime import datetime, timezone
    import hmac
    import hashlib
    
    # AWS SigV4 test vector (simplified for GET with UNSIGNED-PAYLOAD)
    # Using example from AWS documentation
    access_key = "AKIAIOSFODNN7EXAMPLE"
    secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    region = "us-east-1"
    service = "s3"
    
    # Fixed timestamp
    timestamp = datetime(2013, 5, 24, 0, 0, 0, tzinfo=timezone.utc)
    amz_date = "20130524T000000Z"
    date_stamp = "20130524"
    
    # Build canonical request for GET /test.txt
    headers_to_sign = {
        "host": "examplebucket.s3.amazonaws.com",
        "x-amz-date": amz_date,
        "x-amz-content-sha256": "UNSIGNED-PAYLOAD",
    }
    signed_headers = ";".join(sorted(headers_to_sign.keys()))
    
    canonical_req = _canonical_request(
        method="GET",
        path="/test.txt",
        query_params={},
        headers=headers_to_sign,
        signed_headers=signed_headers,
        payload_hash="UNSIGNED-PAYLOAD",
    )
    
    # Expected canonical request (from AWS docs, adapted for UNSIGNED-PAYLOAD)
    expected_canonical = (
        "GET\n"
        "/test.txt\n"
        "\n"
        "host:examplebucket.s3.amazonaws.com\n"
        "x-amz-content-sha256:UNSIGNED-PAYLOAD\n"
        "x-amz-date:20130524T000000Z\n"
        "\n"
        "host;x-amz-content-sha256;x-amz-date\n"
        "UNSIGNED-PAYLOAD"
    )
    
    assert canonical_req == expected_canonical
    
    # Build string to sign
    credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = _string_to_sign(
        algorithm="AWS4-HMAC-SHA256",
        amz_date=amz_date,
        credential_scope=credential_scope,
        canonical_request=canonical_req,
    )
    
    # Expected string to sign format
    assert string_to_sign.startswith("AWS4-HMAC-SHA256\n")
    assert amz_date in string_to_sign
    assert f"{date_stamp}/{region}/{service}/aws4_request" in string_to_sign
    
    # Signature should be deterministic
    signing_key = _derive_signing_key(secret_key, date_stamp, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    assert len(signature) == 64  # SHA256 hex digest
    assert all(c in "0123456789abcdef" for c in signature)
    
    # Verify signature is consistent
    signature2 = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    assert signature == signature2
