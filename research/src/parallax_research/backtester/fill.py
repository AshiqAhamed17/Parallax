"""CPMM-aware fill simulation (Task 11.2).

Manifold prices via a CPMM ("Maniswap"): a pool of `yes`/`no` shares held to the invariant
`yes^p · no^(1-p) = k`, with marginal probability `P(YES) = p·no / (p·no + (1-p)·yes)`
(`implementation.md` §7, doc 03). `p` is the market's resting probability parameter (0.5 for a
standard binary market — when `yes == no` the price is exactly `p`).

To buy `stake` mana of YES: the AMM adds `stake` to *both* pools (minting matched YES+NO), then
withdraws YES shares to restore the invariant. The shares you receive and the effective price you
paid follow directly:

    yes' = yes · (no / (no + stake))^((1-p)/p)      # YES pool after
    no'  = no + stake                                # NO pool after
    shares = (yes + stake) − yes'                    # YES shares acquired
    effective_price = stake / shares                 # mana per share

(NO buys are the mirror image.) The fill preserves `k` by construction — that invariant is the
defining property and the strongest test. This module simulates fills against a historical pool
state; it never places a real bet (constraint §2.1).
"""

from __future__ import annotations

from dataclasses import dataclass

YES = "YES"
NO = "NO"


@dataclass(frozen=True)
class CpmmPool:
    """A Maniswap pool: `yes`/`no` share reserves and the resting-probability parameter `p`."""

    yes: float
    no: float
    p: float = 0.5

    def __post_init__(self) -> None:
        if self.yes <= 0 or self.no <= 0:
            raise ValueError("pool reserves must be positive")
        if not 0.0 < self.p < 1.0:
            raise ValueError("p must be in (0, 1)")

    @property
    def probability(self) -> float:
        """Marginal P(YES)."""
        return (self.p * self.no) / (self.p * self.no + (1.0 - self.p) * self.yes)

    @property
    def invariant(self) -> float:
        """`k = yes^p · no^(1-p)` — constant across fills."""
        return self.yes**self.p * self.no ** (1.0 - self.p)

    @classmethod
    def from_probability(cls, probability: float, liquidity: float, p: float = 0.5) -> CpmmPool:
        """Build a pool with a given marginal `probability` and total reserves `liquidity` (yes+no).

        Historical snapshots store the probability, not the raw reserves, so the backtester
        reconstructs a pool of an assumed size from the stored probability (liquidity supplied by the
        caller, Task 11.3).
        """
        if not 0.0 < probability < 1.0:
            raise ValueError("probability must be in (0, 1)")
        if liquidity <= 0:
            raise ValueError("liquidity must be positive")
        # n/y ratio that yields the target marginal probability, then split `liquidity` accordingly.
        ratio = (probability * (1.0 - p)) / (p * (1.0 - probability))  # no / yes
        yes = liquidity / (1.0 + ratio)
        no = liquidity - yes
        return cls(yes=yes, no=no, p=p)


@dataclass(frozen=True)
class Fill:
    """The simulated result of buying `stake` mana on one side of a market."""

    side: str
    stake: float
    shares: float
    effective_price: float  # mana paid per share (each share pays 1 if that side resolves true)
    prob_before: float
    prob_after: float
    pool_after: CpmmPool


def simulate_fill(pool: CpmmPool, side: str, stake: float) -> Fill:
    """Simulate buying `stake` mana of `side` (YES/NO) against `pool`.

    Returns the shares acquired, the effective price, and the post-fill pool/probability. The
    post-fill pool preserves the CPMM invariant `k`.
    """
    if stake <= 0:
        raise ValueError("stake must be positive")
    y, n, p = pool.yes, pool.no, pool.p

    if side == YES:
        new_yes = y * (n / (n + stake)) ** ((1.0 - p) / p)
        new_no = n + stake
        shares = (y + stake) - new_yes
    elif side == NO:
        new_no = n * (y / (y + stake)) ** (p / (1.0 - p))
        new_yes = y + stake
        shares = (n + stake) - new_no
    else:
        raise ValueError(f"side must be {YES!r} or {NO!r}, got {side!r}")

    pool_after = CpmmPool(yes=new_yes, no=new_no, p=p)
    return Fill(
        side=side,
        stake=stake,
        shares=shares,
        effective_price=stake / shares,
        prob_before=pool.probability,
        prob_after=pool_after.probability,
        pool_after=pool_after,
    )
