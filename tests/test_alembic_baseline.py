from alembic.config import Config
from alembic.script import ScriptDirectory


def test_alembic_has_linear_baseline():
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())
    assert revisions
    assert revisions[-1].revision == "0001_baseline"
    assert script.get_current_head() == "0002_identity"
