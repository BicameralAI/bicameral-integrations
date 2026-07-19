from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/external-ingest-contract-release.yml"


def test_release_workflow_receives_bot_dispatch_and_checks_all_pins() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "external_ingest_contract_released" in workflow
    assert "github.event.client_payload.bot_sha" in workflow
    assert "github.event.client_payload.contract_sha256" in workflow
    assert "github.event.client_payload.request_schema_sha256" in workflow
    assert "runtime/schemas/ingest_schema_pin.json" in workflow
    assert "raw.githubusercontent.com/BicameralAI/bicameral-bot/${BOT_SHA}" in workflow
    assert "python scripts/validate_ingest_schema_pin.py" in workflow
