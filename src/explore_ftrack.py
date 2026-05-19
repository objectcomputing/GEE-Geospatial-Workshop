"""
Explore the FTRACK layer from BNSF_Ferrovia_Export.gdb.
Prints schema info, identifies Pikes Peak features, and produces a map.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import geopandas as gpd
import matplotlib.pyplot as plt
import folium
import pandas as pd
from config import DATA_ROOT, OUTPUT_DIR


def main():
    gdb_path = DATA_ROOT / "BNSF_Ferrovia_Export.gdb"
    print(f"Loading FTRACK from: {gdb_path}")
    gdf = gpd.read_file(gdb_path, layer="FTRACK")

    # 1. CRS
    print(f"\nCRS: {gdf.crs}")

    # 2. Column names and dtypes
    print(f"\nColumns ({len(gdf.columns)}):")
    for col in gdf.columns:
        print(f"  {col:30s} {gdf[col].dtype}")

    # 3. Sample rows
    print("\nSample rows (first 5):")
    print(gdf.head(5).to_string())

    # 4. Unique values of subdivision/route-like columns
    candidate_cols = [c for c in gdf.columns if any(
        kw in c.upper() for kw in ["SUBDIV", "SUBDV", "ROUTE", "LINE", "SEG", "LOC"]
    )]
    print(f"\nSubdivision/route candidate columns: {candidate_cols}")
    for col in candidate_cols:
        nunique = gdf[col].nunique()
        print(f"\n  {col} — {nunique} unique values")
        if nunique <= 50:
            print(f"    {sorted(gdf[col].dropna().unique())}")
        else:
            print(f"    (showing first 30): {sorted(gdf[col].dropna().unique())[:30]}")

    # 5. Total feature count
    print(f"\nTotal features: {len(gdf):,}")

    # --- Plot ---
    pikes_peak_col = None
    for col in candidate_cols:
        if gdf[col].astype(str).str.contains("PIKES PEAK", case=False, na=False).any():
            pikes_peak_col = col
            break

    if pikes_peak_col is None:
        # fallback: search all string columns
        for col in gdf.select_dtypes(include="object").columns:
            if gdf[col].astype(str).str.contains("PIKES PEAK", case=False, na=False).any():
                pikes_peak_col = col
                break

    if pikes_peak_col:
        mask = gdf[pikes_peak_col].astype(str).str.contains("PIKES PEAK", case=False, na=False)
        print(f"\nPikes Peak features found via column '{pikes_peak_col}': {mask.sum()}")
    else:
        print("\nWARNING: Could not find Pikes Peak features in any column.")
        mask = gpd.pd.Series([False] * len(gdf))

    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    gdf.plot(ax=ax, color="lightgray", linewidth=0.3)
    if mask.any():
        gdf[mask].plot(ax=ax, color="red", linewidth=1.5)
    ax.set_title("BNSF FTRACK — Pikes Peak highlighted", fontsize=14)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "ftrack_overview.png"
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"\nPlot saved to: {out_path}")


def make_folium_map():
    """Create an interactive folium map of Pikes Peak FTRACK + crossing candidates."""
    gdb_path = DATA_ROOT / "BNSF_Ferrovia_Export.gdb"
    print("Loading FTRACK for folium map...")
    gdf = gpd.read_file(gdb_path, layer="FTRACK")

    # Filter to Pikes Peak
    pp = gdf[gdf["SUBDV"].str.upper() == "PIKES PEAK"].copy()
    print(f"Pikes Peak FTRACK segments: {len(pp)}")

    # Center map on midpoint of Pikes Peak tracks
    bounds = pp.geometry.total_bounds  # [minx, miny, maxx, maxy]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="OpenStreetMap")

    # Plot FTRACK segments as red polylines
    for _, row in pp.iterrows():
        geom = row.geometry
        coords = []
        if geom.geom_type == "MultiLineString":
            for part in geom.geoms:
                coords.extend([(c[1], c[0]) for c in part.coords])
        elif geom.geom_type == "LineString":
            coords = [(c[1], c[0]) for c in geom.coords]

        if coords:
            tooltip = (
                f"SUBDV: {row['SUBDV']}<br>"
                f"MP: {row['MILE_POST_BEG']:.3f} – {row['MILE_POST_END']:.3f}<br>"
                f"TRACK_TYPE: {row['TRACK_TYPE']}"
            )
            folium.PolyLine(
                locations=coords,
                color="red",
                weight=3,
                opacity=0.8,
                tooltip=tooltip,
            ).add_to(m)

    # Load crossing candidates
    candidates_path = OUTPUT_DIR / "grade_crossing_candidates.csv"
    if candidates_path.exists():
        cdf = pd.read_csv(candidates_path)
        print(f"Crossing candidates loaded: {len(cdf)}")
        for _, row in cdf.iterrows():
            tooltip = (
                f"DOT_Num: {row['DOT_Num']}<br>"
                f"Milepost: {row['Milepost']}<br>"
                f"TK_Angle: {row.get('TK_Angle', 'N/A')}"
            )
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=6,
                color="blue",
                fill=True,
                fill_color="blue",
                fill_opacity=0.7,
                tooltip=tooltip,
            ).add_to(m)
    else:
        print(f"WARNING: {candidates_path} not found — skipping crossings.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "pikes_peak_interactive.html"
    m.save(str(out_path))
    print(f"Folium map saved to: {out_path}")


if __name__ == "__main__":
    main()
    make_folium_map()
