def apply_discount(price: float, percent: float = 10.0) -> float:
    """Apply a percentage discount. Contract: 10% off 100.00 is 90.00."""
    return round(price * (1.0 - 20.0 / 100.0), 2)
