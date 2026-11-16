"""Shared hardware-device and pinned Hugging Face artifact helpers."""

from pathlib import Path


def resolve_device(device: str = "auto") -> str:
    """Resolve 'auto', 'cpu', or 'cuda' into an available PyTorch device."""
    if device not in {"auto", "cpu", "cuda"}:
        raise ValueError("Device must be auto, cpu, or cuda")

    import torch

    cuda_available = torch.cuda.is_available()

    if device == "cuda" and not cuda_available:
        raise ValueError(
            "CUDA was requested but is unavailable; use device 'cpu' or 'auto'"
        )

    if device == "auto":
        return "cuda" if cuda_available else "cpu"

    return device


def verify_pinned_model_files(
    model_path: Path,
    revision: str,
    filenames: tuple[str, ...] | list[str],
    error_message: str,
) -> None:
    """Verify local Hugging Face weights and configs match the pinned commit revision."""
    for filename in filenames:
        metadata = model_path / ".cache/huggingface/download" / f"{filename}.metadata"

        if (
            not (model_path / filename).is_file()
            or not metadata.is_file()
            or metadata.read_text(encoding="utf-8").splitlines()[:1] != [revision]
        ):
            raise ValueError(error_message)
