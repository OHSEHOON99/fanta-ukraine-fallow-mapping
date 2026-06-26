#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fanta_ukraine_fallow_mapping.ndvi import process_all_regions_for_ndvi


def parse_args():
    parser = argparse.ArgumentParser(description="Preprocess NDVI GeoTIFF files by region and year.")
    parser.add_argument("--input-dir", required=True, help="Directory containing one subdirectory per region with source NDVI TIFF files.")
    parser.add_argument("--output-dir", required=True, help="Directory where preprocessed NDVI bands will be written.")
    parser.add_argument("--regions", nargs="*", default=None, help="Optional region names. Defaults to all input subdirectories.")
    parser.add_argument("--jobs", type=int, default=5, help="Number of parallel jobs.")
    parser.add_argument("--crs", default="EPSG:4326", help="Output coordinate reference system.")
    return parser.parse_args()


def main():
    args = parse_args()
    process_all_regions_for_ndvi(args.input_dir, args.output_dir, target_regions=args.regions, n_jobs=args.jobs, crs=args.crs)


if __name__ == "__main__":
    main()
