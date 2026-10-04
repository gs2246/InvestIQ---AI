"""Number formatting shared by templates and margin notes, so a figure reads the same everywhere."""
import math


def format_inr(value, decimals: int = 2) -> str:
    """Rupee amount with Indian digit grouping: 1234567.8 -> '₹12,34,567.80'."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    sign = "-" if value < 0 else ""
    whole, _, frac = f"{abs(value):.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}" + (f".{frac}" if frac else "")


def format_pct(fraction: float, decimals: int = 1) -> str:
    """0.2439 -> '+24.4%', -0.142 -> '−14.2%' (a real minus sign)."""
    v = fraction * 100
    sign = "+" if v > 0 else "−" if v < 0 else ""
    return f"{sign}{abs(v):.{decimals}f}%"
