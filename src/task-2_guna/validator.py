
import re

from models import Claim, EvidenceSource, EvidenceUsed, ValidationResult


def normalize(text: str) -> str:
    """Normalize text for case-insensitive comparisons."""
    return " ".join(text.lower().split())


def extract_numbers(text: str) -> list[str]:
    """Extract numbers, percentages, and decimal values."""
    return re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", text)


def has_inference_language(text: str) -> bool:
    """Identify common language that suggests an inference or prediction."""
    patterns = [
        r"\bwill\b",
        r"\bwould\b",
        r"\bcould\b",
        r"\bmay\b",
        r"\bmight\b",
        r"\bprobably\b",
        r"\blikely\b",
        r"\bsuggests?\b",
        r"\bindicates?\b",
        r"\bimplies?\b",
        r"\btherefore\b",
        r"\bcauses?\b",
        r"\bleads? to\b",
        r"\bresults? in\b",
        r"\bsignificantly\b",
    ]
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def direction(text: str) -> str | None:
    """Identify an increase or decrease described in a passage."""
    normalized = normalize(text)

    increase_patterns = [
        r"\bincreased?\b",
        r"\brose\b",
        r"\bgrew\b",
        r"\bwent up\b",
        r"\bhigher\b",
    ]
    decrease_patterns = [
        r"\bdecreased?\b",
        r"\bfell\b",
        r"\bdropped\b",
        r"\bwent down\b",
        r"\blower\b",
    ]

    has_increase = any(
        re.search(pattern, normalized) for pattern in increase_patterns
    )
    has_decrease = any(
        re.search(pattern, normalized) for pattern in decrease_patterns
    )

    if has_increase and not has_decrease:
        return "increase"
    if has_decrease and not has_increase:
        return "decrease"
    return None


def comparable_context(claim_text: str, excerpt: str) -> bool:
    """Check whether a claim and excerpt discuss overlapping terms."""
    stop_words = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on",
        "by", "for", "with", "is", "was", "were", "be", "been",
        "it", "this", "that", "during", "at", "from", "as",
    }

    claim_words = set(re.findall(r"\b[a-z0-9]+\b", normalize(claim_text)))
    excerpt_words = set(re.findall(r"\b[a-z0-9]+\b", normalize(excerpt)))

    claim_terms = claim_words - stop_words
    excerpt_terms = excerpt_words - stop_words

    if not claim_terms:
        return False

    return bool(claim_terms & excerpt_terms)


class ClaimValidator:
    """Validate claims against supplied evidence excerpts."""

    def __init__(self, sources: list[EvidenceSource]):
        self.sources: dict[str, EvidenceSource] = {}
        duplicate_ids: list[str] = []

        for source in sources:
            if source.source_id in self.sources:
                duplicate_ids.append(source.source_id)
            else:
                self.sources[source.source_id] = source

        if duplicate_ids:
            duplicates = ", ".join(sorted(set(duplicate_ids)))
            raise ValueError(
                f"Duplicate source IDs are not allowed: {duplicates}"
            )

    def validate(self, claim: Claim) -> ValidationResult:
        """Validate a claim while preserving evidence and contradictions."""
        evidence: list[EvidenceUsed] = []
        missing_source_ids: list[str] = []

        for source_id in claim.source_ids:
            source = self.sources.get(source_id)

            if source is None:
                missing_source_ids.append(source_id)
                continue

            evidence.append(
                EvidenceUsed(
                    source_id=source.source_id,
                    locator=source.locator,
                    excerpt=source.excerpt,
                )
            )

        contradictions: list[str] = []
        unresolved_questions: list[str] = []

        assessed_classification = (
            "inference"
            if has_inference_language(claim.text)
            else claim.classification
        )

        if missing_source_ids:
            unresolved_questions.append(
                "Could the missing source(s) be supplied? "
                + ", ".join(missing_source_ids)
            )

            return ValidationResult(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                status="unsupported",
                classification=claim.classification,
                assessed_classification=assessed_classification,
                source_ids=claim.source_ids,
                evidence=evidence,
                contradictions=[],
                unresolved_questions=unresolved_questions,
                reason=(
                    "One or more referenced sources could not be found: "
                    + ", ".join(missing_source_ids)
                    + ". The missing sources provide no verifiable evidence."
                ),
            )

        if not evidence:
            return ValidationResult(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                status="unsupported",
                classification=claim.classification,
                assessed_classification=assessed_classification,
                source_ids=claim.source_ids,
                evidence=[],
                contradictions=[],
                unresolved_questions=[
                    "No valid evidence excerpts were supplied."
                ],
                reason="The claim has no available evidence to validate.",
            )

        if (
            claim.classification == "fact"
            and assessed_classification == "inference"
        ):
            return ValidationResult(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                status="uncertain",
                classification=claim.classification,
                assessed_classification=assessed_classification,
                source_ids=claim.source_ids,
                evidence=evidence,
                contradictions=[],
                unresolved_questions=[
                    "What evidence establishes the inferred outcome or causal link?"
                ],
                reason=(
                    "The claim contains language commonly associated with "
                    "an inference or prediction, but it is labelled as a fact. "
                    "The supplied excerpts do not independently establish "
                    "the inferred conclusion."
                ),
            )

        # Compare the claim's direction against each relevant excerpt.
        claim_direction = direction(claim.text)

        if claim_direction is not None:
            for item in evidence:
                excerpt_direction = direction(item.excerpt)

                if (
                    excerpt_direction is not None
                    and excerpt_direction != claim_direction
                    and comparable_context(claim.text, item.excerpt)
                ):
                    contradictions.append(
                        f"{item.source_id} ({item.locator}) states "
                        f"'{item.excerpt}', which indicates "
                        f"{excerpt_direction} while the claim indicates "
                        f"{claim_direction}."
                    )

        # Also compare evidence excerpts against each other. This detects
        # conflicts when the claim uses neutral wording such as "changed".
        conflicting_source_indexes: set[int] = set()

        for i in range(len(evidence)):
            for j in range(i + 1, len(evidence)):
                first = evidence[i]
                second = evidence[j]

                first_direction = direction(first.excerpt)
                second_direction = direction(second.excerpt)

                if (
                    first_direction is not None
                    and second_direction is not None
                    and first_direction != second_direction
                    and comparable_context(first.excerpt, second.excerpt)
                ):
                    conflicting_source_indexes.update({i, j})

        # Preserve each conflicting excerpt in the result.
        for index in sorted(conflicting_source_indexes):
            item = evidence[index]
            item_direction = direction(item.excerpt)

            contradictions.append(
                f"{item.source_id} ({item.locator}) states "
                f"'{item.excerpt}', indicating {item_direction}; "
                "this conflicts with another supplied evidence excerpt."
            )

        if contradictions:
            # Remove duplicate messages while preserving their order.
            contradictions = list(dict.fromkeys(contradictions))

            return ValidationResult(
                claim_id=claim.claim_id,
                claim_text=claim.text,
                status="uncertain",
                classification=claim.classification,
                assessed_classification=assessed_classification,
                source_ids=claim.source_ids,
                evidence=evidence,
                contradictions=contradictions,
                unresolved_questions=[
                    "Which source is authoritative, and what time period "
                    "or measurement does each source describe?"
                ],
                reason=(
                    "The supplied evidence contains conflicting directional "
                    "statements about a comparable topic. Both sides of the "
                    "conflict are preserved, so the claim cannot be "
                    "confidently resolved."
                ),
            )

        # Check numerical claims against evidence relevant to the topic.
        claim_numbers = extract_numbers(claim.text)

        if claim_numbers:
            relevant_evidence = [
                item
                for item in evidence
                if comparable_context(claim.text, item.excerpt)
            ]

            evidence_numbers = [
                number
                for item in relevant_evidence
                for number in extract_numbers(item.excerpt)
            ]

            unsupported_numbers = [
                number
                for number in claim_numbers
                if number not in evidence_numbers
            ]

            if relevant_evidence and unsupported_numbers:
                unresolved_questions.append(
                    "Can a source be provided that directly verifies "
                    "the numerical value(s) in the claim?"
                )

                return ValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.text,
                    status="unsupported",
                    classification=claim.classification,
                    assessed_classification=assessed_classification,
                    source_ids=claim.source_ids,
                    evidence=evidence,
                    contradictions=[],
                    unresolved_questions=unresolved_questions,
                    reason=(
                        "The numerical value(s) "
                        f"{', '.join(unsupported_numbers)} in the claim "
                        "are not supported by the relevant supplied "
                        "excerpt(s)."
                    ),
                )

        # Direct textual match is a strong signal of support.
        normalized_claim = normalize(claim.text)

        for item in evidence:
            normalized_excerpt = normalize(item.excerpt)

            if normalized_claim in normalized_excerpt:
                return ValidationResult(
                    claim_id=claim.claim_id,
                    claim_text=claim.text,
                    status="supported",
                    classification=claim.classification,
                    assessed_classification=assessed_classification,
                    source_ids=claim.source_ids,
                    evidence=evidence,
                    contradictions=[],
                    unresolved_questions=[],
                    reason=(
                        "The claim text appears directly in the supplied "
                        f"excerpt from {item.source_id} ({item.locator})."
                    ),
                )

        unresolved_questions.append(
            "Does the supplied evidence establish the claim through "
            "a reliable paraphrase or additional context?"
        )

        return ValidationResult(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            status="uncertain",
            classification=claim.classification,
            assessed_classification=assessed_classification,
            source_ids=claim.source_ids,
            evidence=evidence,
            contradictions=[],
            unresolved_questions=unresolved_questions,
            reason=(
                "The claim was not found as a direct textual match, and "
                "the supplied evidence does not establish enough information "
                "to make a confident decision."
            ),
        )
