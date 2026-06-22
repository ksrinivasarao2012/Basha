import time
import uuid
import threading
from typing import Any, Dict, Optional

class JobQueueManager:
    """
    In-memory, thread-safe manager for asynchronous translation and synthesis jobs.
    """
    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_job(self, text: str, target_lang: str, voice: Optional[str] = None) -> str:
        """
        Creates a new job record with state 'pending'.
        """
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "text": text,
                "target_language": target_lang,
                "voice": voice,
                "status": "pending",
                "created_at": time.time(),
                "completed_at": None,
                "error": None,
                "result_key": None,  # Points to the cache filename/key
                "metrics": None
            }
        return job_id

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the full metadata dictionary for a specific job.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def start_job(self, job_id: str) -> None:
        """
        Transitions job state to 'processing'.
        """
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "processing"

    def complete_job(self, job_id: str, result_key: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        """
        Transitions job state to 'completed' and sets the final result key and metrics.
        """
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "completed"
                self._jobs[job_id]["completed_at"] = time.time()
                self._jobs[job_id]["result_key"] = result_key
                self._jobs[job_id]["metrics"] = metrics

    def fail_job(self, job_id: str, error_message: str) -> None:
        """
        Transitions job state to 'failed' and logs the error message.
        """
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["completed_at"] = time.time()
                self._jobs[job_id]["error"] = error_message

# Shared global instance of the job manager
job_manager = JobQueueManager()
