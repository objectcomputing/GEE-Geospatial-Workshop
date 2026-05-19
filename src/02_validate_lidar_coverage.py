"""
Phase 1 supplement — Validate LiDAR coverage over crossing candidates.
Reads bounding boxes from LiDAR tile headers (EPSG:32613), reprojects to WGS84,
and overlays them on a folium map alongside Pikes Peak FTRACK and crossings.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import laspy
import folium
import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from config import DATA_ROOT, OUTPUT_DIR

def find_complete_lidar_tiles(root):
    """Walk DATA_ROOT and return all .copc.laz files (excluding .gstmp artifacts)."""
    tiles = []
    for path in sorted(root.rglob("*.copc.laz")):
        if path.name.endswith(".gstmp"):
            continue
        tiles.append(path)
    return tiles


def get_tile_bounds(filepath):
    """Read LiDAR header and return (x_min, y_min, x_max, y_max) in native CRS."""
    with laspy.open(filepath) as f:
        hdr = f.header
        return (hdr.x_min, hdr.y_min, hdr.x_max, hdr.y_max)


def main():
    # Dynamically discover all complete LiDAR tiles
    lidar_tiles = find_complete_lidar_tiles(DATA_ROOT)

    print(f"Complete LiDAR tiles found: {len(lidar_tiles)}")
    print("-" * 70)
    for p in lidar_tiles:
        print(f"  {p.relative_to(DATA_ROOT)}")

    transformer = Transformer.from_crs("EPSG:32613", "EPSG:4326", always_xy=True)

    tile_extents = []
    print(f"\nLiDAR Tile Bounding Boxes (EPSG:32613):")
    print("-" * 70)
    for filepath in lidar_tiles:
        x_min, y_min, x_max, y_max = get_tile_bounds(filepath)
        label = filepath.stem.split("_")[-3]  # extract milepost number from filename
        print(
            f"  {filepath.name:<55s} | "
            f"X: {x_min:.1f} – {x_max:.1f} | Y: {y_min:.1f} – {y_max:.1f}"
        )

        # Reproject corners to WGS84
        lon_min, lat_min = transformer.transform(x_min, y_min)
        lon_max, lat_max = transformer.transform(x_max, y_max)

        tile_extents.append({
            "label": f"MP {label}",
            "filename": filepath.name,
            "bounds_4326": [[lat_min, lon_min], [lat_max, lon_max]],
        })

    print(f"\n{len(tile_extents)} tiles successfully read.")

    # --- Build folium map ---
    # Load Pikes Peak FTRACK
    gdb_path = DATA_ROOT / "BNSF_Ferrovia_Export.gdb"
    print("\nLoading FTRACK (Pikes Peak only)...")
    gdf = gpd.read_file(gdb_path, layer="FTRACK")
    pp = gdf[gdf["SUBDV"].str.upper() == "PIKES PEAK"].copy()

    bounds = pp.geometry.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=10, tiles="OpenStreetMap")

    # FTRACK polylines
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
                locations=coords, color="red", weight=3, opacity=0.8, tooltip=tooltip
            ).add_to(m)

    # Crossing candidates
    candidates_path = OUTPUT_DIR / "grade_crossing_candidates.csv"
    if candidates_path.exists():
        cdf = pd.read_csv(candidates_path)
        for _, row in cdf.iterrows():
            tooltip = (
                f"DOT_Num: {row['DOT_Num']}<br>"
                f"Milepost: {row['Milepost']}<br>"
                f"TK_Angle: {row.get('TK_Angle', 'N/A')}"
            )
            folium.CircleMarker(
                location=[row["Latitude"], row["Longitude"]],
                radius=6, color="blue", fill=True,
                fill_color="blue", fill_opacity=0.7, tooltip=tooltip,
            ).add_to(m)

    # LiDAR tile bounding boxes
    for tile in tile_extents:
        folium.Rectangle(
            bounds=tile["bounds_4326"],
            color="green",
            fill=True,
            fill_opacity=0.1,
            weight=2,
            tooltip=f"{tile['filename']}<br>{tile['label']}",
        ).add_to(m)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "lidar_coverage_validation.html"
    m.save(str(out_path))
    print(f"\nMap saved to: {out_path}")


if __name__ == "__main__":
    main()
