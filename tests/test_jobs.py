import time
import os
import shutil
import pytest
from fastapi.testclient import TestClient
from basha.main import app
from basha.jobs.queue import job_manager

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup: Ensure cache is initialized
    yield
    # Teardown: Clear jobs db and files in the cache to avoid pollution
    job_manager._jobs.clear()
    cache_dir = "./audio_cache"
    if os.path.exists(cache_dir):
        for filename in os.listdir(cache_dir):
            if filename.startswith("job_"):
                try:
                    os.remove(os.path.join(cache_dir, filename))
                except OSError:
                    pass

def test_jobs_workflow():
    # 1. Submit a job
    payload = {
        "text": "This is a simple integration test for the background job queue system.",
        "target_language": "de"
    }
    
    response = client.post("/jobs", json=payload)
    assert response.status_code == 202
    
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ("pending", "processing", "completed")
    job_id = data["job_id"]
    
    # 2. Poll job status until completed
    max_retries = 30
    completed = False
    
    for _ in range(max_retries):
        status_resp = client.get(f"/jobs/{job_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        
        if status_data["status"] == "completed":
            completed = True
            assert status_data["completed_at"] is not None
            assert "download" in status_data["download_url"]
            break
        elif status_data["status"] == "failed":
            pytest.fail(f"Job failed with error: {status_data['error']}")
            
        time.sleep(0.2)
        
    assert completed, f"Job {job_id} did not complete within the timeout"
    
    # 3. Download the final audio file
    download_resp = client.get(f"/jobs/{job_id}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "audio/mpeg"
    assert len(download_resp.content) > 0
    
def test_job_not_found():
    response = client.get("/jobs/non-existent-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"

def test_job_download_not_completed():
    job_id = job_manager.create_job("Some text", "de")
    response = client.get(f"/jobs/{job_id}/download")
    assert response.status_code == 400
    assert "Job is not completed" in response.json()["detail"]
