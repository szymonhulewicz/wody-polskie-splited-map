import os
import math
import time
import warnings
from pathlib import Path

import numpy as np
import geopandas as gpd
from shapely.geometry import box

warnings.filterwarnings("ignore")

# =========================
# KONFIGURACJA
# =========================

typy = ["Rzeki", "Morze"]
dorzecza = ["Odra", "Dunaj", "Łaba", "Niemen", "Pregola", "Wisła"]
scenariusze = ["1", "02", "10"]

base_path = Path("/home/ailab-user/wody_polskie/Wody_Polskie")
out_base = Path("/home/ailab-user/splited-map")

target_parts = 1000
overlap_ratio = 0.10

out_base.mkdir(parents=True, exist_ok=True)

# =========================
# FUNKCJA DZIELĄCA PLIK SHP
# =========================

def split_shp_to_tiles(input_shp, typ, rzeka, scen):
    start = time.time()

    print(f"\nPrzetwarzam: {input_shp}")

    gdf = gpd.read_file(input_shp)

    if gdf.empty:
        print("Pusty plik — pomijam")
        return

    if gdf.crs is None:
        print("Brak CRS — pomijam")
        return

    # Nazwy plików mają mieć longitude/latitude w systemie dziesiętnym
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

            # Realny zakres ma 10% nakładki,
            # ale nazwa pliku zostaje po zakresie nominalnym
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
    print(f"Zapisano {counter} kafelków dla {input_shp.name} w {elapsed}s")


# =========================
# GŁÓWNA PĘTLA
# =========================

for typ in typy:
    for rzeka in dorzecza:

        if typ == "Morze":
            suffix = "_M"
        else:
            suffix = ""

        for scen in scenariusze:

            input_shp = (
                base_path
                / typ
                / "Dorzecza"
                / rzeka
                / "MZP"
                / f"glebokosc_{scen}{suffix}.shp"
            )

            if not input_shp.exists():
                print(f"Nie istnieje: {input_shp}")
                continue

            split_shp_to_tiles(input_shp, typ, rzeka, scen)

print("\nGotowe.")
print(f"Wyniki zapisane w: {out_base}")