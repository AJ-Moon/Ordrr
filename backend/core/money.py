from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Optional

CENT = Decimal("0.01")


def to_cents(value: object) -> int:
    if value is None or value == "":
        return 0
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"Invalid monetary value: {value!r}") from exc
    return int(amount * 100)


def from_cents(value: Optional[int]) -> Decimal:
    return (Decimal(int(value or 0)) / 100).quantize(CENT)


def cents_to_float(value: Optional[int]) -> float:
    return float(from_cents(value))


def percentage_of_cents(amount_cents: int, percent: int) -> int:
    if amount_cents < 0 or percent < 0:
        raise ValueError("amount and percent must be non-negative")
    return int((Decimal(amount_cents) * Decimal(percent) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def sum_cents(values: Iterable[int]) -> int:
    return sum(int(value) for value in values)


@dataclass(frozen=True)
class MarginBreakdown:
    revenue_cents: int
    ingredient_cost_cents: int
    packaging_cost_cents: int
    payment_cost_cents: int
    commission_cents: int
    refund_cents: int

    @property
    def contribution_margin_cents(self) -> int:
        return (
            self.revenue_cents
            - self.ingredient_cost_cents
            - self.packaging_cost_cents
            - self.payment_cost_cents
            - self.commission_cents
            - self.refund_cents
        )
