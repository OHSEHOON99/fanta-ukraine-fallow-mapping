#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fanta_ukraine_fallow_mapping.fanta import (
    calculate_fallow_for_all_regions,
    calculate_median_cd_for_all_regions,
    calculate_monthly_products,
    calculate_tandvi_products,
    resample_cropmaps,
)


def parse_regions(value):
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_args():
    parser = argparse.ArgumentParser(description="Run FANTA fallow-land mapping steps.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    monthly = subparsers.add_parser("monthly", help="Calculate monthly max NDVI and monthly NDVI range rasters.")
    monthly.add_argument("--preprocessed-dir", required=True, help="Base preprocessed NDVI directory.")
    monthly.add_argument("--start-year", type=int, default=2013)
    monthly.add_argument("--end-year", type=int, default=2023)
    monthly.add_argument("--regions", default=None, help="Comma-separated region names. Defaults to all regions.")
    monthly.add_argument("--jobs", type=int, default=5)

    tandvi = subparsers.add_parser("tandvi", help="Calculate pure-crop statistics, TANDVI, and TANDVI range.")
    tandvi.add_argument("--preprocessed-dir", required=True, help="Base preprocessed NDVI directory.")
    tandvi.add_argument("--pure-crop-start-year", type=int, default=2013)
    tandvi.add_argument("--pure-crop-end-year", type=int, default=2019)
    tandvi.add_argument("--start-year", type=int, default=2020)
    tandvi.add_argument("--end-year", type=int, default=2023)
    tandvi.add_argument("--regions", default=None, help="Comma-separated region names. Defaults to all regions.")
    tandvi.add_argument("--jobs", type=int, default=-1)

    resample = subparsers.add_parser("resample-cropmaps", help="Resample region cropmaps to the NDVI grid.")
    resample.add_argument("--ndvi-dir", required=True, help="Base preprocessed NDVI directory.")
    resample.add_argument("--cropmap-dir", required=True, help="Directory containing cropmap_REGION.tif files.")
    resample.add_argument("--output-dir", required=True, help="Directory for resampled cropmaps.")
    resample.add_argument("--reference-year", type=int, default=2023)
    resample.add_argument("--reference-doy", type=int, default=361)

    median = subparsers.add_parser("median-cd", help="Calculate MedianCD YAML files for NDVI and NDVI range.")
    median.add_argument("--base-dir", required=True, help="Workspace base directory containing preprocessed/ and cropmap/.")
    median.add_argument("--cropmap-dir", default=None, help="Optional directory containing resampled cropmaps.")
    median.add_argument("--jobs", type=int, default=-1)

    fallow = subparsers.add_parser("fallow", help="Calculate Q1-Q4 and final FANTA fallow masks.")
    fallow.add_argument("--base-dir", required=True, help="Workspace base directory containing preprocessed/.")
    fallow.add_argument("--start-year", type=int, default=2020)
    fallow.add_argument("--end-year", type=int, default=2023)
    fallow.add_argument("--regions", default=None, help="Comma-separated region names. Defaults to all regions.")
    fallow.add_argument("--jobs", type=int, default=-1)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "monthly":
        calculate_monthly_products(args.preprocessed_dir, args.start_year, args.end_year, regions=parse_regions(args.regions), n_jobs=args.jobs)
    elif args.command == "tandvi":
        calculate_tandvi_products(
            args.preprocessed_dir,
            args.pure_crop_start_year,
            args.pure_crop_end_year,
            args.start_year,
            args.end_year,
            regions=parse_regions(args.regions),
            n_jobs=args.jobs,
        )
    elif args.command == "resample-cropmaps":
        resample_cropmaps(args.ndvi_dir, args.cropmap_dir, args.output_dir, reference_year=args.reference_year, reference_doy=args.reference_doy)
    elif args.command == "median-cd":
        calculate_median_cd_for_all_regions(args.base_dir, cropmap_base_path=args.cropmap_dir, n_jobs=args.jobs)
    elif args.command == "fallow":
        calculate_fallow_for_all_regions(args.base_dir, start_year=args.start_year, end_year=args.end_year, regions=parse_regions(args.regions), n_jobs=args.jobs)


if __name__ == "__main__":
    main()
