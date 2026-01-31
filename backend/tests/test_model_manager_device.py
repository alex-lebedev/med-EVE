"""Tests for model_manager device selection: MEDGEMMA_DEVICE, USE_MPS (Apple Silicon reliability)."""
from unittest.mock import patch

from core.model_manager import ModelManager


def test_detect_device_medgemma_device_cpu():
    """MEDGEMMA_DEVICE=cpu forces CPU regardless of CUDA/MPS."""
    with patch.dict("os.environ", {"MEDGEMMA_DEVICE": "cpu"}, clear=False):
        mm = ModelManager()
        assert mm.device == "cpu"


def test_detect_device_medgemma_device_mps():
    """MEDGEMMA_DEVICE=mps forces MPS when set."""
    with patch.dict("os.environ", {"MEDGEMMA_DEVICE": "mps"}, clear=False):
        mm = ModelManager()
        assert mm.device == "mps"


def test_detect_device_apple_silicon_defaults_to_cpu():
    """When MPS would be chosen, default to CPU unless USE_MPS=1."""
    with patch.dict("os.environ", {"USE_MPS": "", "MEDGEMMA_DEVICE": ""}, clear=False):
        with patch("core.model_manager.TORCH_AVAILABLE", True):
            with patch("torch.cuda.is_available", return_value=False):
                with patch("torch.backends.mps.is_available", return_value=True):
                    mm = ModelManager()
                    assert mm.device == "cpu"


def test_detect_device_use_mps_opt_in():
    """USE_MPS=1 allows MPS when available."""
    with patch.dict("os.environ", {"USE_MPS": "1", "MEDGEMMA_DEVICE": ""}, clear=False):
        with patch("core.model_manager.TORCH_AVAILABLE", True):
            with patch("torch.cuda.is_available", return_value=False):
                with patch("torch.backends.mps.is_available", return_value=True):
                    mm = ModelManager()
                    assert mm.device == "mps"
