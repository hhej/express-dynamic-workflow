"""Generate Express rate table CSV with documented assumptions.

Phase 999.9 (D-05/D-06/D-07): origin_zone × dest_zone matrix.

Assumptions (D-01 through D-07):
- 3 shipping types: bounce, retail_standard, retail_fast
- 3 zones: central-1 (Bangkok Metro), central-2 (Greater Central),
  central-3 (Extended Central)
- 5 weight tiers: 0-5, 5-10, 10-20, 20-50, 50-999 kg
- Base rates in THB: ~50-500 range for central-1 dest
- ORIGIN_DEST_MULTIPLIER 3×3 symmetric matrix (D-06):
  M[origin_zone][dest_zone] = M[dest_zone][origin_zone]
  Diagonal = 1.0 (preserves v1.0 central-1 rates byte-for-byte —
  see Pitfall 3 in RESEARCH.md). Off-diagonal scales with zone
  distance: one-zone-apart = 1.25, two-zones-apart = 1.70.
- Final rate = base * M[origin_zone][dest_zone], rounded to nearest int.
- 135 rows = 3 origin × 3 dest × 3 ship × 5 weight (D-05).
"""

from pathlib import Path

import pandas as pd


SHIPPING_TYPES: list[str] = ["bounce", "retail_standard", "retail_fast"]
ZONES: list[str] = ["central-1", "central-2", "central-3"]
WEIGHT_TIERS: list[tuple[int, int]] = [
    (0, 5),
    (5, 10),
    (10, 20),
    (20, 50),
    (50, 999),
]
BASE_RATES: dict[str, list[int]] = {
    "bounce": [55, 85, 130, 220, 380],
    "retail_standard": [50, 75, 110, 190, 340],
    "retail_fast": [65, 100, 155, 260, 450],
}
# Phase 999.9 D-06: REPLACES legacy single-zone multiplier dict (Pitfall 3 —
# do NOT stack a single-zone multiplier on top of this matrix). Diagonal
# = 1.0 keeps v1.0 central-1 rates stable; off-diagonals are symmetric.
ORIGIN_DEST_MULTIPLIER: dict[str, dict[str, float]] = {
    "central-1": {"central-1": 1.00, "central-2": 1.25, "central-3": 1.70},
    "central-2": {"central-1": 1.25, "central-2": 1.00, "central-3": 1.45},
    "central-3": {"central-1": 1.70, "central-2": 1.45, "central-3": 1.00},
}


def main() -> None:
    """Generate 135-row rate table CSV (3 origin × 3 dest × 3 ship × 5 weight)."""
    rows: list[dict] = []

    for shipping_type in SHIPPING_TYPES:
        for origin_zone in ZONES:
            for dest_zone in ZONES:
                multiplier = ORIGIN_DEST_MULTIPLIER[origin_zone][dest_zone]
                for i, (weight_min, weight_max) in enumerate(WEIGHT_TIERS):
                    base = BASE_RATES[shipping_type][i]
                    rate = round(base * multiplier)
                    rows.append(
                        {
                            "shipping_type": shipping_type,
                            "origin_zone": origin_zone,
                            "dest_zone": dest_zone,
                            "weight_min_kg": weight_min,
                            "weight_max_kg": weight_max,
                            "base_rate_thb": rate,
                        }
                    )

    df = pd.DataFrame(rows)

    output_path = Path(__file__).parent.parent / "raw" / "express_rate_table.csv"
    df.to_csv(output_path, index=False)

    print(f"Generated {len(df)} rate table rows -> {output_path}")
    print(f"Shipping types: {df['shipping_type'].unique().tolist()}")
    print(f"Origin zones: {df['origin_zone'].unique().tolist()}")
    print(f"Dest zones: {df['dest_zone'].unique().tolist()}")
    print(
        f"Rate range: {df['base_rate_thb'].min()}-"
        f"{df['base_rate_thb'].max()} THB"
    )


if __name__ == "__main__":
    main()
