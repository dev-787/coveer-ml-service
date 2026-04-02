import re
import datetime

from dateutil import parser as date_parser

from validators.name_match import match_names

# ── Keyword lists ────────────────────────────────────────────────────────────

AADHAAR_KEYWORDS = [
    "Government of India",
    "Unique Identification Authority",
    "UIDAI",
]

PAN_KEYWORDS = [
    "Income Tax Department",
    "Govt. of India",
    "Permanent Account Number",
]

# ── Verhoeff lookup tables ───────────────────────────────────────────────────

# Multiplication table
_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# Permutation table
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

# Inverse table
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff_checksum(number: str) -> bool:
    """Return True if the number passes the Verhoeff checksum."""
    c = 0
    digits = [int(d) for d in reversed(number)]
    for i, digit in enumerate(digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][digit]]
    return c == 0


# ── Document type detection ──────────────────────────────────────────────────

def detect_document_type(text: str) -> str:
    """Return 'aadhaar', 'pan', or 'unknown' based on keyword presence."""
    lower = text.lower()
    if any(kw.lower() in lower for kw in AADHAAR_KEYWORDS):
        return "aadhaar"
    if any(kw.lower() in lower for kw in PAN_KEYWORDS):
        return "pan"
    return "unknown"


# ── Aadhaar validation ───────────────────────────────────────────────────────

def validate_aadhaar(text: str) -> dict:
    """
    Extract a 12-digit Aadhaar number from OCR text and validate it using
    the Verhoeff checksum algorithm.

    Returns:
        { "valid": bool, "id_number": str | None, "reason": str | None }
    """
    try:
        match = re.search(r"\b\d{4}\s?\d{4}\s?\d{4}\b", text)
        if not match:
            return {"valid": False, "id_number": None, "reason": "Aadhaar number not found in document"}

        raw = match.group(0)
        digits_only = raw.replace(" ", "")

        if not _verhoeff_checksum(digits_only):
            return {"valid": False, "id_number": digits_only, "reason": "Aadhaar checksum validation failed"}

        return {"valid": True, "id_number": digits_only, "reason": None}

    except Exception as exc:
        return {"valid": False, "id_number": None, "reason": f"Aadhaar validation error: {exc}"}


# ── PAN validation ───────────────────────────────────────────────────────────

def validate_pan(text: str) -> dict:
    """
    Extract and validate a PAN number (format: AAAAA9999A) from OCR text.

    Returns:
        { "valid": bool, "id_number": str | None, "reason": str | None }
    """
    try:
        match = re.search(r"[A-Z]{5}[0-9]{4}[A-Z]", text)
        if not match:
            return {"valid": False, "id_number": None, "reason": "PAN number not found in document"}

        pan = match.group(0)
        return {"valid": True, "id_number": pan, "reason": None}

    except Exception as exc:
        return {"valid": False, "id_number": None, "reason": f"PAN validation error: {exc}"}


# ── Date of birth extraction ─────────────────────────────────────────────────

# Patterns to match common date formats in Indian documents
_DOB_PATTERNS = [
    r"\b\d{2}/\d{2}/\d{4}\b",   # dd/mm/yyyy
    r"\b\d{2}-\d{2}-\d{4}\b",   # dd-mm-yyyy
    r"\b\d{2}\.\d{2}\.\d{4}\b", # dd.mm.yyyy
    r"\b\d{4}-\d{2}-\d{2}\b",   # yyyy-mm-dd
]


def extract_dob(text: str) -> datetime.date | None:
    """
    Search OCR text for a date of birth using common Indian document date formats.

    Returns a datetime.date object or None if no date is found.
    """
    for pattern in _DOB_PATTERNS:
        match = re.search(pattern, text)
        if match:
            try:
                return date_parser.parse(match.group(0), dayfirst=True).date()
            except Exception:
                continue
    return None


# ── Name extraction ──────────────────────────────────────────────────────────

# Patterns that typically precede a name on Aadhaar cards
_AADHAAR_NAME_PREFIXES = re.compile(
    r"(?:name|नाम|to|dear|mr\.?|mrs\.?|ms\.?)[:\s]+([A-Za-z\s]{3,40})",
    re.IGNORECASE,
)

# On PAN cards the name usually appears on its own line after the PAN number
_PAN_NUMBER_RE = re.compile(r"[A-Z]{5}[0-9]{4}[A-Z]")


def extract_name(text: str, doc_type: str) -> str | None:
    """
    Best-effort name extraction from noisy OCR text.

    For Aadhaar: looks for lines following common name-preceding keywords.
    For PAN: looks for the line immediately after the PAN number line.

    Returns a name string or None.
    """
    try:
        if doc_type == "aadhaar":
            match = _AADHAAR_NAME_PREFIXES.search(text)
            if match:
                return match.group(1).strip()

            # Fallback: look for an all-caps or title-case line that looks like a name
            for line in text.splitlines():
                line = line.strip()
                if 3 <= len(line) <= 40 and re.match(r"^[A-Za-z\s]+$", line):
                    return line

        elif doc_type == "pan":
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            for i, line in enumerate(lines):
                if _PAN_NUMBER_RE.search(line) and i + 1 < len(lines):
                    candidate = lines[i + 1]
                    if re.match(r"^[A-Za-z\s]+$", candidate):
                        return candidate

            # Fallback: first alphabetic-only line of reasonable length
            for line in lines:
                if 3 <= len(line) <= 40 and re.match(r"^[A-Za-z\s]+$", line):
                    return line

    except Exception:
        pass

    return None


# ── Full identity document validation ───────────────────────────────────────

def validate_identity_document(text: str, user_profile: dict) -> dict:
    """
    Orchestrates all identity document checks:
      1. Detect document type (Aadhaar / PAN / unknown)
      2. Validate the ID number
      3. Compare date of birth
      4. Fuzzy-match the extracted name against the user profile

    Returns:
        {
            "doc_type": str,
            "id_valid": bool,
            "dob_match": bool,
            "name_match_score": float,  # 0–100
            "reason": str | None
        }
    """
    try:
        doc_type = detect_document_type(text)

        # Validate ID number based on detected type
        if doc_type == "aadhaar":
            id_result = validate_aadhaar(text)
        elif doc_type == "pan":
            id_result = validate_pan(text)
        else:
            id_result = {"valid": False, "id_number": None, "reason": "Unknown document type"}

        id_valid = id_result.get("valid", False)

        # Date of birth comparison
        dob_match = False
        extracted_dob = extract_dob(text)
        if extracted_dob and user_profile.get("dob"):
            try:
                profile_dob = date_parser.parse(user_profile["dob"], dayfirst=True).date()
                dob_match = extracted_dob == profile_dob
            except Exception:
                dob_match = False

        # Name fuzzy match
        extracted_name = extract_name(text, doc_type)
        name_score = match_names(
            extracted_name,
            user_profile.get("firstName", ""),
            user_profile.get("lastName", ""),
        )

        # Collect a human-readable failure reason
        reason = None
        if not id_valid:
            reason = id_result.get("reason", "ID validation failed")
        elif not dob_match:
            reason = "Date of birth does not match"
        elif name_score < 50:
            reason = "Name on document does not match profile"

        return {
            "doc_type": doc_type,
            "id_valid": id_valid,
            "dob_match": dob_match,
            "name_match_score": float(name_score),
            "reason": reason,
        }

    except Exception as exc:
        return {
            "doc_type": "unknown",
            "id_valid": False,
            "dob_match": False,
            "name_match_score": 0.0,
            "reason": f"Identity validation error: {exc}",
        }
