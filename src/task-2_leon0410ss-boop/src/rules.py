import re

def extract_numbers(text: str) -> list[str]:
    pattern = r"\b\d+(?:\.\d+)?%?"
    return re.findall(pattern, text)

def numbers_supported(claim_text: str, evidence_text: str) -> bool:
    claim_numbers = extract_numbers(claim_text)
    evidence_numbers = extract_numbers(evidence_text)

    return all(number in evidence_numbers for number in claim_numbers)

def normalize_text(text: str) -> str:
    return " ".join(text.lower().strip().split())

def has_direct_text_support(claim_text: str, evidence_text: str) -> bool:
    return normalize_text(claim_text) == normalize_text(evidence_text)

INFERENCE_MARKERS = [
    "caused",
    "causes",
    "because of",
    "led to",
    "resulted in",
    "suggests that",
    "indicates that",
    "likely",
    "probably",
]


def contains_inference_marker(text: str) -> bool:
    normalized = normalize_text(text)

    return any(marker in normalized for marker in INFERENCE_MARKERS)

def numbers_conflict(text_a: str, text_b: str) -> bool:
    numbers_a = set(extract_numbers(text_a))
    numbers_b = set(extract_numbers(text_b))

    if not numbers_a or not numbers_b:
        return False

    return numbers_a != numbers_b
