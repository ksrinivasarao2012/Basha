import os
import hashlib
import shutil
from typing import Optional

class AudioCache:
    """
    Saves and retrieves synthesized audio bytes from a local folder.
    Keyed on a deterministic MD5 hash of text + language + voice.
    """
    def __init__(self,cache_dir = "./audio_cache"):
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir,exist_ok= True)
    
    def _get_key(self,text: str,lang: str,voice: Optional[str] = None, backend: Optional[str] = None) -> str:
        voice_str = voice or "default"
        backend_str = backend or "default"
        combined = f"{text.strip()}:{lang.lower()}:{voice_str.lower()}:{backend_str.lower()}"
        key = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return key 
    
    def get(self,text: str,lang: str,voice: Optional[str] = None, backend: Optional[str] = None) -> bytes:
        key = self._get_key(text,lang,voice,backend)
        path = os.path.join(self.cache_dir,key + ".mp3")

        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        else:
            return None 
    
    def set(self,text: str,lang: str,audio_bytes: bytes,voice: Optional[str] = None, backend: Optional[str] = None):
        """
        Save the audio bytes to the cache folder.
        """
        key = self._get_key(text,lang,voice,backend)
        path = os.path.join(self.cache_dir,key + '.mp3')
        with open(path,"wb") as f:
            f.write(audio_bytes)
    
    def clear(self) -> None:
        """
        Clear all cached files from the disk.
        """
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                file_path = os.path.join(self.cache_dir,filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")