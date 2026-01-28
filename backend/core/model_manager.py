import os
import json
import re
import hashlib
import threading
from typing import Optional, Dict, Any

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from huggingface_hub import HfApi
    TRANSFORMERS_AVAILABLE = True
    HF_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    HF_AVAILABLE = False

# Support both 4B and 27B models via environment variable
DEFAULT_MODEL = os.getenv("MEDGEMMA_MODEL", "google/medgemma-4b-it")
CACHE_DIR = os.path.expanduser(os.getenv("HF_CACHE_DIR", "~/.cache/huggingface"))
MODE = os.getenv("MODE", "lite").lower()

# Check for local model directory (relative to backend/core/)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
LOCAL_MODEL_BASE = os.path.join(_REPO_ROOT, "models")

def _get_local_model_path(model_name: str) -> Optional[str]:
    """Check if local model exists and return path"""
    # Extract model name from "google/medgemma-4b-it" -> "medgemma-4b-it"
    model_dir_name = model_name.split("/")[-1] if "/" in model_name else model_name
    local_path = os.path.join(LOCAL_MODEL_BASE, model_dir_name)

    # Check if directory exists and has model files
    if os.path.exists(local_path):
        # Check for common model files
        config_file = os.path.join(local_path, "config.json")
        if os.path.exists(config_file):
            return local_path
    return None

class ModelManager:
    def __init__(self):
        self.device = self.detect_device()
        self.model = None
        self.tokenizer = None
        self.model_name = DEFAULT_MODEL
        self.lite_mode = (MODE != "model")
        self.model_loaded = False
        self.model_loading = False
        self.model_loaded_event = threading.Event()
        # If lite mode, event is already "set" (no wait). If model mode, clear until load completes.
        if self.lite_mode:
            self.model_loaded_event.set()
        else:
            self.model_loaded_event.clear()
        self.response_cache = {}  # Simple in-memory cache for prompt responses

    def detect_device(self):
        if not TORCH_AVAILABLE:
            return "cpu"
        try:
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        return "cpu"

    def wait_for_model(self, timeout: Optional[float] = None) -> None:
        """
        Block until model is loaded (or loading has finished). When MODE=model,
        call this before running the pipeline so hypotheses are generated with the model.
        Returns immediately if model is already loaded or in lite mode.
        Raises TimeoutError if timeout (seconds) is given and exceeded.
        """
        if self.lite_mode:
            return
        if self.model_loaded:
            return
        ok = self.model_loaded_event.wait(timeout=timeout)
        if not ok:
            raise TimeoutError(
                "Model did not finish loading within the timeout. "
                "Check server logs for load errors."
            )

    def load_model(self):
        """Load MedGemma model - checks local directory first, then HuggingFace"""
        if not TRANSFORMERS_AVAILABLE:
            raise Exception("transformers not available. Install with: pip install transformers")
        if not HF_AVAILABLE:
            raise Exception("huggingface_hub not available. Install with: pip install huggingface_hub")

        if self.model_loaded:
            return

        self.model_loading = True
        self.model_loaded_event.clear()
        try:
            # Check for local model first
            local_model_path = _get_local_model_path(self.model_name)
            model_source = local_model_path if local_model_path else self.model_name

            if local_model_path:
                print(f"📦 Loading model from local directory: {local_model_path}")
            else:
                print(f"🌐 Loading model from HuggingFace: {self.model_name}")
                # Verify model is accessible on HuggingFace
                api = HfApi()
                api.model_info(self.model_name)

            try:
                # Load tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(
                    model_source,
                    cache_dir=CACHE_DIR if not local_model_path else None,
                    trust_remote_code=True
                )

                # Load model with appropriate device and quantization
                load_kwargs = {
                    "trust_remote_code": True
                }

                if not local_model_path:
                    load_kwargs["cache_dir"] = CACHE_DIR

                if self.device == "cuda":
                    # Try 8-bit quantization for CUDA to save memory
                    try:
                        from transformers import BitsAndBytesConfig
                        quantization_config = BitsAndBytesConfig(
                            load_in_8bit=True,
                            llm_int8_threshold=6.0
                        )
                        load_kwargs["quantization_config"] = quantization_config
                        load_kwargs["device_map"] = "auto"
                        self.model = AutoModelForCausalLM.from_pretrained(
                            model_source,
                            **load_kwargs
                        )
                    except Exception:
                        # Fallback to full precision if quantization fails
                        load_kwargs.pop("quantization_config", None)
                        load_kwargs["device_map"] = "auto"
                        self.model = AutoModelForCausalLM.from_pretrained(
                            model_source,
                            **load_kwargs
                        )
                elif self.device == "mps":
                    # MPS (Apple Silicon) - no quantization support yet
                    # Load without device_map for MPS to avoid memory issues
                    load_kwargs.pop("device_map", None)
                    # Use low_cpu_mem_usage to reduce memory pressure
                    load_kwargs["low_cpu_mem_usage"] = True
                    # Load model first, then move to device
                    self.model = AutoModelForCausalLM.from_pretrained(
                        model_source,
                        **load_kwargs
                    )
                    # Move to MPS device manually
                    self.model = self.model.to(self.device)
                else:
                    # CPU - use full precision
                    self.model = AutoModelForCausalLM.from_pretrained(
                        model_source,
                        **load_kwargs
                    )

                # Set pad token if not set
                if self.tokenizer.pad_token is None:
                    self.tokenizer.pad_token = self.tokenizer.eos_token

                self.model_loaded = True
                self.lite_mode = False
                print(f"✅ Model loaded successfully!")
            except Exception as e:
                self.lite_mode = True
                self.model_loaded = False
                error_msg = str(e)
                # Don't raise exception during pre-load - just log and continue in lite mode
                if local_model_path:
                    print(f"⚠️  Model pre-load failed (will load on first use): Failed to load local model from {local_model_path}. Error: {error_msg}")
                else:
                    print(f"⚠️  Model pre-load failed (will load on first use): Failed to load model {self.model_name}. Error: {error_msg}")
        finally:
            self.model_loading = False
            self.model_loaded_event.set()

    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from model output, handling markdown code blocks and text-wrapped JSON"""
        # Try to find JSON in markdown code blocks first
        json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_block_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find JSON object directly
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue

        # Try parsing the entire text as JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        return None

    def _cache_key(self, system_prompt: str, user_prompt: str) -> str:
        """Generate cache key for prompt"""
        combined = f"{system_prompt}\n\n{user_prompt}"
        return hashlib.md5(combined.encode()).hexdigest()

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        top_p: float = 0.9,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Generate response from model with JSON extraction and caching

        Returns:
            dict with keys: 'text', 'json', 'raw_output', 'cached'
        """
        if not self.model_loaded:
            raise Exception("Model not loaded. Call load_model() first.")

        # Check cache
        cache_key = self._cache_key(system_prompt, user_prompt) if use_cache else None
        if cache_key and cache_key in self.response_cache:
            cached_result = self.response_cache[cache_key]
            return {
                'text': cached_result['text'],
                'json': cached_result['json'],
                'raw_output': cached_result['raw_output'],
                'cached': True
            }

        # Format prompt
        if self.tokenizer.chat_template:
            # Use chat template if available
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            # Fallback to simple formatting
            prompt = f"{system_prompt}\n\n{user_prompt}\n\nResponse:"

        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt", padding=True, truncation=True, max_length=2048)

        # Move to device
        if self.device != "cpu" and not hasattr(self.model, "device"):
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=(temperature > 0),
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id
            )

        # Decode
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Extract the new tokens (response only)
        input_length = inputs['input_ids'].shape[1]
        response_text = self.tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)

        # Extract JSON
        extracted_json = self._extract_json_from_text(response_text)

        result = {
            'text': response_text,
            'json': extracted_json,
            'raw_output': generated_text,
            'cached': False
        }

        # Cache result
        if cache_key and use_cache:
            self.response_cache[cache_key] = result

        return result

    def get_health(self):
        return {
            "model_loaded": self.model_loaded,
            "model_loading": self.model_loading,
            "device": self.device,
            "lite_mode": self.lite_mode,
            "model_name": self.model_name,
            "cache_size": len(self.response_cache)
        }

model_manager = ModelManager()
