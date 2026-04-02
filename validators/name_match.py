from rapidfuzz import fuzz


def normalize(name: str) -> str:
    """Uppercase and strip extra whitespace from a name string."""
    return " ".join(name.upper().split())


def match_names(extracted: str, first: str, last: str) -> float:
    """
    Fuzzy match an extracted name against the user's full name.

    Uses token_sort_ratio so word order differences don't penalize the score.
    Returns 0 if extracted is None or empty.
    """
    if not extracted:
        return 0.0

    full_name = f"{first} {last}"
    extracted_norm = normalize(extracted)
    full_name_norm = normalize(full_name)

    return fuzz.token_sort_ratio(extracted_norm, full_name_norm)
