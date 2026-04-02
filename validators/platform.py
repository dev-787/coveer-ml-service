import re
from validators.name_match import match_names

# ── Keyword dictionaries ─────────────────────────────────────────────────────

PLATFORM_KEYWORDS = {
    "swiggy":   ["swiggy", "swiggy delivery", "delivery partner"],
    "zomato":   ["zomato", "zomato delivery", "delivery partner"],
    "blinkit":  ["blinkit", "delivery partner"],
    "zepto":    ["zepto", "delivery partner"],
    "amazon":   ["amazon", "amazon flex", "delivery associate"],
    "flipkart": ["flipkart", "ekart", "delivery partner"],
}

ACTIVE_STATUS_KEYWORDS = ["online", "active", "delivering", "on duty", "available"]
PARTNER_KEYWORDS = ["delivery partner", "partner", "associate"]

# Minimum fuzzy score to consider a name match successful
NAME_MATCH_THRESHOLD = 50


def validate_platform_screenshot(text: str, user_profile: dict) -> dict:
    """
    Validate a delivery-platform screenshot using OCR text.

    Checks:
      1. Platform name matches the user's declared platform.
      2. Partner-related keywords are present.
      3. Active/online status keywords are present.
      4. The user's name appears somewhere in the screenshot.

    Returns:
        {
            "platform_match": bool,
            "partner_keywords_found": bool,
            "active_status_found": bool,
            "name_match_score": float,
            "reason": str | None
        }
    """
    try:
        lower_text = text.lower()

        # ── Platform detection ────────────────────────────────────────────────
        expected_platform = user_profile.get("platform", "").lower().strip()
        platform_match = False

        if expected_platform and expected_platform in PLATFORM_KEYWORDS:
            keywords = PLATFORM_KEYWORDS[expected_platform]
            platform_match = any(kw in lower_text for kw in keywords)
        elif expected_platform:
            # Fallback: just check if the platform name itself appears in the text
            platform_match = expected_platform in lower_text

        # ── Partner keyword check ─────────────────────────────────────────────
        partner_keywords_found = any(kw in lower_text for kw in PARTNER_KEYWORDS)

        # ── Active status check ───────────────────────────────────────────────
        active_status_found = any(kw in lower_text for kw in ACTIVE_STATUS_KEYWORDS)

        # ── Name match ────────────────────────────────────────────────────────
        # Extract candidate name tokens: sequences of capitalised words
        name_candidates = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", text)
        best_score = 0.0
        first = user_profile.get("firstName", "")
        last = user_profile.get("lastName", "")

        for candidate in name_candidates:
            score = match_names(candidate, first, last)
            if score > best_score:
                best_score = score

        # ── Build failure reason ──────────────────────────────────────────────
        reason = None
        if not platform_match:
            reason = f"Platform '{expected_platform}' not detected in screenshot"
        elif not partner_keywords_found:
            reason = "No delivery partner keywords found in screenshot"
        elif not active_status_found:
            reason = "No active/online status found in screenshot"
        elif best_score < NAME_MATCH_THRESHOLD:
            reason = "Name not found in platform screenshot"

        return {
            "platform_match": platform_match,
            "partner_keywords_found": partner_keywords_found,
            "active_status_found": active_status_found,
            "name_match_score": float(best_score),
            "reason": reason,
        }

    except Exception as exc:
        return {
            "platform_match": False,
            "partner_keywords_found": False,
            "active_status_found": False,
            "name_match_score": 0.0,
            "reason": f"Platform validation error: {exc}",
        }
