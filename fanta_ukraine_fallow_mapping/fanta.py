import os
import re
from glob import glob
from pathlib import Path

import numpy as np
import rasterio
import yaml
from joblib import Parallel, delayed
from rasterio.warp import Resampling, reproject
from tqdm import tqdm


CROPLAND_VALUE = 255


def extract_doy_from_filename(filename):
    match = re.search(r"_(\d{3})\.tif$", Path(filename).name)
    return int(match.group(1)) if match else None


def get_month_from_doy(doy):
    month_ends = [31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 366]
    for month, end_day in enumerate(month_ends, start=1):
        if doy <= end_day:
            return month
    raise ValueError(f"Invalid day-of-year value: {doy}")


def calculate_monthly_max_ndvi(ndvi_files, output_tif):
    if not ndvi_files:
        raise ValueError("At least one NDVI file is required.")

    monthly_ndvi = {month: [] for month in range(1, 13)}
    for ndvi_file in ndvi_files:
        doy = extract_doy_from_filename(ndvi_file)
        if doy is not None:
            monthly_ndvi[get_month_from_doy(doy)].append(ndvi_file)

    with rasterio.open(ndvi_files[0]) as src:
        profile = src.profile
        height, width = src.shape

    monthly_max_ndvi = []
    for month in range(1, 13):
        if monthly_ndvi[month]:
            max_ndvi = np.full((height, width), np.iinfo(np.int16).min, dtype=np.int16)
            for ndvi_file in monthly_ndvi[month]:
                with rasterio.open(ndvi_file) as src:
                    max_ndvi = np.maximum(max_ndvi, src.read(1).astype(np.int16))
            monthly_max_ndvi.append(max_ndvi)
        else:
            monthly_max_ndvi.append(np.zeros((height, width), dtype=np.int16))

    output_tif = Path(output_tif)
    output_tif.parent.mkdir(parents=True, exist_ok=True)
    profile.update(dtype=rasterio.int16, count=12)
    with rasterio.open(output_tif, "w", **profile) as dst:
        for i, max_ndvi in enumerate(monthly_max_ndvi, start=1):
            dst.write(max_ndvi, i)

    print(f"Monthly maximum NDVI saved to {output_tif}.")


def calculate_monthly_ndvi_range(ndvi_files, output_range_tif):
    if not ndvi_files:
        raise ValueError("At least one NDVI file is required.")

    monthly_ndvi = {month: [] for month in range(1, 13)}
    for ndvi_file in ndvi_files:
        doy = extract_doy_from_filename(ndvi_file)
        if doy is not None:
            monthly_ndvi[get_month_from_doy(doy)].append(ndvi_file)

    with rasterio.open(ndvi_files[0]) as src:
        profile = src.profile
        height, width = src.shape

    monthly_ranges = []
    for month in range(1, 13):
        if monthly_ndvi[month]:
            max_ndvi = np.full((height, width), np.iinfo(np.int16).min, dtype=np.int16)
            min_ndvi = np.full((height, width), np.iinfo(np.int16).max, dtype=np.int16)
            for ndvi_file in monthly_ndvi[month]:
                with rasterio.open(ndvi_file) as src:
                    ndvi = src.read(1).astype(np.int16)
                    max_ndvi = np.maximum(max_ndvi, ndvi)
                    min_ndvi = np.minimum(min_ndvi, ndvi)
            monthly_ranges.append(max_ndvi - min_ndvi)
        else:
            monthly_ranges.append(np.zeros((height, width), dtype=np.int16))

    output_range_tif = Path(output_range_tif)
    output_range_tif.parent.mkdir(parents=True, exist_ok=True)
    profile.update(dtype=rasterio.int16, count=12)
    with rasterio.open(output_range_tif, "w", **profile) as dst:
        for i, ndvi_range in enumerate(monthly_ranges, start=1):
            dst.write(ndvi_range, i)

    print(f"Monthly NDVI range saved to {output_range_tif}.")


def calculate_monthly_products_for_year(region, year, ndvi_path, output_max_tif, output_range_tif):
    ndvi_files = sorted(glob(os.path.join(ndvi_path, f"NDVI_*_{year}_*.tif")))
    if not ndvi_files:
        print(f"Skipping {region} {year}: no NDVI files found.")
        return
    calculate_monthly_max_ndvi(ndvi_files, output_max_tif)
    calculate_monthly_ndvi_range(ndvi_files, output_range_tif)


def calculate_monthly_products(base_preprocessed_path, start_year, end_year, regions=None, n_jobs=5):
    base_preprocessed_path = Path(base_preprocessed_path)
    if regions is None:
        regions = sorted(path.name for path in base_preprocessed_path.iterdir() if path.is_dir())

    tasks = []
    for region in regions:
        base_ndvi_path = base_preprocessed_path / region / "preprocessed"
        output_max_dir = base_preprocessed_path / region / "monthly_max"
        output_range_dir = base_preprocessed_path / region / "range"
        output_max_dir.mkdir(parents=True, exist_ok=True)
        output_range_dir.mkdir(parents=True, exist_ok=True)
        for year in range(start_year, end_year + 1):
            tasks.append(
                (
                    region,
                    year,
                    base_ndvi_path / str(year),
                    output_max_dir / f"Monthly_Max_NDVI_{year}.tif",
                    output_range_dir / f"Monthly_NDVI_Range_{year}.tif",
                )
            )

    Parallel(n_jobs=n_jobs)(
        delayed(calculate_monthly_products_for_year)(region, year, ndvi_path, output_max_tif, output_range_tif)
        for region, year, ndvi_path, output_max_tif, output_range_tif in tasks
    )


def calculate_pure_crop_mean_and_std(ndvi_files, output_mean_tif, output_std_tif, description):
    if not ndvi_files:
        print(f"Skipping {description}: no files available for mean/std calculation.")
        return

    with rasterio.open(ndvi_files[0]) as src:
        profile = src.profile
        height, width = src.shape
        profile.update(count=12, dtype=rasterio.float32)

    mean_data = np.zeros((12, height, width), dtype=np.float32)
    std_data = np.zeros((12, height, width), dtype=np.float32)

    for band in range(1, 13):
        band_values = []
        for ndvi_file in ndvi_files:
            with rasterio.open(ndvi_file) as src:
                band_values.append(src.read(band).astype(np.float32))

        band_values = np.array(band_values)
        median_value = np.median(band_values, axis=0)
        pure_crop_values = np.where(band_values >= median_value, band_values, np.nan)
        mean_data[band - 1] = np.nanmean(pure_crop_values, axis=0)
        std_data[band - 1] = np.nanstd(pure_crop_values, axis=0)

    Path(output_mean_tif).parent.mkdir(parents=True, exist_ok=True)
    Path(output_std_tif).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(output_mean_tif, "w", **profile) as dst_mean, rasterio.open(output_std_tif, "w", **profile) as dst_std:
        for band in range(1, 13):
            dst_mean.write(mean_data[band - 1].astype(np.float32), band)
            dst_std.write(std_data[band - 1].astype(np.float32), band)

    print(f"Pure-crop monthly mean {description} saved to {output_mean_tif}.")
    print(f"Pure-crop monthly std {description} saved to {output_std_tif}.")


def calculate_pure_crop_tandvi_and_tandvirange(
    ndvi_file,
    range_file,
    mean_ndvi_file,
    std_ndvi_file,
    mean_range_file,
    std_range_file,
    output_tandvi_tif,
    output_tandvirange_tif,
):
    with rasterio.open(ndvi_file) as src_ndvi, rasterio.open(range_file) as src_range, rasterio.open(mean_ndvi_file) as src_mean_ndvi, rasterio.open(std_ndvi_file) as src_std_ndvi, rasterio.open(mean_range_file) as src_mean_range, rasterio.open(std_range_file) as src_std_range:
        profile = src_ndvi.profile
        profile.update(count=12, dtype=rasterio.float32)

        Path(output_tandvi_tif).parent.mkdir(parents=True, exist_ok=True)
        Path(output_tandvirange_tif).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_tandvi_tif, "w", **profile) as dst_tandvi, rasterio.open(output_tandvirange_tif, "w", **profile) as dst_tandvirange:
            for band in range(1, 13):
                ndvi_month = src_ndvi.read(band).astype(np.float32)
                ndvi_range_month = src_range.read(band).astype(np.float32)
                mean_ndvi = src_mean_ndvi.read(band).astype(np.float32)
                std_ndvi = src_std_ndvi.read(band).astype(np.float32)
                mean_range = src_mean_range.read(band).astype(np.float32)
                std_range = src_std_range.read(band).astype(np.float32)

                epsilon = 1e-6
                dst_tandvi.write(((ndvi_month - mean_ndvi) / (std_ndvi + epsilon)).astype(np.float32), band)
                dst_tandvirange.write(((ndvi_range_month - mean_range) / (std_range + epsilon)).astype(np.float32), band)

    print(f"TANDVI saved to {output_tandvi_tif}.")
    print(f"TANDVI range saved to {output_tandvirange_tif}.")


def process_pure_crop_stats(pure_crop_start_year, pure_crop_end_year, region_dir):
    region_dir = Path(region_dir)
    output_mean_ndvi_tif = region_dir / f"Pure_Crop_Mean_NDVI_{pure_crop_start_year}_{pure_crop_end_year}.tif"
    output_std_ndvi_tif = region_dir / f"Pure_Crop_STD_NDVI_{pure_crop_start_year}_{pure_crop_end_year}.tif"
    output_mean_range_tif = region_dir / f"Pure_Crop_Mean_NDVI_Range_{pure_crop_start_year}_{pure_crop_end_year}.tif"
    output_std_range_tif = region_dir / f"Pure_Crop_STD_NDVI_Range_{pure_crop_start_year}_{pure_crop_end_year}.tif"

    ndvi_files = sorted(glob(str(region_dir / "monthly_max" / "*.tif")))
    range_files = sorted(glob(str(region_dir / "range" / "*.tif")))

    if not output_mean_ndvi_tif.exists() or not output_std_ndvi_tif.exists():
        calculate_pure_crop_mean_and_std(ndvi_files, output_mean_ndvi_tif, output_std_ndvi_tif, "NDVI")
    if not output_mean_range_tif.exists() or not output_std_range_tif.exists():
        calculate_pure_crop_mean_and_std(range_files, output_mean_range_tif, output_std_range_tif, "NDVI Range")

    return output_mean_ndvi_tif, output_std_ndvi_tif, output_mean_range_tif, output_std_range_tif


def calculate_tandvi_for_year(year, region_dir, mean_ndvi_tif, std_ndvi_tif, mean_range_tif, std_range_tif):
    region_dir = Path(region_dir)
    ndvi_month_file = region_dir / "monthly_max" / f"Monthly_Max_NDVI_{year}.tif"
    range_month_file = region_dir / "range" / f"Monthly_NDVI_Range_{year}.tif"
    output_tandvi_tif = region_dir / "tandvi" / f"TANDVI_{year}.tif"
    output_tandvirange_tif = region_dir / "tandvirange" / f"TANDVIrange_{year}.tif"

    if ndvi_month_file.exists() and range_month_file.exists():
        calculate_pure_crop_tandvi_and_tandvirange(
            ndvi_month_file,
            range_month_file,
            mean_ndvi_tif,
            std_ndvi_tif,
            mean_range_tif,
            std_range_tif,
            output_tandvi_tif,
            output_tandvirange_tif,
        )
    else:
        print(f"Skipping {region_dir.name} {year}: monthly NDVI or NDVI range file is missing.")


def calculate_tandvi_products(base_preprocessed_path, pure_crop_start_year, pure_crop_end_year, tandvi_start_year, tandvi_end_year, regions=None, n_jobs=-1):
    base_preprocessed_path = Path(base_preprocessed_path)
    if regions is None:
        regions = sorted(path.name for path in base_preprocessed_path.iterdir() if path.is_dir())

    for region in regions:
        region_dir = base_preprocessed_path / region
        if not (region_dir / "preprocessed").is_dir():
            print(f"Skipping {region}: preprocessed directory does not exist.")
            continue
        print(f"Processing TANDVI products for {region}.")
        stats = process_pure_crop_stats(pure_crop_start_year, pure_crop_end_year, region_dir)
        years = range(tandvi_start_year, tandvi_end_year + 1)
        Parallel(n_jobs=n_jobs)(delayed(calculate_tandvi_for_year)(year, region_dir, *stats) for year in years)


def resample_cropmaps(ndvi_base_dir, cropmap_base_dir, output_base_dir, reference_year=2023, reference_doy=361):
    ndvi_base_dir = Path(ndvi_base_dir)
    cropmap_base_dir = Path(cropmap_base_dir)
    output_base_dir = Path(output_base_dir)
    output_base_dir.mkdir(parents=True, exist_ok=True)

    region_names = sorted(path.name for path in ndvi_base_dir.iterdir() if path.is_dir())
    for region in region_names:
        ndvi_path = ndvi_base_dir / region / "preprocessed" / str(reference_year) / f"NDVI_{region}_{reference_year}_{reference_doy:03d}.tif"
        cropmap_path = cropmap_base_dir / f"cropmap_{region}.tif"
        output_path = output_base_dir / f"resampled_cropmap_{region}.tif"

        if not ndvi_path.exists() or not cropmap_path.exists():
            print(f"Skipping {region}: reference NDVI or cropmap file is missing.")
            continue

        with rasterio.open(ndvi_path) as ref_src, rasterio.open(cropmap_path) as crop_src:
            out_meta = ref_src.meta.copy()
            out_meta.update({"count": crop_src.count, "dtype": crop_src.dtypes[0], "nodata": crop_src.nodata})
            with rasterio.open(output_path, "w", **out_meta) as dst:
                for i in range(1, crop_src.count + 1):
                    reproject(
                        source=rasterio.band(crop_src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=crop_src.transform,
                        src_crs=crop_src.crs,
                        dst_transform=ref_src.transform,
                        dst_crs=ref_src.crs,
                        resampling=Resampling.nearest,
                    )
        print(f"Resampled cropmap created for {region}: {output_path}")


def get_cropland_mask(cropmap_file, cropland_value=CROPLAND_VALUE):
    with rasterio.open(cropmap_file) as src:
        return src.read(1) == cropland_value


def calculate_median_cd(ndvi_files, cropland_mask, output_median_cd_yaml, data_type="NDVI"):
    median_cd_values = {}
    for month in range(1, 13):
        monthly_values = []
        for ndvi_file in tqdm(ndvi_files, desc=f"{data_type} - month {month}", leave=False):
            with rasterio.open(ndvi_file) as src_ndvi:
                if month > src_ndvi.count:
                    continue
                data_cropped = src_ndvi.read(month)[cropland_mask]
                if data_cropped.size > 0:
                    monthly_values.extend(data_cropped)
        median_cd_values[f"Month_{month}"] = float(np.median(monthly_values)) if monthly_values else None

    output_median_cd_yaml = Path(output_median_cd_yaml)
    output_median_cd_yaml.parent.mkdir(parents=True, exist_ok=True)
    with output_median_cd_yaml.open("w") as yaml_file:
        yaml.safe_dump(median_cd_values, yaml_file, sort_keys=True)

    print(f"{data_type} MedianCD saved to {output_median_cd_yaml}.")


def calculate_median_cd_for_region(region_name, ndvi_dir, ndvi_range_dir, cropmap_base_path, output_dir):
    cropmap_file = Path(cropmap_base_path) / f"resampled_cropmap_{region_name}.tif"
    if not cropmap_file.exists():
        print(f"Skipping {region_name}: cropmap file not found.")
        return

    cropland_mask = get_cropland_mask(cropmap_file)
    output_dir = Path(output_dir)
    ndvi_files = sorted(glob(str(Path(ndvi_dir) / "Monthly_Max_NDVI_20[1-2][0-9].tif")))
    range_files = sorted(glob(str(Path(ndvi_range_dir) / "Monthly_NDVI_Range_20[1-2][0-9].tif")))

    calculate_median_cd(ndvi_files, cropland_mask, output_dir / "MedianCD_Monthly.yaml", data_type="NDVI")
    calculate_median_cd(range_files, cropland_mask, output_dir / "MedianCD_Range_Monthly.yaml", data_type="NDVI Range")


def calculate_median_cd_for_all_regions(base_dir, cropmap_base_path=None, n_jobs=-1):
    base_dir = Path(base_dir)
    cropmap_base_path = Path(cropmap_base_path) if cropmap_base_path else base_dir / "cropmap"
    preprocessed_base_dir = base_dir / "preprocessed"
    region_names = sorted(path.name for path in preprocessed_base_dir.iterdir() if path.is_dir())

    Parallel(n_jobs=n_jobs)(
        delayed(calculate_median_cd_for_region)(
            region,
            preprocessed_base_dir / region / "monthly_max",
            preprocessed_base_dir / region / "range",
            cropmap_base_path,
            preprocessed_base_dir / region,
        )
        for region in tqdm(region_names, desc="Processing regions")
    )


def calculate_fallow_tandvi(tandvi_dir, year, output_fallow_tif):
    tandvi_file = Path(tandvi_dir) / f"TANDVI_{year}.tif"
    if not tandvi_file.exists():
        print(f"{tandvi_file} does not exist. Skipping.")
        return

    with rasterio.open(tandvi_file) as src:
        profile = src.profile
        height, width = src.shape
        profile.update(count=1, dtype=rasterio.uint8)
        tandvi_april = src.read(4).astype(np.float32)
        tandvi_may = src.read(5).astype(np.float32)
        tandvi_june = src.read(6).astype(np.float32)
        tandvi_july = src.read(7).astype(np.float32)
        fallow = np.zeros((height, width), dtype=np.uint8)
        condition1 = (tandvi_may < -3) & (tandvi_june < -3) & (tandvi_july < -3)
        condition2 = (tandvi_april < -3) & (tandvi_may < -3) & (tandvi_june < -3)
        fallow[condition1 | condition2] = 255

        Path(output_fallow_tif).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_fallow_tif, "w", **profile) as dst:
            dst.write(fallow, 1)


def calculate_fallow_tandvirange(tandvirange_dir, year, output_fallow_tif):
    tandvirange_file = Path(tandvirange_dir) / f"TANDVIrange_{year}.tif"
    if not tandvirange_file.exists():
        print(f"{tandvirange_file} does not exist. Skipping.")
        return

    with rasterio.open(tandvirange_file) as src:
        profile = src.profile
        height, width = src.shape
        profile.update(count=1, dtype=rasterio.uint8)
        april = src.read(4).astype(np.float32)
        may = src.read(5).astype(np.float32)
        june = src.read(6).astype(np.float32)
        july = src.read(7).astype(np.float32)
        fallow = np.zeros((height, width), dtype=np.uint8)
        fallow[((may < -3) & (june < -3) & (july < -3)) | ((april < -3) & (may < -3) & (june < -3))] = 255

        Path(output_fallow_tif).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_fallow_tif, "w", **profile) as dst:
            dst.write(fallow, 1)


def _load_median_cd_max(median_cd_file):
    if not Path(median_cd_file).exists():
        raise FileNotFoundError(f"MedianCD file not found: {median_cd_file}")
    with open(median_cd_file, "r") as yaml_file:
        median_cd_values = yaml.safe_load(yaml_file)
    values = [median_cd_values.get(f"Month_{month}") or 0 for month in [4, 5, 6, 7]]
    return max(values)


def calculate_fallow_ndvi(ndvi_dir, median_cd_file, year, output_fallow_tif):
    ndvi_file = Path(ndvi_dir) / f"Monthly_Max_NDVI_{year}.tif"
    if not ndvi_file.exists():
        print(f"{ndvi_file} does not exist. Skipping.")
        return

    median_cd_max = _load_median_cd_max(median_cd_file)
    with rasterio.open(ndvi_file) as src:
        profile = src.profile
        height, width = src.shape
        profile.update(count=1, dtype=rasterio.uint8)
        ndvi_max = np.maximum(np.maximum(src.read(4).astype(np.float32), src.read(5).astype(np.float32)), np.maximum(src.read(6).astype(np.float32), src.read(7).astype(np.float32)))
        fallow = np.zeros((height, width), dtype=np.uint8)
        fallow[ndvi_max < 0.8 * median_cd_max] = 255

        Path(output_fallow_tif).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_fallow_tif, "w", **profile) as dst:
            dst.write(fallow, 1)


def calculate_fallow_ndvi_range(ndvi_range_dir, median_cd_file, year, output_fallow_tif):
    ndvi_range_file = Path(ndvi_range_dir) / f"Monthly_NDVI_Range_{year}.tif"
    if not ndvi_range_file.exists():
        print(f"{ndvi_range_file} does not exist. Skipping.")
        return

    median_cd_max = _load_median_cd_max(median_cd_file)
    with rasterio.open(ndvi_range_file) as src:
        profile = src.profile
        height, width = src.shape
        profile.update(count=1, dtype=rasterio.uint8)
        ndvi_range_max = np.maximum(np.maximum(src.read(4).astype(np.float32), src.read(5).astype(np.float32)), np.maximum(src.read(6).astype(np.float32), src.read(7).astype(np.float32)))
        fallow = np.zeros((height, width), dtype=np.uint8)
        fallow[ndvi_range_max < 0.8 * median_cd_max] = 255

        Path(output_fallow_tif).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_fallow_tif, "w", **profile) as dst:
            dst.write(fallow, 1)


def calculate_final_fallow_mask(q1_dir, q2_dir, q3_dir, q4_dir, year, output_fallow_tif, non_fallow_value=1):
    q1_file = Path(q1_dir) / f"FALLOW_q1_{year}.tif"
    q2_file = Path(q2_dir) / f"FALLOW_q2_{year}.tif"
    q3_file = Path(q3_dir) / f"FALLOW_q3_{year}.tif"
    q4_file = Path(q4_dir) / f"FALLOW_q4_{year}.tif"
    missing_files = [str(path) for path in [q1_file, q2_file, q3_file, q4_file] if not path.exists()]
    if missing_files:
        print(f"Skipping final FALLOW {year}: missing component masks: {missing_files}")
        return

    with rasterio.open(q1_file) as src_q1, rasterio.open(q2_file) as src_q2, rasterio.open(q3_file) as src_q3, rasterio.open(q4_file) as src_q4:
        profile = src_q1.profile
        profile.update(count=1, dtype=rasterio.uint8)
        true_count = (
            (src_q1.read(1) == 255).astype(np.uint8)
            + (src_q2.read(1) == 255).astype(np.uint8)
            + (src_q3.read(1) == 255).astype(np.uint8)
            + (src_q4.read(1) == 255).astype(np.uint8)
        )
        final_fallow = np.zeros_like(true_count, dtype=np.uint8)
        final_fallow[true_count >= 2] = 255
        final_fallow[true_count < 2] = non_fallow_value

        Path(output_fallow_tif).parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(output_fallow_tif, "w", **profile) as dst:
            dst.write(final_fallow, 1)


def calculate_fallow_for_year(region_name, tandvi_dir, tandvirange_dir, ndvi_dir, ndvi_range_dir, median_cd_file, median_cd_range_file, output_fallow_dir, year):
    output_fallow_dir = Path(output_fallow_dir)
    output_q1 = output_fallow_dir / f"FALLOW_q1_{year}.tif"
    output_q2 = output_fallow_dir / f"FALLOW_q2_{year}.tif"
    output_q3 = output_fallow_dir / f"FALLOW_q3_{year}.tif"
    output_q4 = output_fallow_dir / f"FALLOW_q4_{year}.tif"
    output_final = output_fallow_dir / f"Final_FALLOW_{year}.tif"

    try:
        calculate_fallow_tandvi(tandvi_dir, year, output_q1)
        calculate_fallow_tandvirange(tandvirange_dir, year, output_q2)
        calculate_fallow_ndvi(ndvi_dir, median_cd_file, year, output_q3)
        calculate_fallow_ndvi_range(ndvi_range_dir, median_cd_range_file, year, output_q4)
    except FileNotFoundError as exc:
        print(f"Skipping FANTA fallow outputs for {region_name} {year}: {exc}")
        return
    calculate_final_fallow_mask(output_fallow_dir, output_fallow_dir, output_fallow_dir, output_fallow_dir, year, output_final)
    print(f"FANTA fallow outputs saved for {region_name} {year}.")


def calculate_fallow_for_region(region_name, base_dir, start_year=2020, end_year=2023, n_jobs=-1):
    region_dir = Path(base_dir) / "preprocessed" / region_name
    output_fallow_dir = region_dir / "fanta"
    output_fallow_dir.mkdir(parents=True, exist_ok=True)

    Parallel(n_jobs=n_jobs)(
        delayed(calculate_fallow_for_year)(
            region_name,
            region_dir / "tandvi",
            region_dir / "tandvirange",
            region_dir / "monthly_max",
            region_dir / "range",
            region_dir / "MedianCD_Monthly.yaml",
            region_dir / "MedianCD_Range_Monthly.yaml",
            output_fallow_dir,
            year,
        )
        for year in tqdm(range(start_year, end_year + 1), desc=f"Processing years for {region_name}")
    )


def calculate_fallow_for_all_regions(base_dir, start_year=2020, end_year=2023, regions=None, n_jobs=-1):
    preprocessed_base_dir = Path(base_dir) / "preprocessed"
    if regions is None:
        regions = sorted(path.name for path in preprocessed_base_dir.iterdir() if path.is_dir())
    for region_name in tqdm(regions, desc="Processing regions"):
        calculate_fallow_for_region(region_name, base_dir, start_year=start_year, end_year=end_year, n_jobs=n_jobs)
