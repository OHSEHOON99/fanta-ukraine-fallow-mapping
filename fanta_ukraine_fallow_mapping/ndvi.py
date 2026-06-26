import os
import re
from pathlib import Path

import rasterio
from joblib import Parallel, delayed
from rasterio.merge import merge


DEFAULT_CRS = "EPSG:4326"


def extract_doy_from_band_name(band_name):
    match = re.search(r"Syn_VI_fitted(\d+)", band_name or "")
    return int(match.group(1)) if match else None


def extract_year_from_filename(filename):
    match = re.search(r"_(\d{4})(?:[.\-_]|$)", Path(filename).name)
    return int(match.group(1)) if match else None


def merge_tiff_files(tiff_files):
    if not tiff_files:
        raise ValueError("No TIFF files to merge.")

    datasets = []
    band_descriptions = None
    try:
        for tif_file in tiff_files:
            src = rasterio.open(tif_file)
            datasets.append(src)
            if band_descriptions is None:
                band_descriptions = src.descriptions

        mosaic, out_transform = merge(datasets)
        out_meta = datasets[0].meta.copy()
        out_meta.update({"transform": out_transform})
        return mosaic, out_meta, band_descriptions
    finally:
        for src in datasets:
            src.close()


def process_and_save_bands(mosaic, out_meta, band_descriptions, output_dir, year, region_name, crs=DEFAULT_CRS):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for band_idx in range(mosaic.shape[0]):
        band_description = band_descriptions[band_idx] if band_descriptions else None
        doy = extract_doy_from_band_name(band_description)
        if doy is None:
            print(f"Skipping band {band_idx + 1}: DOY could not be extracted from {band_description!r}.")
            continue

        band_data = mosaic[band_idx, :, :]
        output_file = output_dir / f"NDVI_{region_name}_{year}_{doy:03d}.tif"
        band_meta = out_meta.copy()
        band_meta.update(
            {
                "driver": "GTiff",
                "height": band_data.shape[0],
                "width": band_data.shape[1],
                "count": 1,
                "dtype": "int16",
                "crs": crs,
            }
        )

        with rasterio.open(output_file, "w", **band_meta) as dest:
            dest.write(band_data, 1)

        print(f"Saved {output_file}")


def process_ndvi_for_region(region_name, year, tiff_files, output_dir, crs=DEFAULT_CRS):
    print(f"Merging {len(tiff_files)} TIF files for {year} in region {region_name}.")
    mosaic, out_meta, band_descriptions = merge_tiff_files(tiff_files)
    out_meta.update({"crs": crs, "dtype": "int16"})
    process_and_save_bands(mosaic, out_meta, band_descriptions, output_dir, year, region_name, crs)
    print(f"Completed processing for {year} in region {region_name}.")


def discover_regions(base_input_dir):
    base_input_dir = Path(base_input_dir)
    return sorted(path.name for path in base_input_dir.iterdir() if path.is_dir())


def collect_tiffs_by_year(region_path):
    tiff_files_by_year = {}
    for filename in os.listdir(region_path):
        if not filename.lower().endswith((".tif", ".tiff")):
            continue
        year = extract_year_from_filename(filename)
        if year is None:
            continue
        tiff_files_by_year.setdefault(year, []).append(str(Path(region_path) / filename))
    return tiff_files_by_year


def process_region(base_input_dir, base_output_dir, region_name, crs=DEFAULT_CRS):
    region_path = Path(base_input_dir) / region_name
    if not region_path.is_dir():
        print(f"Skipping {region_name}: input directory does not exist.")
        return

    tiff_files_by_year = collect_tiffs_by_year(region_path)
    for year, tiff_files in sorted(tiff_files_by_year.items()):
        output_dir = Path(base_output_dir) / region_name / "preprocessed" / str(year)
        process_ndvi_for_region(region_name, year, tiff_files, output_dir, crs=crs)


def process_all_regions_for_ndvi(base_input_dir, base_output_dir, target_regions=None, n_jobs=5, crs=DEFAULT_CRS):
    if target_regions is None:
        target_regions = discover_regions(base_input_dir)

    Parallel(n_jobs=n_jobs)(
        delayed(process_region)(base_input_dir, base_output_dir, region, crs=crs)
        for region in target_regions
    )
