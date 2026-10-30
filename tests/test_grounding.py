from pathlib import Path

import pytest

from app.core.grounding import (
    DEFECT_TARGET_NOT_FOUND,
    QA_FILE_TYPE_REJECT,
    DefectTargetNotFound,
    PatchTypeMismatch,
    assert_patch_matches_nature,
    classify_issue_nature,
    locate_defect_targets,
)
from app.repair.agents import QAEngineer, revision_for
from app.repair.schemas import FixProposal


def test_locate_finds_existing_function(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "README.md").write_text("# Calculator\n", encoding="utf-8")
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    result = locate_defect_targets(
        repo,
        title="Wrong result",
        description="calculate returns 1 instead of 2",
    )
    assert result.found is True
    assert any(path.endswith("calculator.py") for path in result.files)


def test_locate_missing_login_ignores_readme(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "README.md").write_text(
        "# Sample\nThere is no login function in this project.\n",
        encoding="utf-8",
    )
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    result = locate_defect_targets(
        repo,
        title="Login accepts any password",
        description="The login function does not validate credentials.",
    )
    assert result.found is False
    assert result.reason == DEFECT_TARGET_NOT_FOUND
    assert result.files == []


def test_code_bug_cannot_patch_markdown():
    patch = (
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1,1 +1,2 @@\n"
        " # Sample\n"
        "+login is broken\n"
    )
    with pytest.raises(PatchTypeMismatch, match="file type"):
        assert_patch_matches_nature(patch, ["README.md"], nature="code")


def test_code_bug_empty_patch_is_missing_target():
    with pytest.raises(DefectTargetNotFound, match="No code modifications possible"):
        assert_patch_matches_nature("", [], nature="code")


def test_qa_rejects_markdown_patch_for_logic_bug(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "README.md").write_text("# x\n", encoding="utf-8")
    patch = (
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1 +1,2 @@\n"
        " # x\n"
        "+note\n"
    )
    proposal = FixProposal(
        summary="Document the bug",
        patch=patch,
        patch_revision=revision_for(patch),
        affected_files=["README.md"],
        reasoning="Could not find login.py so the README was edited.",
    )
    qa = QAEngineer(validation=None, patcher=None)  # type: ignore[arg-type]
    with pytest.raises(PatchTypeMismatch, match="file type"):
        qa.preflight(str(repo), proposal, issue_nature="code", issue_title="Login is broken")


def test_repair_investigator_halts_on_missing_login(tmp_path):
    from app.factory import create_repair_orchestrator

    repo = tmp_path / "proj"
    repo.mkdir()
    (repo / "README.md").write_text("# App\nLogin is described here only.\n", encoding="utf-8")
    (repo / "calculator.py").write_text("def calculate():\n    return 1\n", encoding="utf-8")
    orch = create_repair_orchestrator("mock")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    db = sessionmaker(bind=engine, future=True)()
    session = orch.create_and_investigate(
        db,
        title="Login accepts any password",
        description="The login function accepts any non-empty password.",
        repository_path=str(repo),
    )
    assert session.state == "BLOCKED"
    assert session.proposal is None
    assert DEFECT_TARGET_NOT_FOUND in session.message
    assert session.investigation is not None
    assert session.investigation.target_found is False


def test_docs_nature_allows_markdown():
    assert classify_issue_nature("Typo in README", "The documentation markdown is wrong") == "docs"
    patch = (
        "--- a/README.md\n"
        "+++ b/README.md\n"
        "@@ -1 +1,2 @@\n"
        " # x\n"
        "+fixed typo\n"
    )
    paths = assert_patch_matches_nature(patch, ["README.md"], nature="docs")
    assert paths == ["README.md"]
    assert QA_FILE_TYPE_REJECT
