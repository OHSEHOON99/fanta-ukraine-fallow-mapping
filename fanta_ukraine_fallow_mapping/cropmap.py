import os
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.mask import mask
from rasterio.merge import merge
from shapely.geometry import box, mapping
from tqdm import tqdm


DEFAULT_CROPLAND_VALUES = [10, 11, 12, 20]


def load_boundary(boundary_file, epsg=4326):
    boundary = gpd.read_file(boundary_file)
    if boundary.crs is not None and boundary.crs.to_epsg() != epsg:
        boundary = boundary.to_crs(epsg=epsg)
    return boundary


def find_annual_tif_files(cropmap_dir):
    tif_files = []
    for root, _, files in os.walk(cropmap_dir):
        for file_name in files:
            if file_name.lower().endswith((".tif", ".tiff")) and "Annual" in file_name:
                tif_files.append(str(Path(root) / file_name))
    return sorted(tif_files)


def check_overlap(tif_path, polygons):
    with rasterio.open(tif_path) as src:
        tif_bounds = box(*src.bounds)
        return bool(polygons.intersects(tif_bounds).any())


def filter_overlapping_tifs(tif_files, polygons):
    return [tif for tif in tqdm(tif_files, desc="Checking overlap") if check_overlap(tif, polygons)]


def merge_tif_files(tif_files, band_index):
    if not tif_files:
        raise ValueError("No TIFF files to merge.")

    datasets = []
    try:
        for tif in tif_files:
            datasets.append(rasterio.open(tif))

        mosaic, out_transform = merge(datasets, indexes=[band_index])
        out_meta = datasets[0].meta.copy()
        out_meta.update(
            {
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": out_transform,
                "count": 1,
                "dtype": mosaic.dtype,
            }
        )
        return mosaic, out_meta
    finally:
        for src in datasets:
            src.close()


def mask_with_polygon(mosaic, out_meta, polygons, output_path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    shapes = [mapping(geom) for geom in polygons.geometry]
    mask_arr = geometry_mask(shapes, transform=out_meta["transform"], invert=True, out_shape=mosaic.shape[1:])
    masked_mosaic = np.where(mask_arr, mosaic[0], 0)

    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(masked_mosaic, 1)

    return output_path


def create_ukraine_cropmaps(cropmap_dir, boundary_file, output_dir, start_year=2013, end_year=2023, first_band_year=2000):
    boundary = load_boundary(boundary_file)
    tif_files = find_annual_tif_files(cropmap_dir)
    valid_tif_files = filter_overlapping_tifs(tif_files, boundary)
    if not valid_tif_files:
        raise ValueError("No annual TIFF files overlap with the boundary polygon.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    for year in tqdm(range(start_year, end_year + 1), desc="Processing years"):
        band_index = year - first_band_year + 1
        output_file = output_dir / f"masked_cropmap_{year}.tif"
        mosaic, out_meta = merge_tif_files(valid_tif_files, band_index)
        outputs.append(mask_with_polygon(mosaic, out_meta, boundary, output_file))
        print(f"Masked cropmap for {year} saved to {output_file}.")

    return outputs


def get_polygons_from_geojson(geojson_file, name_column="ADM1_NAME"):
    gdf = gpd.read_file(geojson_file)
    regions = []
    for _, row in gdf.iterrows():
        if row.geometry.is_empty:
            continue
        regions.append((row[name_column], row.geometry))
    if not regions:
        raise ValueError("No valid polygons found in the GeoJSON file.")
    return regions


def crop_raster_with_polygon(src, polygon):
    out_image, out_transform = mask(src, [polygon], crop=True)
    out_meta = src.meta.copy()
    out_meta.update(
        {
            "driver": "GTiff",
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform,
        }
    )
    return out_image, out_meta


def process_cropmap(file_paths, polygon, cropland_values=None, threshold=5, output_file=None):
    if cropland_values is None:
        cropland_values = DEFAULT_CROPLAND_VALUES
    if output_file is None:
        raise ValueError("output_file is required.")
    if not file_paths:
        raise ValueError("At least one cropmap file is required.")

    total_pixels = []
    print(f"Loading and cropping {len(file_paths)} cropmap files.")
    for file_path in tqdm(file_paths, desc="Processing files"):
        with rasterio.open(file_path) as src:
            out_image, out_meta = crop_raster_with_polygon(src, polygon)
            total_pixels.append(out_image[0])

    cropland_mask = np.isin(np.stack(total_pixels), cropland_values)
    result_map = np.sum(cropland_mask, axis=0) >= threshold
    result_map = np.where(result_map, 255, 0).astype(np.uint8)

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    out_meta.update(count=1, dtype=rasterio.uint8)
    with rasterio.open(output_file, "w", **out_meta) as dst:
        dst.write(result_map, 1)

    print(f"Cropland map saved to {output_file}.")
    return output_file


def generate_cropmaps_by_region(geojson_file, file_paths, output_base_dir, cropland_values=None, threshold=5):
    output_base_dir = Path(output_base_dir)
    output_base_dir.mkdir(parents=True, exist_ok=True)
    outputs = []

    for region_name, polygon in get_polygons_from_geojson(geojson_file):
        safe_region = str(region_name).replace("/", "_")
        output_file = output_base_dir / f"cropmap_{safe_region}.tif"
        outputs.append(
            process_cropmap(
                file_paths=file_paths,
                polygon=polygon,
                cropland_values=cropland_values,
                threshold=threshold,
                output_file=output_file,
            )
        )

    return outputs
