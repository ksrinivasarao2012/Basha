from abc import ABC , abstractmethod

class TranslateBackend(ABC):
    """
    Abstract Base Class representing a Translation engine interface
    """

    @abstractmethod
    def translate(self,text:str,target_lang:str) -> str:
        """
        Translates text from English to the target language.
        :param text: The source text in English.
        :param target_lang: The target language code (e.g., 'te', 'de').
        :return: Translated text.
        """
        pass
