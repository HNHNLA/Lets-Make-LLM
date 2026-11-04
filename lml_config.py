import torch

VERSION = "1.0.0-alpha"
DEFAULT_MAX_LENGTH = 512


def get_device():
    # 1. NVIDIA (CUDA)
    if torch.cuda.is_available():
        return "cuda"

    # 2. AMD (ROCm)
    # PyTorch ROCm builds expose GPU operations through the torch.cuda API.
    if hasattr(torch.version, "hip") and torch.version.hip is not None:
        return "cuda"

    # 3. Intel (XPU)
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        return "xpu"

    # 4. CPU fallback
    return "cpu"


DEVICE = get_device()
