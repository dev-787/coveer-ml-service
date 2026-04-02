import io
import numpy as np
from PIL import Image

# Pixels with mean error above this threshold are considered tampered
DEFAULT_THRESHOLD = 10.0
# JPEG quality used for re-compression during ELA
ELA_JPEG_QUALITY = 90


def detect_tampering(image: Image.Image, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """
    Error Level Analysis (ELA) for image tampering detection.

    Re-saves the image at a reduced JPEG quality, then computes the absolute
    pixel difference between the original and the re-compressed version.
    Regions that were previously saved at a lower quality will show lower
    error levels, which can indicate tampering.

    Args:
        image: PIL Image to analyse.
        threshold: Mean pixel error above which the image is flagged as tampered.

    Returns:
        { "tampered": bool, "mean_error": float }
    """
    try:
        # Convert to RGB so JPEG encoding always works (no alpha channel issues)
        original = image.convert("RGB")

        # Re-save at reduced quality into an in-memory buffer
        buffer = io.BytesIO()
        original.save(buffer, format="JPEG", quality=ELA_JPEG_QUALITY)
        buffer.seek(0)

        # Reopen the compressed version
        compressed = Image.open(buffer).convert("RGB")

        # Compute absolute pixel-level difference
        orig_array = np.array(original, dtype=np.float32)
        comp_array = np.array(compressed, dtype=np.float32)
        diff = np.abs(orig_array - comp_array)

        mean_error = float(diff.mean())
        tampered = mean_error > threshold

        return {"tampered": tampered, "mean_error": mean_error}

    except Exception as exc:
        # On any failure return a safe default (not tampered) so the pipeline continues
        return {"tampered": False, "mean_error": 0.0, "error": str(exc)}
