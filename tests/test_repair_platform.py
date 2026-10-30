from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import RepairSessionRecord  # noqa: F401
from app.core.grounding import DEFECT_TARGET_NOT_FOUND
from app.repair.agents import revision_for
from app.repair.orchestrator import RepairOrchestrator
from app.repair.schemas import FixProposal, InvestigationReport, VerificationReport
from app.repair.states import IllegalTransition, RepairState, transition


def test_legal_and_illegal_transitions():
    assert transition(RepairState.RECEIVED, RepairState.VALIDATING) == RepairState.VALIDATING
    with pytest.raises(IllegalTransition):
        transition(RepairState.RECEIVED, RepairState.APPROVED)
    with pytest.raises(IllegalTransition):
        transition(RepairState.AWAITING_APPROVAL, RepairState.TESTING)


class FakeInvestigator:
    def investigate(self, issue, top_k=5):
        return InvestigationReport(
            diagnosis="Calculator returns the wrong value.",
            root_cause="calculate() returns 1.",
            explanation="The function body returns a constant.",
            affected_files=["calculator.py"],
            confidence=0.9,
            facts=["calculator.py:2"],
        )


class FakeRepair:
    def propose(self, issue, investigation):
        patch = (
            "--- a/calculator.py\n"
            "+++ b/calculator.py\n"
            "@@ -1,2 +1,2 @@\n"
            " def calculate():\n"
            "-    return 1\n"
            "+    return 2\n"
        )
        return FixProposal(
            summary="Return 2",
            patch=patch,
            patch_revision=revision_for(patch),
            affected_files=["calculator.py"],
            reasoning="Expected result is 2.",
        )


class FakeQA:
    def __init__(self):
        self.verified = False

    def preflight(self, repository_path, proposal, **kwargs):
        return None

    def verify(self, repository_path, proposal, command, iteration, **kwargs):
        self.verified = True
        return (
            VerificationReport(passed=True, tests_run=1, tests_passed=1, iteration=iteration),
            Path(repository_path),
        )


def _db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True)()


def test_intake_stops_for_approval_and_does_not_test(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    qa = FakeQA()
    orch = RepairOrchestrator(FakeInvestigator(), FakeRepair(), qa)
    db = _db()
    session = orch.create_and_investigate(
        db,
        title="Wrong result",
        description="calculate returns 1",
        repository_path=str(repo),
    )
    assert session.state == RepairState.AWAITING_APPROVAL.value
    assert session.proposal is not None
    assert qa.verified is False
    assert session.approved_patch_revision is None


def test_stale_revision_cannot_approve(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    orch = RepairOrchestrator(FakeInvestigator(), FakeRepair(), FakeQA())
    db = _db()
    session = orch.create_and_investigate(
        db, title="Wrong result", description="calculate returns 1", repository_path=str(repo)
    )
    with pytest.raises(PermissionError):
        orch.decide(db, session.id, decision="approved", actor="manager", patch_revision="deadbeef")


def test_approval_runs_qa_then_ready(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    qa = FakeQA()
    orch = RepairOrchestrator(FakeInvestigator(), FakeRepair(), qa)
    db = _db()
    session = orch.create_and_investigate(
        db, title="Wrong result", description="calculate returns 1", repository_path=str(repo)
    )
    approved = orch.decide(
        db,
        session.id,
        decision="approved",
        actor="manager",
        patch_revision=session.current_patch_revision,
    )
    assert qa.verified is True
    assert approved.state == RepairState.READY_FOR_INTEGRATION.value
    completed = orch.integrate(db, approved.id, actor="manager")
    assert completed.state == RepairState.COMPLETED.value


def test_repair_api_create_and_reject_approval_mismatch(rag_client, tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    account = rag_client.post(
        "/api/v1/auth/register",
        json={"email": "repair-owner@example.com", "password": "password1"},
    )
    assert account.status_code == 200, account.text
    headers = {"Authorization": f"Bearer {account.json()['token']}"}
    created = rag_client.post(
        "/api/v1/repair/sessions",
        json={
            "title": "Wrong result",
            "description": "calculate returns 1 instead of 2",
            "repository_path": str(repo),
            "provider": "mock",
        },
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["state"] in {"AWAITING_APPROVAL", "BLOCKED"}
    if body["state"] == "AWAITING_APPROVAL":
        stale = rag_client.post(
            f"/api/v1/repair/sessions/{body['id']}/decision",
            json={"decision": "approved", "patch_revision": "not-the-revision"},
            headers=headers,
        )
        assert stale.status_code == 409


def test_request_revision_invalidates_approval(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    qa = FakeQA()
    orch = RepairOrchestrator(FakeInvestigator(), FakeRepair(), qa)
    db = _db()
    session = orch.create_and_investigate(
        db, title="Wrong result", description="calculate returns 1", repository_path=str(repo)
    )
    revised = orch.decide(
        db,
        session.id,
        decision="revision_requested",
        actor="manager",
        patch_revision=session.current_patch_revision,
        comment="Make it smaller.",
    )
    assert revised.state == RepairState.AWAITING_APPROVAL.value
    assert qa.verified is False
    assert revised.approved_patch_revision is None


def test_authorized_repo_list_includes_sample():
    from app.repair.repos import list_authorized_repositories

    items = list_authorized_repositories()
    assert any("sample_project" in item["path"] or item["name"] == "sample_project" for item in items)


def test_missing_defect_target_blocks_without_patch(tmp_path):
    class MissingTargetInvestigator:
        def investigate(self, issue, top_k=5):
            return InvestigationReport(
                diagnosis=DEFECT_TARGET_NOT_FOUND,
                root_cause=DEFECT_TARGET_NOT_FOUND,
                explanation="Provide a repository that contains the login implementation.",
                target_found=False,
                halt_reason=DEFECT_TARGET_NOT_FOUND,
                issue_nature="code",
            )

    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    qa = FakeQA()
    orch = RepairOrchestrator(MissingTargetInvestigator(), FakeRepair(), qa)
    db = _db()
    session = orch.create_and_investigate(
        db,
        title="Login accepts any password",
        description="login() does not check credentials",
        repository_path=str(repo),
    )
    assert session.state == RepairState.BLOCKED.value
    assert session.proposal is None
    assert session.message == DEFECT_TARGET_NOT_FOUND
    assert qa.verified is False


def test_reject_never_tests(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    qa = FakeQA()
    orch = RepairOrchestrator(FakeInvestigator(), FakeRepair(), qa)
    db = _db()
    session = orch.create_and_investigate(
        db, title="Wrong result", description="calculate returns 1", repository_path=str(repo)
    )
    rejected = orch.decide(
        db, session.id, decision="rejected", actor="manager", patch_revision=session.current_patch_revision
    )
    assert rejected.state == RepairState.REJECTED.value
    assert qa.verified is False
