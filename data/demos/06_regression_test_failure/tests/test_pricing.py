import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pricing import apply_discount


def test_ten_percent_off_one_hundred():
    assert apply_discount(100.0, 10.0) == 90.0


def test_custom_percent_is_honored():
    assert apply_discount(200.0, 25.0) == 150.0
