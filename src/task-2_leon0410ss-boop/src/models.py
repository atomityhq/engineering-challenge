from enum import Enum

from pydantic import BaseModel

class EvidenceExcerpt(BaseModel):
    locator: str
    text: str

class EvidenceReference(BaseModel):
    source_id:str
    locator:str

class Source(BaseModel):
    source_id: str
    title: str
    excerpts: list[EvidenceExcerpt]

class Claim(BaseModel):
    claim_id:str
    text: str
    evidence_refs: list[EvidenceReference]

class SupportStatus(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNCERTAIN = "uncertain"

class ClaimClassification(str, Enum):
    FACT = "fact"
    INFERENCE = "inference"

class EvidenceRecord(BaseModel):
    source_id:str
    locator: str
    excerpt: str

class ReferenceResolution(BaseModel):
    evidence: EvidenceRecord | None
    error: str | None

class ValidationResult(BaseModel):
    claim_id: str
    claim_text: str
    status: SupportStatus
    classification: ClaimClassification
    supporting_source_ids: list[str]
    evidence: list[EvidenceRecord]
    contradictions: list[str]
    unresolved_questions: list[str]
    reason: str
