import pytest
import httpx

# LiteLLM proxy is running on port 4000 based on docker-compose.yml
LITELLM_URL = "http://localhost:4000"

@pytest.mark.asyncio
async def test_litellm_connection():
    """Test that the LiteLLM database/container is up and accessible via its health endpoint."""
    
    # LiteLLM exposes a health check endpoint
    health_url = f"{LITELLM_URL}/health/readiness"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(health_url, timeout=5.0)
            
            # LiteLLM health endpoint should return 200 OK
            assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
            
    except httpx.RequestError as e:
        pytest.fail(f"Failed to connect to LiteLLM container at {LITELLM_URL}. Error details: {e}")

@pytest.mark.asyncio
async def test_litellm_models_endpoint():
    """Test that the LiteLLM container exposes the models endpoint."""
    
    models_url = f"{LITELLM_URL}/v1/models"
    
    try:
        async with httpx.AsyncClient() as client:
            # We check the /v1/models endpoint to see if the proxy is correctly routing/configured
            response = await client.get(models_url, timeout=5.0)
            
            # Depending on if a Master Key is set, this could be 200 or 401/403.
            # As long as the service is responding, the infra is up.
            assert response.status_code in [200, 401, 403], f"Unexpected status {response.status_code}. Response: {response.text}"
            
            if response.status_code == 200:
                data = response.json()
                assert "data" in data, "Expected 'data' array in /v1/models response"
                
    except httpx.RequestError as e:
        pytest.fail(f"Failed to connect to LiteLLM container at {LITELLM_URL}. Error details: {e}")
