
import json
from pathlib import Path

from pydantic import ValidationError

from models import Claim, EvidenceSource
from validator import ClaimValidator


def main() -> None:
    """Run the local Task 2 demonstration."""

    project_dir = Path(__file__).resolve().parent
    fixture_path = project_dir / "fixtures" / "claims.json"

    try:
        data = json.loads(
            fixture_path.read_text(encoding="utf-8")
        )

        sources = [
            EvidenceSource(**item)
            for item in data["sources"]
        ]

        validator = ClaimValidator(sources)

        for raw_claim in data["claims"]:
            print("=" * 70)

            try:
                claim = Claim(**raw_claim)
            except ValidationError as exc:
                print(f"Malformed claim: {raw_claim.get('claim_id', 'unknown')}")
                print(f"Validation error: {exc.errors()}")
                continue

            result = validator.validate(claim)

            print(f"Claim: {result.claim_text}")
            print(f"Status: {result.status}")
            print(f"Classification: {result.classification}")
            print(f"Reason: {result.reason}")

            print("Evidence:")
            for item in result.evidence:
                print(f"  Source: {item.source_id}")
                print(f"  Locator: {item.locator}")
                print(f"  Excerpt: {item.excerpt}")

            if result.contradictions:
                print("Contradictions:")
                for contradiction in result.contradictions:
                    print(f"  - {contradiction}")

            if result.unresolved_questions:
                print("Unresolved questions:")
                for question in result.unresolved_questions:
                    print(f"  - {question}")

    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"Unable to load the demonstration data: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
