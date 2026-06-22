import os
import json
from datasets import load_dataset
import huggingface_hub
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()

# Map our 2-letter codes to FLORES+ 3-letter + Script codes
LANG_MAP = {
    "en": "eng_Latn",
    "te": "tel_Telu",
    "ta": "tam_Taml",
    "kn": "kan_Knda",
    "ml": "mal_Mlym",
    "mr": "mar_Deva",
    "hi": "hin_Deva",
    "de": "deu_Latn",
    "fr": "fra_Latn",
    "es": "spa_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn"
}

def main():
    # Programmatic login using HF_TOKEN if available in .env
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        print("Logging in to Hugging Face Hub using token from .env...")
        huggingface_hub.login(token=hf_token)
    else:
        print("Warning: HF_TOKEN not found in .env. Attempting download using existing hub credentials...")

    evaluation_set = []
    
    # We will fetch all 1012 parallel sentences from devtest
    num_sentences = 1012
    
    # Download and extract each language
    loaded_data = {}
    print("Downloading FLORES+ datasets for the 12 selected languages...")
    for proj_code, flores_code in LANG_MAP.items():
        try:
            print(f"Loading {flores_code}...")
            # Download only the devtest split for this specific language configuration
            ds = load_dataset("openlanguagedata/flores_plus", flores_code, split="devtest")
            loaded_data[proj_code] = ds["text"][:num_sentences]
        except Exception as e:
            print(f"Error loading {flores_code}: {e}")
            
    # Determine the actual number of parallel sentences available (dev split is capped at 997)
    if loaded_data:
        actual_num_sentences = min(num_sentences, min(len(sentences) for sentences in loaded_data.values()))
    else:
        actual_num_sentences = 0
            
    # Restructure parallel sentences: 
    # [{ "id": 0, "en": "...", "te": "...", "de": "..." }, ...]
    for idx in range(actual_num_sentences):
        sentence_entry = {"id": idx}
        for proj_code in LANG_MAP.keys():
            if proj_code in loaded_data:
                sentence_entry[proj_code] = loaded_data[proj_code][idx]
        evaluation_set.append(sentence_entry)
        
    # Save to a local file
    out_path = "samples/input/flores_evaluation_set.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(evaluation_set, f, ensure_ascii=False, indent=2)
        
    print(f"\nSuccess! Created evaluation set with {actual_num_sentences} parallel sentences.")
    print(f"Saved to: {out_path}")

if __name__ == "__main__":
    main()
