from src.models import (
    Claim,
    ClaimClassification,
    EvidenceExcerpt,
    EvidenceRecord,
    EvidenceReference,
    ReferenceResolution,
    Source,
    SupportStatus,
    ValidationResult,
)

from src.rules import (
    contains_inference_marker,
    has_direct_text_support,
    numbers_conflict,
    numbers_supported,
)

def find_source(source_id: str, sources: list[Source]) -> Source | None:
    for source in sources:
        if source.source_id == source_id:
            return source

    return None


def find_excerpt(locator: str, source: Source) -> EvidenceExcerpt | None:
    for excerpt in source.excerpts:
        if excerpt.locator == locator:
            return excerpt

    return None


def resolve_reference(
    reference: EvidenceReference,
    sources: list[Source],
) -> ReferenceResolution:
    source = find_source(reference.source_id, sources)

    if source is None:
        return ReferenceResolution(
            evidence=None,
            error=f"Missing source: {reference.source_id}",
        )

    excerpt = find_excerpt(reference.locator, source)

    if excerpt is None:
        return ReferenceResolution(
            evidence=None,
            error=(
                f"Missing locator: {reference.locator} "
                f"in source: {reference.source_id}"
            ),
        )

    evidence = EvidenceRecord(
        source_id=source.source_id,
        locator=excerpt.locator,
        excerpt=excerpt.text,
    )

    return ReferenceResolution(
        evidence=evidence,
        error=None,
    )


def evaluate_single_evidence(
    claim_text: str,
    evidence_text: str,
) -> tuple[SupportStatus, str]:
    if not numbers_supported(claim_text, evidence_text):
        return (
            SupportStatus.UNSUPPORTED,
            "The claim contains a numerical value that is not present in the evidence.",
        )

    if has_direct_text_support(claim_text, evidence_text):
        return (
            SupportStatus.SUPPORTED,
            "The evidence directly matches the claim.",
        )

    return (
        SupportStatus.UNCERTAIN,
        "The evidence does not directly match the claim, and this baseline does not infer semantic support.",
    )

def classify_claim(
    claim_text: str,
    evidence_text: str,
) -> ClaimClassification:
    if (
        contains_inference_marker(claim_text)
        and not has_direct_text_support(claim_text, evidence_text)
    ):
        return ClaimClassification.INFERENCE

    return ClaimClassification.FACT

def find_conflicts(evidence_records: list[EvidenceRecord]) -> list[str]:
    contradictions: list[str] = []

    for i in range(len(evidence_records)):
        for j in range(i + 1, len(evidence_records)):
            evidence_a = evidence_records[i]
            evidence_b = evidence_records[j]

            if numbers_conflict(evidence_a.excerpt, evidence_b.excerpt):
                contradictions.append(
                    (
                        f"Conflicting numerical evidence between "
                        f"{evidence_a.source_id} ({evidence_a.locator}) "
                        f"and {evidence_b.source_id} ({evidence_b.locator})."
                    )
                )

    return contradictions

def validate_claim(
    claim: Claim,
    sources: list[Source],
) -> ValidationResult:
    evidence_records: list[EvidenceRecord] = []
    unresolved_questions: list[str] = []

    # 1. Resolve every evidence reference.
    for reference in claim.evidence_refs:
        resolution = resolve_reference(reference, sources)

        if resolution.evidence is not None:
            evidence_records.append(resolution.evidence)

        if resolution.error is not None:
            unresolved_questions.append(resolution.error)

    # 2. Missing source or locator means we cannot fully validate the claim.
    if unresolved_questions:
        return ValidationResult(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            status=SupportStatus.UNCERTAIN,
            classification=ClaimClassification.FACT,
            supporting_source_ids=[],
            evidence=evidence_records,
            contradictions=[],
            unresolved_questions=unresolved_questions,
            reason="One or more evidence references could not be resolved.",
        )

    # 3. Check whether the resolved evidence conflicts.
    contradictions = find_conflicts(evidence_records)

    if contradictions:
        return ValidationResult(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            status=SupportStatus.UNCERTAIN,
            classification=ClaimClassification.FACT,
            supporting_source_ids=[],
            evidence=evidence_records,
            contradictions=contradictions,
            unresolved_questions=[],
            reason="The supplied evidence contains conflicting information.",
        )

    # 4. No usable evidence means the claim cannot be validated.
    if not evidence_records:
        return ValidationResult(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            status=SupportStatus.UNCERTAIN,
            classification=ClaimClassification.FACT,
            supporting_source_ids=[],
            evidence=[],
            contradictions=[],
            unresolved_questions=["No usable evidence was supplied."],
            reason="The claim cannot be validated without evidence.",
        )

    # 5. Classify the claim using the first resolved evidence record.
    classification = classify_claim(
        claim.text,
        evidence_records[0].excerpt,
    )

    # 6. Evaluate support against the first resolved evidence record.
    status, reason = evaluate_single_evidence(
        claim.text,
        evidence_records[0].excerpt,
    )

    # 7. Record supporting source IDs only when support is established.
    supporting_source_ids: list[str] = []

    if status == SupportStatus.SUPPORTED:
        supporting_source_ids = [
            evidence.source_id for evidence in evidence_records
        ]

    return ValidationResult(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        status=status,
        classification=classification,
        supporting_source_ids=supporting_source_ids,
        evidence=evidence_records,
        contradictions=[],
        unresolved_questions=[],
        reason=reason,
    )