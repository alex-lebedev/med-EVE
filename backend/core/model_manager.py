import torch
import os
from huggingface_hub import HfApi

MODEL_NAME = "google/medgemma-7b"  # placeholder, actual may be different
CACHE_DIR = os.getenv("HF_CACHE_DIR", "~/.cache/huggingface")

class ModelManager:
    def __init__(self):
        self.device = self.detect_device()
        self.model = None
        self.tokenizer = None
        self.lite_mode = True  # For demo, set to True
        self.model_loaded = False

    def detect_device(self):
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def load_model(self):
        # Check if cached
        api = HfApi()
        try:
            # Check if model exists in cache
            api.model_info(MODEL_NAME)
            # If yes, load
            # self.model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, cache_dir=CACHE_DIR)
            # self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, cache_dir=CACHE_DIR)
            # self.model_loaded = True
            # self.lite_mode = False
            pass  # For demo, don't load
        except Exception as e:
            self.lite_mode = True
            raise Exception(f"Model not available. Please run 'huggingface-cli login' and accept terms for {MODEL_NAME}. Error: {str(e)}")

    def get_health(self):
        return {
            "model_loaded": self.model_loaded,
            "device": self.device,
            "lite_mode": self.lite_mode
        }

model_manager = ModelManager()