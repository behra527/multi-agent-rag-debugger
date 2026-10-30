import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from store import get_user_name, init_db


def test_get_user_name_by_id():
    init_db()
    assert get_user_name(1) == "Ada"
