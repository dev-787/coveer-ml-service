import traceback
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from validators.ocr import extract_text_from_url
from validators.ela import detect_tampering
from validators.document import validate_identity_document
from validators.platform import validate_platform_screenshot

# ── Confidence weight constants ──────────────────────────────────────────────

WEIGHT_TAMPERING  = 0.30
WEIGHT_ID_VALID   = 0.20
WEIGHT_NAME_MATCH = 0.15
WEIGHT_DOB_MATCH  = 0.15
WEIGHT_PLATFORM   = 0.20  # split across three platform sub-checks

# Thresholds for final decision
CONFIDENCE_VALID_THRESHOLD  = 0.80
CONFIDENCE_REVIEW_THRESHOLD = 0.60

# ── Pydantic models ──────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    firstName: str
    lastName: str
    dob: str          # ISO date string, e.g. "1990-05-15"
    platform: str     # e.g. "swiggy", "zomato"


class ValidationRequest(BaseModel):
    userId: str
    identityProofUrl: str
    platformProofUrl: str
    userProfile: UserProfile


class ValidationResponse(BaseModel):
    valid: bool
    reason: Optional[str]
    confidence: float


# ── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="Document Verification Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Route ────────────────────────────────────────────────────────────────────

@app.post("/validate", response_model=ValidationResponse)
async def validate(request: ValidationRequest):
    """
    Full document verification pipeline:
      1. Download both images and run OCR.
      2. Run ELA tampering detection on both images.
      3. Validate the identity document (Aadhaar / PAN).
      4. Validate the platform screenshot.
      5. Compute a weighted confidence score.
      6. Return { valid, reason, confidence }.
    """
    try:
        profile_dict = request.userProfile.model_dump()

        # ── Step 1: Download images + OCR ────────────────────────────────────
        try:
            identity_image, identity_text = extract_text_from_url(request.identityProofUrl)
        except Exception as exc:
            return ValidationResponse(
                valid=False,
                reason=f"Failed to download identity document: {exc}",
                confidence=0.0,
            )

        try:
            platform_image, platform_text = extract_text_from_url(request.platformProofUrl)
        except Exception as exc:
            return ValidationResponse(
                valid=False,
                reason=f"Failed to download platform screenshot: {exc}",
                confidence=0.0,
            )

        # ── Step 2: ELA tampering detection ──────────────────────────────────
        identity_ela = detect_tampering(identity_image)
        platform_ela = detect_tampering(platform_image)

        if identity_ela.get("tampered") or platform_ela.get("tampered"):
            return ValidationResponse(
                valid=False,
                reason="Document appears tampered",
                confidence=0.0,
            )

        # ── Step 3: Identity document validation ─────────────────────────────
        id_result = validate_identity_document(identity_text, profile_dict)

        # ── Step 4: Platform screenshot validation ────────────────────────────
        platform_result = validate_platform_screenshot(platform_text, profile_dict)

        # ── Step 5: Confidence score calculation ─────────────────────────────

        # Tampering passed (we only reach here if both images are clean)
        tampering_score = 1.0 * WEIGHT_TAMPERING

        # Identity checks
        id_score   = (1.0 if id_result["id_valid"] else 0.0) * WEIGHT_ID_VALID
        name_score = (id_result["name_match_score"] / 100.0) * WEIGHT_NAME_MATCH
        dob_score  = (1.0 if id_result["dob_match"] else 0.0) * WEIGHT_DOB_MATCH

        # Platform checks — split the platform weight equally across three signals
        platform_sub_weight = WEIGHT_PLATFORM / 3.0
        platform_score = (
            (1.0 if platform_result["platform_match"] else 0.0) * platform_sub_weight
            + (1.0 if platform_result["partner_keywords_found"] else 0.0) * platform_sub_weight
            + (1.0 if platform_result["active_status_found"] else 0.0) * platform_sub_weight
        )

        confidence = tampering_score + id_score + name_score + dob_score + platform_score
        # Clamp to [0, 1] to guard against floating-point drift
        confidence = max(0.0, min(1.0, confidence))

        # ── Step 6: Decision ─────────────────────────────────────────────────
        if confidence > CONFIDENCE_VALID_THRESHOLD:
            return ValidationResponse(valid=True, reason=None, confidence=confidence)

        if confidence >= CONFIDENCE_REVIEW_THRESHOLD:
            return ValidationResponse(valid=False, reason="manual_review", confidence=confidence)

        # Below review threshold — surface the first meaningful failure reason
        failure_reason = (
            id_result.get("reason")
            or platform_result.get("reason")
            or "Verification failed"
        )
        return ValidationResponse(valid=False, reason=failure_reason, confidence=confidence)

    except Exception:
        # Catch-all: log the traceback and return a 500-style response
        tb = traceback.format_exc()
        return ValidationResponse(
            valid=False,
            reason=f"Internal server error: {tb}",
            confidence=0.0,
        )
