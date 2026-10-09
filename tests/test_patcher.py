from app.tools.patcher import PatchApplier


def test_patcher_creates_isolated_workspace(tmp_path):
    source = tmp_path / "project"
    source.mkdir()

    file_path = source / "example.py"
    file_path.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    patcher = PatchApplier()

    workspace = patcher.create_workspace(source)

    copied_file = workspace / "example.py"

    assert workspace.exists()
    assert copied_file.exists()
    assert copied_file.read_text(
        encoding="utf-8"
    ) == "value = 1\n"

    assert workspace != source


def test_patcher_applies_valid_patch(tmp_path):
    source = tmp_path / "project"
    source.mkdir()

    file_path = source / "example.py"
    file_path.write_text(
        "value = 1\n",
        encoding="utf-8",
    )

    patcher = PatchApplier()

    workspace = patcher.create_workspace(source)

    patch = """\
diff --git a/example.py b/example.py
index 1234567..abcdefg 100644
--- a/example.py
+++ b/example.py
@@ -1 +1 @@
-value = 1
+value = 2
"""

    patcher.apply(workspace, patch)

    assert file_path.read_text(
        encoding="utf-8"
    ) == "value = 1\n"

    copied_file = workspace / "example.py"

    assert copied_file.read_text(
        encoding="utf-8"
    ) == "value = 2\n"


def test_patcher_rejects_empty_patch(tmp_path):
    source = tmp_path / "project"
    source.mkdir()

    patcher = PatchApplier()
    workspace = patcher.create_workspace(source)

    try:
        patcher.apply(workspace, "")
        assert False, "Expected ValueError"
    except ValueError:
        pass