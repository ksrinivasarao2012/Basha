import socket
import os
import time
import io
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import Response, FileResponse
from pydub import AudioSegment

from basha.api.schemas import SynthesizeRequest, JobSubmitRequest, JobStatusResponse, SceneRequest
from basha.pipeline.orchestrator import PipelineOrchestrator
from basha.jobs.queue import job_manager
from basha.core.logging import get_logger
from basha.eval.metrics import calculate_rtf, calculate_semantic_similarity
from basha.eval.asr_roundtrip import transcribe_audio_bytes, ASRRateLimited

# Create a router object to group our endpoints
router = APIRouter()

# Instantiate the orchestrator
orchestrator = PipelineOrchestrator()
logger = get_logger("basha.api")

def run_background_synthesis(job_id: str, text: str, target_lang: str, voice: Optional[str] = None, backend: str = "auto", gender: Optional[str] = None):
    """
    Background worker task running the translation & synthesis pipeline.
    """
    from basha.core.logging import REQUEST_ID_VAR
    REQUEST_ID_VAR.set(job_id)

    logger.info(f"Background task starting for job {job_id} using backend {backend}")
    job_manager.start_job(job_id)

    try:
        # Run orchestrator
        audio_bytes, pipeline_metrics = orchestrator.process(text, target_lang, backend=backend, voice=voice, gender=gender)
        if not audio_bytes:
            raise ValueError("Stitcher returned empty audio bytes.")

        # Save the stitched file to cache using job_id to prevent memory footprint issues
        cache_dir = orchestrator.cache.cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        file_path = os.path.join(cache_dir, f"job_{job_id}.mp3")
        
        with open(file_path, "wb") as f:
            f.write(audio_bytes)

        # Get audio duration
        audio_segment = AudioSegment.from_file(file_path)
        audio_duration = len(audio_segment) / 1000.0  # seconds

        # ASR Round-trip transcription
        logger.info(f"Running ASR round-trip evaluation for job {job_id}")
        asr_available = True
        asr_note = ""
        try:
            transcription = transcribe_audio_bytes(audio_bytes, lang=target_lang)
            if not transcription or not transcription.strip():
                # ASR ran but returned nothing intelligible — not a real 100% error.
                asr_available = False
                asr_note = "ASR returned no text (audio unintelligible to the free recognizer)."
                transcription = ""
        except ASRRateLimited as e:
            logger.warning(f"ASR rate-limited for job {job_id}: {e}")
            asr_available = False
            asr_note = "Free Google recognizer rate-limited this request. Wait a few minutes and retry."
            transcription = ""
        except Exception as e:
            logger.warning(f"ASR transcription failed during evaluation: {e}")
            asr_available = False
            asr_note = f"ASR error: {e}"
            transcription = ""

        # Translate once: shown in the UI as the "translated text".
        try:
            translated_text = orchestrator.translator.translate(text, target_lang)
        except Exception as e:
            logger.warning(f"Translation failed during evaluation: {e}")
            translated_text = text

        sem_sim = None
        if asr_available and transcription:
            sem_sim = calculate_semantic_similarity(translated_text, transcription)

        metrics_dict = {
            "rtf": round(pipeline_metrics.get("rtf", 0.0), 4),
            "transcription": transcription or f"[ASR unavailable] {asr_note}",
            "asr_available": asr_available,
            "semantic_similarity": sem_sim,
            "translated_text": translated_text,
            "translation_time": round(pipeline_metrics.get("translation_time", 0.0), 4),
            "synthesis_time": round(pipeline_metrics.get("synthesis_time", 0.0), 4),
            "cache_savings": round(pipeline_metrics.get("cache_savings", 0.0), 2),
            "cache_hits": pipeline_metrics.get("cache_hits", 0),
            "total_chunks": pipeline_metrics.get("total_chunks", 0),
        }

        job_manager.complete_job(job_id, f"job_{job_id}.mp3", metrics_dict)
        logger.info(f"Background task completed for job {job_id}. RTF={metrics_dict['rtf']:.4f}, SemanticSimilarity={sem_sim}")
    except Exception as e:
        logger.error(f"Background task failed for job {job_id}: {str(e)}", exc_info=True)
        job_manager.fail_job(job_id, str(e))

@router.post("/synthesize")
def synthesize(request: SynthesizeRequest):
    """
    Endpoint that accepts English text, translates it, 
    synthesizes it, and streams the finished MP3 audio back.
    """
    try:
        # Run the pipeline (chunk -> translate -> speak -> stitch)
        audio_bytes, pipeline_metrics = orchestrator.process(
            text = request.text,
            target_lang = request.target_language,
            backend = request.backend,
            voice = request.voice
        )

        if not audio_bytes:
            raise HTTPException(status_code=400,detail = "Failed to generate audio.")
        
        # Return the raw audio bytes as an audio/mpeg stream
        return Response(content = audio_bytes, media_type = "audio/mpeg")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scene")
def render_scene(request: SceneRequest):
    """
    Multi-voice audio drama: parse a 'Speaker: text' script, assign each
    character a distinct voice, synthesize every line, and return one stitched
    scene as audio/mpeg. The resolved cast is returned in the X-Cast header.
    """
    try:
        audio_bytes, cast, transcript, metrics = orchestrator.process_scene(
            script=request.script,
            target_lang=request.target_language,
            translate=request.translate,
            voice_map=request.voice_map,
        )
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Failed to render scene (empty script or audio).")

        import json, base64
        # The translated lines contain non-ASCII (Telugu/Hindi/…), which HTTP
        # headers can't carry raw — so base64-encode the UTF-8 JSON.
        script_b64 = base64.b64encode(
            json.dumps(transcript, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "X-Cast": json.dumps(cast),
                "X-Script": script_b64,
                "X-Metrics": json.dumps(metrics),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scene rendering failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs", response_model=JobStatusResponse, status_code=202)
def submit_job(request: JobSubmitRequest, background_tasks: BackgroundTasks, req: Request):
    """
    Submit a long-form text synthesis job to run in the background.
    Returns the job_id immediately.
    """
    job_id = job_manager.create_job(request.text, request.target_language, request.voice)
    
    # Queue the background synthesis task
    background_tasks.add_task(
        run_background_synthesis,
        job_id=job_id,
        text=request.text,
        target_lang=request.target_language,
        voice=request.voice,
        backend=request.backend,
        gender=request.gender
    )
    
    # Construct base download/status URLs
    base_url = str(req.base_url).rstrip("/")
    download_url = f"{base_url}/jobs/{job_id}/download"
    
    job = job_manager.get_job(job_id)
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        created_at=job["created_at"],
        download_url=download_url,
        metrics=job.get("metrics")
    )

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, req: Request):
    """
    Retrieve status and metadata of a background job.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    base_url = str(req.base_url).rstrip("/")
    download_url = f"{base_url}/jobs/{job_id}/download" if job["status"] == "completed" else None
    
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        created_at=job["created_at"],
        completed_at=job["completed_at"],
        error=job["error"],
        download_url=download_url,
        metrics=job.get("metrics")
    )

@router.get("/jobs/{job_id}/download")
def download_job_audio(job_id: str):
    """
    Download the final synthesized MP3 file for a completed job.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job is not completed. Current status: {job['status']}")
        
    file_path = os.path.join(orchestrator.cache.cache_dir, job["result_key"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=500, detail="Result file not found on disk")
        
    return FileResponse(file_path, media_type="audio/mpeg", filename=f"basha_narration_{job_id}.mp3")

@router.get("/cache/stats")
def cache_stats():
    """Report how many audio files are currently cached."""
    import os
    cache_dir = orchestrator.cache.cache_dir
    files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))] if os.path.exists(cache_dir) else []
    total_mb = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files) / (1024 * 1024)
    return {"cached_files": len(files), "total_mb": round(total_mb, 2), "cache_dir": cache_dir}


@router.delete("/cache")
def clear_cache():
    """Delete every cached audio file so the next request re-synthesizes fresh."""
    orchestrator.cache.clear()
    logger.info("Audio cache cleared via API")
    return {"status": "cleared", "message": "All cached audio removed."}


@router.get("/health")
def heath_check():
    """
    A robust health check that tests internet connectivity and cache directory access.
    """
    health_info = {
        "status": "healthy",
        "internet_connected": False,
        "cache_writable": False,
        "active_engine": "gTTS"
    }
    
    # 1. Test internet connection (ping a public DNS server with a 1-second timeout)
    try:
        socket.setdefaulttimeout(1.0)
        # Try to connect to Cloudflare DNS (1.1.1.1) on port 53 (DNS port)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
        health_info["internet_connected"] = True
    except OSError:
        health_info["status"] = "degraded"
        health_info["internet_connected"] = False
    # 2. Test cache folder access
    cache_dir = "./audio_cache"
    try:
        if os.path.exists(cache_dir):
            # Test writing a dummy file
            test_file = os.path.join(cache_dir, ".health_test")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            health_info["cache_writable"] = True
    except Exception:
        health_info["status"] = "degraded"
        health_info["cache_writable"] = False
    # If both failed, set status to unhealthy
    if not health_info["internet_connected"] and not health_info["cache_writable"]:
        health_info["status"] = "unhealthy"
    return health_info

