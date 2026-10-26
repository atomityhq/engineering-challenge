import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import Claim, Source
from src.validator import validate_claim


FIXTURE_PATH = PROJECT_ROOT / "fixtures" / "validation_cases.json"


def main() -> None:
    with FIXTURE_PATH.open() as file:
        data = json.load(file)

    sources = [
        Source.model_validate(source)
        for source in data["sources"]
    ]

    claims = [
        Claim.model_validate(claim)
        for claim in data["claims"]
    ]

    results = [
        validate_claim(claim, sources)
        for claim in claims
    ]

    output = [
        result.model_dump(mode="json")
        for result in results
    ]

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()