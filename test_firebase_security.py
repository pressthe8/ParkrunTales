import requests
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Firebase Realtime Database URL
DATABASE_URL = "https://parkrun-story-default-rtdb.europe-west1.firebasedatabase.app"

def test_unauthorized_write():
    """
    Test attempting to write to Firebase without authentication.
    This should be rejected by the security rules.
    """
    # Test data
    test_data = {
        "content": "Test unauthorized write",
        "athlete_id": "TEST123",
        "url_hash": "test_hash",
        "created_at": {"sv": "timestamp"}
    }
    
    # Attempt to write directly to the stories node
    response = requests.post(
        f"{DATABASE_URL}/stories.json",
        json=test_data
    )
    
    logger.info(f"Response Status Code: {response.status_code}")
    logger.info(f"Response Content: {response.text}")
    
    # The request should be rejected (Permission denied)
    if response.status_code == 401 or "error" in response.json():
        logger.info("✅ Security test passed: Unauthorized write was correctly rejected")
    else:
        logger.error("❌ Security test failed: Unauthorized write was not rejected")

if __name__ == "__main__":
    test_unauthorized_write()
