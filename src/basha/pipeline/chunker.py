import re
from typing import List

def split_text_into_chunks(text: str, max_chars: int = 240) -> List[str]:
    """
    Splits text into chunks of maximum max_chars length, preferring split boundaries
    at clause markings (periods, question marks, commas, semicolons).
    """
    # Clean up whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []

    # Use regular expressions to split text after punctuation boundaries (., ?, !, ;, ,)
    # preserving the punctuation with the preceding sentence/clause.
    sentences = re.split(r'(?<=[.?!;,])\s+', text)

    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        if len(sentence) > max_chars:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_length = 0

            words = sentence.split(' ')
            temp_chunk = []
            temp_len = 0
            for word in words:
                if temp_len + len(word) + 1 > max_chars:
                    chunks.append(" ".join(temp_chunk))
                    temp_chunk = [word]
                    temp_len = len(word)
                else:
                    temp_chunk.append(word)
                    temp_len += len(word) + 1
            if temp_chunk:
                current_chunk = temp_chunk
                current_length = temp_len
        
        else:
            # Standard chunk accumulation
            # +1 accounts for the space between sentences/clauses
            if current_length + len(sentence) + (1 if current_chunk else 0) > max_chars:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_length = len(sentence)
            else:
                current_chunk.append(sentence)
                current_length += len(sentence) + (1 if len(current_chunk) > 1 else 0)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks
