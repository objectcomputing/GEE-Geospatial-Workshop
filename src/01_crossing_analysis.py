"""
Phase 1 — Crossing Analysis
Filter BNSF crossings to at-grade, public crossings within LiDAR milepost windows.
"""

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

import pandas as pd
from config import DATA_ROOT, LIDAR_MP_WINDOWS, OUTPUT_DIR


def in_any_mp_window(milepost, windows):
    """Return True if milepost falls within any (lo, hi) window."""
    return any(lo <= milepost <= hi for lo, hi in windows)


def main():
    csv_path = DATA_ROOT / "bnsf_bnsf_latest.csv"
    df = pd.read_csv(csv_path)

    print(f"Loaded {len(df):,} rows from bnsf_bnsf_latest.csv")
    print(f"\nColumn names ({len(df.columns)}):")
    for col in df.columns:
        print(f"  {col}")

    # --- Filters ---
    at_grade = df["Grade_Code"] == 1
    public = df["Xing_Type_Code"].isin([1, 2])
    in_mp = df["Milepost"].apply(lambda mp: in_any_mp_window(mp, LIDAR_MP_WINDOWS))

    filtered = df[at_grade & public & in_mp].copy()

    print(f"\n{'='*60}")
    print(f"Filtered crossings: {len(filtered)}")
    print(f"  Grade_Code == 1 (at-grade)")
    print(f"  Xing_Type_Code in (1, 2) (public)")
    print(f"  Milepost within LiDAR windows: {LIDAR_MP_WINDOWS}")
    print(f"{'='*60}")

    # --- Per-window counts ---
    print("\nCrossings per milepost window:")
    for lo, hi in LIDAR_MP_WINDOWS:
        count = filtered["Milepost"].between(lo, hi).sum()
        print(f"  MP {lo}–{hi}: {count} crossing(s)")

    # --- Save ---
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "grade_crossing_candidates.csv"
    filtered.to_csv(out_path, index=False)
    print(f"\nSaved to: {out_path}")

    # --- Preview ---
    if not filtered.empty:
        preview_cols = [
            "DOT_Num", "Milepost", "Street", "City",
            "Latitude", "Longitude", "TK_Angle", "Num_Lanes", "WIDTH", "Height",
        ]
        preview_cols = [c for c in preview_cols if c in filtered.columns]
        print(f"\nCandidate crossings:")
        print(filtered[preview_cols].to_string(index=False))


if __name__ == "__main__":
    main()
