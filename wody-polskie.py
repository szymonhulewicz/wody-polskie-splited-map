import os
import math
import time
import warnings
from pathlib import Path

import numpy as np
import geopandas as gpd
from shapely.geometry import box

warnings.filterwarnings("ignore")

typy = ["Rzeki", "Morze"]
dorzecza = ["Odra", "Dunaj", "Łaba", "Niemen", "Pregola", "Wisła"]
scenariusze = ["1", "02", "10"]

base_path = Path("/home/ailab-user/wody_polskie/Wody_Polskie")
out_base = Path("/home/ailab-user/splited-map")
out_base.mkdir(parents=True, exist_ok=True)

max_parts_for_wisla = 1000
overlap_ratio = 0.10


def get_input_path(typ, rzeka, scen):
    suffix = "_M" if typ == "Morze" else ""
    return (
        base_path
        / typ
        / "Dorzecza"
        / rzeka
        / "MZP"
        / f"glebokosc_{scen}{suffix}.shp"
    )


def read_bounds_area(input_shp):
    gdf = gpd.read_file(input_shp)

    if gdf.empty or gdf.crs is None:
        return None

    gdf = gdf.to_crs(4326)
    lon_min, lat_min, lon_max, lat_max = gdf.total_bounds

    area = (lon_max - lon_min) * (lat_max - lat_min)

    return {
        "lon_min": lon_min,
        "lat_min": lat_min,
        "lon_max": lon_max,
        "lat_max": lat_max,
        "area": area
    }


# =========================
# 1. ZBIERAMY PLIKI I ICH ROZMIARY
# =========================

files_info = []

for typ in typy:
    for rzeka in dorzecza:
        for scen in scenariusze:
            input_shp = get_input_path(typ, rzeka, scen)

            if not input_shp.exists():
                print(f"Nie istnieje: {input_shp}")
                continue

            bounds = read_bounds_area(input_shp)

            if bounds is None:
                print(f"Nie udało się odczytać bbox: {input_shp}")
                continue

            files_info.append({
                "typ": typ,
                "rzeka": rzeka,
                "scen": scen,
                "path": input_shp,
                **bounds
            })


# =========================
# 2. SZUKAMY NAJWIĘKSZEJ WISŁY
# =========================

wisla_files = [f for f in files_info if f["rzeka"] == "Wisła"]

if not wisla_files:
    raise ValueError("Nie znaleziono żadnego pliku dla Wisły")

wisla_max_area = max(f["area"] for f in wisla_files)

print(f"Największa powierzchnia Wisły: {wisla_max_area}")


# =========================
# 3. LICZBA KAFELKÓW PROPORCJONALNIE DO WISŁY
# =========================

for f in files_info:
    ratio = f["area"] / wisla_max_area

    target_parts = round(max_parts_for_wisla * ratio)

    # minimum 1 plik
    target_parts = max(1, target_parts)

    # maksimum 1000
    target_parts = min(max_parts_for_wisla, target_parts)

    f["target_parts"] = target_parts

    print(
        f'{f["typ"]} {f["rzeka"]} glebokosc_{f["scen"]}: '
        f'{target_parts} części'
    )


# =========================
# 4. FUNKCJA ZAPISUJĄCA CAŁY PLIK
# =========================

def save_whole_file_with_coords(input_shp, typ, rzeka, scen):
    gdf = gpd.read_file(input_shp).to_crs(4326)
    gdf = gdf[gdf.geometry.notna()].copy()

    if gdf.empty:
        return

    gdf["geometry"] = gdf.geometry.make_valid()

    lon_min, lat_min, lon_max, lat_max = gdf.total_bounds

    filename = (
        f"{typ}_{rzeka}_glebokosc_{scen}_"
        f"lon_{lon_min:.6f}_{lon_max:.6f}_"
        f"lat_{lat_min:.6f}_{lat_max:.6f}.shp"
    )

    output_shp = out_base / filename
    gdf.to_file(output_shp, driver="ESRI Shapefile", encoding="utf-8")

    print(f"Zapisano cały plik: {filename}")


# =========================
# 5. FUNKCJA DZIELĄCA NA KAFELKI
# =========================

def split_shp_to_tiles(input_shp, typ, rzeka, scen, target_parts):
    start = time.time()

    print(f"\nPrzetwarzam: {input_shp}")
    print(f"Liczba kafelków: {target_parts}")

    if target_parts <= 1:
        save_whole_file_with_coords(input_shp, typ, rzeka, scen)
        return

    gdf = gpd.read_file(input_shp)

    if gdf.empty or gdf.crs is None:
        print("Pusty plik albo brak CRS — pomijam")
        return

    gdf = gdf.to_crs(4326)
    gdf = gdf[gdf.geometry.notna()].copy()

    if gdf.empty:
        print("Brak geometrii — pomijam")
        return

    gdf["geometry"] = gdf.geometry.make_valid()

    lon_min, lat_min, lon_max, lat_max = gdf.total_bounds

    n_cols = math.ceil(math.sqrt(target_parts))
    n_rows = math.ceil(target_parts / n_cols)

    lon_edges = np.linspace(lon_min, lon_max, n_cols + 1)
    lat_edges = np.linspace(lat_min, lat_max, n_rows + 1)

    counter = 0

    for i in range(n_cols):
        for j in range(n_rows):
            lon0 = lon_edges[i]
            lon1 = lon_edges[i + 1]
            lat0 = lat_edges[j]
            lat1 = lat_edges[j + 1]

            lon_width = lon1 - lon0
            lat_height = lat1 - lat0

            real_lon0 = lon0 - lon_width * overlap_ratio
            real_lon1 = lon1 + lon_width * overlap_ratio
            real_lat0 = lat0 - lat_height * overlap_ratio
            real_lat1 = lat1 + lat_height * overlap_ratio

            real_tile = box(real_lon0, real_lat0, real_lon1, real_lat1)

            idx = gdf.sindex.query(real_tile, predicate="intersects")
            part = gdf.iloc[idx].copy()

            if part.empty:
                continue

            part = gpd.clip(part, real_tile)

            if part.empty:
                continue

            filename = (
                f"{typ}_{rzeka}_glebokosc_{scen}_"
                f"lon_{lon0:.6f}_{lon1:.6f}_"
                f"lat_{lat0:.6f}_{lat1:.6f}.shp"
            )

            output_shp = out_base / filename
            part.to_file(output_shp, driver="ESRI Shapefile", encoding="utf-8")

            counter += 1

    elapsed = round(time.time() - start, 2)
    print(f"Zapisano {counter} kafelków w {elapsed}s")


# =========================
# 6. GŁÓWNE WYKONANIE
# =========================

for f in files_info:
    split_shp_to_tiles(
        input_shp=f["path"],
        typ=f["typ"],
        rzeka=f["rzeka"],
        scen=f["scen"],
        target_parts=f["target_parts"]
    )

print("\nGotowe.")
print(f"Wyniki zapisane w: {out_base}")