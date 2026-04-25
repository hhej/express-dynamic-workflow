"""Generate Express rate table CSV with documented assumptions.

Base rates modeled on Thai Express domestic pricing for Bangkok Metro.
Bounce is same-day courier, retail_standard is 2-3 day, retail_fast is
next-day. Zone multipliers reflect increasing distance from Bangkok hub.

Assumptions (D-01 through D-04):
- 3 shipping types: bounce, retail_standard, retail_fast
- 3 zones: central-1 (Bangkok Metro), central-2 (Greater Central),
  central-3 (Extended Central)
- 5 weight tiers: 0-5, 5-10, 10-20, 20-50, 50-999 kg
- Base rates in THB: ~50-500 range for central-1
- Zone multipliers: central-1=1.0, central-2=1.25, central-3=1.55
- Final rate = base * zone_multiplier, rounded to nearest integer
"""

from pathlib import Path

import pandas as pd


# Shipping types offered by Express
SHIPPING_TYPES: list[str] = ["bounce", "retail_standard", "retail_fast"]

# Zone definitions for Bangkok Metro
ZONES: list[str] = ["central-1", "central-2", "central-3"]

# Weight tiers in kg (min, max)
WEIGHT_TIERS: list[tuple[int, int]] = [
    (0, 5),
    (5, 10),
    (10, 20),
    (20, 50),
    (50, 999),
]

# Base rates per shipping type for central-1 (THB), indexed by weight tier
BASE_RATES: dict[str, list[int]] = {
    "bounce": [55, 85, 130, 220, 380],
    "retail_standard": [50, 75, 110, 190, 340],
    "retail_fast": [65, 100, 155, 260, 450],
}

# Zone distance multipliers (central-1 is base)
ZONE_MULTIPLIERS: dict[str, float] = {
    "central-1": 1.0,
    "central-2": 1.25,
    "central-3": 1.55,
}


def main() -> None:
    """Generate rate table CSV and write to data/raw/express_rate_table.csv."""
    rows: list[dict] = []

    for shipping_type in SHIPPING_TYPES:
        for zone in ZONES:
            multiplier = ZONE_MULTIPLIERS[zone]
            for i, (weight_min, weight_max) in enumerate(WEIGHT_TIERS):
                base = BASE_RATES[shipping_type][i]
                rate = round(base * multiplier)
                rows.append(
                    {
                        "shipping_type": shipping_type,
                        "zone": zone,
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
    print(f"Zones: {df['zone'].unique().tolist()}")
    print(f"Rate range: {df['base_rate_thb'].min()}-{df['base_rate_thb'].max()} THB")


if __name__ == "__main__":
    main()
