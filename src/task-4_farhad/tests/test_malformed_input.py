"""Required check: invalid or incomplete input fails predictably and starts nothing."""
import json

import pytest
from pydantic import ValidationError

from workflow.cli import main
from workflow.models import ContentItem

VALID = {"content_id": "c-1", "title": "T", "body": "B"}


@pytest.mark.parametrize("bad", [
    {k: v for k, v in VALID.items() if k != "body"},        # missing field
    {**VALID, "title": ""},                                  # empty field
    {**VALID, "content_id": "   "},                          # whitespace only
    {**VALID, "approve": True},                              # unexpected extra field
    {**VALID, "body": 123},                                  # wrong type
    {},                                                      # empty object
])
def test_contract_rejects_bad_content(bad):
    with pytest.raises(ValidationError):
        ContentItem.model_validate(bad)


def test_valid_content_is_accepted():
    assert ContentItem.model_validate(VALID).content_id == "c-1"


@pytest.mark.parametrize("payload", [
    json.dumps({"content_id": "c-1", "title": "T"}),         # incomplete
    "this is not json",                                       # malformed JSON
])
def test_cli_rejects_bad_file_and_starts_nothing(tmp_path, capsys, payload):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(payload, encoding="utf-8")
    db = tmp_path / "never.db"

    code = main(["run", str(bad_file), "--db", str(db)])

    assert code == 2
    assert "Invalid input" in capsys.readouterr().err
    assert not db.exists(), "no database/checkpoint/event may be created for invalid input"


def test_cli_rejects_unknown_content_id(tmp_path, capsys):
    db = tmp_path / "never.db"
    assert main(["run", "no-such-content", "--db", str(db)]) == 2
    assert not db.exists()


def test_cli_rejects_unknown_scenario(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["run", "content-001", "--scenario", "nope", "--db", str(tmp_path / "x.db")])
    assert exc.value.code == 2
