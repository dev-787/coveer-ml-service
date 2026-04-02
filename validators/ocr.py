import io
import numpy as np
import requests
from PIL import Image

import easyocr

# Lazy-loaded reader — avoids loading at import/build time
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(["en", "hi"], gpu=False)
    return _reader

# Timeout (seconds) for downloading images from URLs
DOWNLOAD_TIMEOUT = 15


def extract_text(image: Image.Image) -> str:
    """
    Run OCR on a PIL image and return all detected text as a single string.

    Converts the image to a numpy array before passing to EasyOCR.
    Returns an empty string if OCR produces no results.
    """
    try:
        img_array = np.array(image.convert("RGB"))
        results = get_reader().readtext(img_array)
        # Each result is (bbox, text, confidence) — we only need the text
        return " ".join(text for (_, text, _) in results)
    except Exception:
        return ""


def extract_text_from_url(url: str) -> tuple:
    """
    Download an image from a URL, run OCR, and return both the image and text.

    Args:
        url: Public URL of the image to download.

    Returns:
        (PIL.Image.Image, str) — the downloaded image and its OCR text.

    Raises:
        ValueError: If the image cannot be downloaded or opened.
    """
    response = requests.get(url, timeout=DOWNLOAD_TIMEOUT)
    response.raise_for_status()

    image = Image.open(io.BytesIO(response.content))
    text = extract_text(image)
    return image, text
