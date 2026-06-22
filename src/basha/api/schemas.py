from pydantic import BaseModel,Field
from typing import Optional, Dict

class SceneRequest(BaseModel):
    """
    Validation schema for a multi-voice audio-drama scene.
    """
    script: str = Field(
        ...,
        description="Dialogue script. One line per turn, formatted 'Speaker: text'.",
        min_length=1, max_length=20000,
        examples=["Ravi: Where are you going?\nMeena: To the market.\nRavi: Be careful!"],
    )
    target_language: str = Field(default="en", description="Target language code (e.g., 'hi', 'te').")
    translate: bool = Field(default=True, description="Translate each line into the target language before speaking.")
    voice_map: Optional[Dict[str, str]] = Field(
        default=None,
        description="Optional explicit mapping of character name -> Edge-TTS voice id. "
                    "Unmapped characters are auto-assigned distinct voices.",
    )


class SynthesizeRequest(BaseModel):
    """
    Validation schema for incoming synthesis requests.
    """
    text: str = Field(..., description="The English text you want to translate and read out loud", min_length=1, max_length=2000)
    target_language: str = Field(default ='hi',description="The target language code (e.g., 'te' for Telugu, 'de' for German)")
    voice: Optional[str] = Field(None, description="Optional voice identifier.")
    backend: Optional[str] = Field("auto", description="The TTS backend to use ('gtts', 'sarvam', 'auto')")


class SynthesizeResponse(BaseModel):
    """
    Metadata returned after a successful synthesis.
    (The actual audio bytes are returned as a binary stream, 
    but we define this in case we need structured responses later).
    """
    message: str
    language: str
    text_length: int


class JobSubmitRequest(BaseModel):
    """
    Validation schema for submitting background synthesis jobs.
    Allows much larger text input sizes.
    """
    text: str = Field(..., description="The text you want to translate and synthesize in the background", min_length=1, max_length=50000)
    target_language: str = Field(default='hi', description="The target language code (e.g., 'te', 'de')")
    voice: Optional[str] = Field(None, description="Optional voice identifier.")
    gender: Optional[str] = Field(None, description="Preferred voice gender: 'male' or 'female' (uses Edge-TTS).")
    backend: Optional[str] = Field("auto", description="The TTS backend to use ('gtts', 'sarvam', 'auto')")


class JobMetrics(BaseModel):
    """
    Quality and performance metrics for a completed job.
    CER/WER are optional: they are None when ASR could not transcribe the audio
    (e.g. unsupported language or a rate-limited request), so we never report a
    misleading 100% error for what is really a measurement failure.
    """
    cer: Optional[float] = Field(None, description="Character Error Rate (None if ASR unavailable)")
    wer: Optional[float] = Field(None, description="Word Error Rate (None if ASR unavailable)")
    rtf: float = Field(..., description="Real-Time Factor")
    transcription: str = Field(..., description="ASR transcription of the output audio")
    asr_available: bool = Field(True, description="Whether ASR produced a usable transcription")
    translated_text: Optional[str] = Field(None, description="Input text translated into the target language (shown in the UI).")


class JobStatusResponse(BaseModel):
    """
    Response detailing the current metadata/status of a background job.
    """
    job_id: str
    status: str = Field(..., description="Status: pending, processing, completed, failed")
    created_at: float
    completed_at: Optional[float] = None
    error: Optional[str] = None
    download_url: Optional[str] = None
    metrics: Optional[JobMetrics] = None


