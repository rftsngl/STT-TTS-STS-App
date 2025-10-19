"""
Test API key storage in database.
"""
import pytest
from fastapi.testclient import TestClient

from app.database import get_database, DatabaseError
from app.voice_utils import get_eleven_provider, clear_provider_cache


def test_database_api_key_storage():
    """Test that API keys can be stored and retrieved from database."""
    db = get_database()
    
    # Store a test API key
    test_key = "sk_test_key_12345678901234567890"
    key_id = db.add_api_key("elevenlabs", "test_key", test_key, True)
    
    assert key_id > 0
    
    # Retrieve the key
    retrieved_key = db.get_api_key("elevenlabs", "test_key")
    assert retrieved_key == test_key
    
    # Retrieve without specifying key name (should get most recent)
    retrieved_key_default = db.get_api_key("elevenlabs")
    assert retrieved_key_default == test_key
    
    # Clean up
    db.delete_api_key("elevenlabs", "test_key")


def test_database_api_key_encryption():
    """Test that API keys are encrypted in database."""
    import sqlite3
    from app.config import get_settings
    
    db = get_database()
    settings = get_settings()
    
    # Store a test API key
    test_key = "sk_test_encrypted_key_1234567890"
    db.add_api_key("elevenlabs", "encrypted_test", test_key, True)
    
    # Read directly from database to verify encryption
    conn = sqlite3.connect(settings.database_path)
    cursor = conn.execute(
        "SELECT encrypted_key FROM api_keys WHERE provider = ? AND key_name = ?",
        ("elevenlabs", "encrypted_test")
    )
    row = cursor.fetchone()
    conn.close()
    
    assert row is not None
    encrypted_value = row[0]
    
    # Encrypted value should NOT match the original key
    assert encrypted_value != test_key
    
    # But decrypted value should match
    retrieved_key = db.get_api_key("elevenlabs", "encrypted_test")
    assert retrieved_key == test_key
    
    # Clean up
    db.delete_api_key("elevenlabs", "encrypted_test")


def test_provider_cache():
    """Test that provider instances are cached."""
    clear_provider_cache()
    
    # Create provider with a test key
    test_key = "sk_test_cache_key_12345678901234567890"
    
    # Store in database
    db = get_database()
    db.add_api_key("elevenlabs", "cache_test", test_key, True)
    
    try:
        # Get provider twice
        provider1 = get_eleven_provider(require=False, api_key=test_key)
        provider2 = get_eleven_provider(require=False, api_key=test_key)
        
        # Should be the same instance (cached)
        assert provider1 is provider2
        
        # Clear cache
        clear_provider_cache()
        
        # Get provider again
        provider3 = get_eleven_provider(require=False, api_key=test_key)
        
        # Should be a different instance (cache was cleared)
        assert provider3 is not provider1
    finally:
        # Clean up
        db.delete_api_key("elevenlabs", "cache_test")
        clear_provider_cache()


def test_api_key_endpoint_saves_to_database(client: TestClient):
    """Test that the /ui/api/config/elevenlabs-key endpoint saves to database."""
    # This test requires a valid API key format
    test_key = "sk_test_endpoint_key_1234567890123456"
    
    response = client.post(
        "/ui/api/config/elevenlabs-key",
        json={"api_key": test_key}
    )
    
    # Should succeed
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "masked_key" in data
    
    # Verify it's in the database
    db = get_database()
    retrieved_key = db.get_api_key("elevenlabs")
    assert retrieved_key == test_key
    
    # Clean up
    db.delete_api_key("elevenlabs", "default")
    clear_provider_cache()


def test_api_key_endpoint_validation(client: TestClient):
    """Test API key validation in the endpoint."""
    # Test missing key
    response = client.post(
        "/ui/api/config/elevenlabs-key",
        json={"api_key": ""}
    )
    assert response.status_code == 400
    assert "MISSING_KEY" in response.text
    
    # Test invalid format (doesn't start with sk_)
    response = client.post(
        "/ui/api/config/elevenlabs-key",
        json={"api_key": "invalid_key_format"}
    )
    assert response.status_code == 400
    assert "INVALID_KEY" in response.text
    
    # Test too short
    response = client.post(
        "/ui/api/config/elevenlabs-key",
        json={"api_key": "sk_short"}
    )
    assert response.status_code == 400
    assert "INVALID_KEY" in response.text


def test_get_api_key_status_from_database(client: TestClient):
    """Test that the status endpoint checks database."""
    db = get_database()
    test_key = "sk_test_status_key_12345678901234567890"
    
    # Store key in database
    db.add_api_key("elevenlabs", "status_test", test_key, True)
    
    try:
        # Get status
        response = client.get("/ui/api/config/elevenlabs-key")
        assert response.status_code == 200
        
        data = response.json()
        assert data["configured"] is True
        assert data["has_valid_format"] is True
        assert "masked_key" in data
    finally:
        # Clean up
        db.delete_api_key("elevenlabs", "status_test")


@pytest.fixture
def client():
    """Create test client."""
    from app.main import app
    return TestClient(app)

