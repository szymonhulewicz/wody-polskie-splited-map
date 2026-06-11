import re
from pathlib import Path
import geopandas as gpd
import pandas as pd

split_dir = Path("/home/ailab-user/splited-map")

tile_pattern = re.compile(
    r"^(?P<typ>.+?)_(?P<rzeka>.+?)_glebokosc_(?P<scen>.+?)_"
    r"lon_(?P<lon_min>-?\d+\.\d+)_(?P<lon_max>-?\d+\.\d+)_"
    r"lat_(?P<lat_min>-?\d+\.\d+)_(?P<lat_max>-?\d+\.\d+)\.shp$"
)


def find_tiles_for_points(typ, rzeka, scen, points_gdf):
    """
    Zwraca listę małych plików SHP, których nominalny zakres obejmuje punkty.
    points_gdf musi być w EPSG:4326.
    """

    lon_min, lat_min, lon_max, lat_max = points_gdf.total_bounds

    matching_files = []

    prefix = f"{typ}_{rzeka}_glebokosc_{scen}_"

    for shp_path in split_dir.glob(f"{prefix}*.shp"):
        match = tile_pattern.match(shp_path.name)

        if not match:
            continue

        tile_lon_min = float(match.group("lon_min"))
        tile_lon_max = float(match.group("lon_max"))
        tile_lat_min = float(match.group("lat_min"))
        tile_lat_max = float(match.group("lat_max"))

        intersects_bbox = (
            tile_lon_max >= lon_min and
            tile_lon_min <= lon_max and
            tile_lat_max >= lat_min and
            tile_lat_min <= lat_max
        )

        if intersects_bbox:
            matching_files.append(shp_path)

    return matching_files


def read_tiles_for_points(typ, rzeka, scen, points_gdf):
    tile_files = find_tiles_for_points(typ, rzeka, scen, points_gdf)

    if len(tile_files) == 0:
        return None

    maps = []

    for tile_file in tile_files:
        maps.append(gpd.read_file(tile_file))

    gdf_polygons = pd.concat(maps, ignore_index=True)
    gdf_polygons = gpd.GeoDataFrame(gdf_polygons, geometry="geometry", crs="EPSG:4326")

    return gdf_polygons

for typ in typy:
    for rzeka in dorzecza:

        for scen in scenariusze:

            print(f"\nSzukam kafelków dla: {typ}, {rzeka}, {scen}")

            t_load_start = time.time()

            mapa_scen = read_tiles_for_points(
                typ=typ,
                rzeka=rzeka,
                scen=scen,
                points_gdf=gdf_points.to_crs(4326)
            )

            if mapa_scen is None:
                print(f"Brak kafelka dla: {typ}, {rzeka}, {scen}")
                continue

            mapa_scen = mapa_scen.to_crs(CRS)

            t_load_end = time.time()
            print(f"Czas ładowania mapy: {round(t_load_end - t_load_start, 2)}s")
            print("Mapa z kafelków wczytana")

            t_calc_start = time.time()

            batch = gdf_points.to_crs(epsg=2180).copy()
            gdf_polygons = mapa_scen.to_crs(epsg=2180)

            gdf_polygons["GLEBOKOSC"] = pd.to_numeric(
                gdf_polygons["GLEBOKOSC"],
                errors="coerce"
            )

            batch["geometry"] = batch.geometry.buffer(buffer)

            intersection = gpd.overlay(
                batch,
                gdf_polygons,
                how="intersection"
            )

            intersection["area"] = intersection.geometry.area

            pole_bufora = np.pi * buffer ** 2

            if intersection.shape[0] > 0:
                weighted_mean = round(
                    intersection.groupby("EXPOSURE_ID").apply(
                        lambda x: (x["GLEBOKOSC"] * x["area"]).sum() / pole_bufora
                    ),
                    0
                )

                median_values = round(
                    intersection.groupby("EXPOSURE_ID")["GLEBOKOSC"].median(),
                    0
                )

                batch = batch.merge(
                    weighted_mean.to_frame(name="wei_avg"),
                    left_on="EXPOSURE_ID",
                    right_index=True
                )

                batch = batch.merge(
                    median_values.to_frame(name="median_value"),
                    left_on="EXPOSURE_ID",
                    right_index=True
                )

            else:
                batch["median_value"] = 0
                batch["wei_avg"] = 0

            wp_scen = f"mzp_{scen}"
            batch["SCEN"] = wp_scen
            batch["TYP"] = typ
            batch["DORZECZE"] = rzeka

            t_calc_end = time.time()

            print("\n=====WYNIK=====")
            print(f"SCENARIUSZ: {wp_scen}")
            print(f"TYP: {typ}")
            print(f"DORZECZE: {rzeka}")
            print(f"Czas wyznaczania wyniku: {round(t_calc_end - t_calc_start, 2)}s")
            print("===============\n")

            if "batch_full" in locals():
                batch_full = pd.concat([batch_full, batch], ignore_index=True)
            else:
                batch_full = batch.copy()