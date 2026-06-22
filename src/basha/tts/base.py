from abc import ABC,abstractmethod

class TTSBackend(ABC):
    """
    Abstract Base Class represtenting a Text-to-Speechengine interface.
    """

    @abstractmethod
    def synthesize(self,text:str,lang:str,voice: str = None) -> bytes:
        """
        Synthesize text in a given language and return the raw audio bytes (typically MP3 or WAV).
        
        :param text: The text to be spoken.
        :param lang: The language code (e.g., 'te', 'de').
        :param voice: Optional name of the voice speaker.
        :return: Audio data as bytes.
        """
        pass