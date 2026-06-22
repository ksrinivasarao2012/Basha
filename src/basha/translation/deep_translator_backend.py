from deep_translator import GoogleTranslator
from basha.translation.base import TranslateBackend

class DeepTranslatorBackend(TranslateBackend):
    """
    Free Google Translate implementation of the TranslationBackend interface.
    """
    def translate(self,text: str,target_lang: str) -> str:
        """
        Translates text using deep-translator's GoogleTranslator wrapper.
        """

        if target_lang.lower() == 'en':
            return text
        
        translated_text = GoogleTranslator(source = 'en',target = target_lang).translate(text)
        return translated_text

    