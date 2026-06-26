#!/usr/bin/env python
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fanta_ukraine_fallow_mapping.cropmap import create_ukraine_cropmaps, generate_cropmaps_by_region


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare cropmap rasters for the FANTA workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ukraine = subparsers.add_parser("mask-ukraine", help="Merge annual cropmap tiles and mask them to Ukraine.")
    ukraine.add_argument("--cropmap-dir", required=True, help="Directory containing source annual cropmap TIFF files.")
    ukraine.add_argument("--boundary", required=True, help="Ukraine boundary GeoJSON or vector file.")
    ukraine.add_argument("--output-dir", required=True, help="Directory for masked annual cropmap TIFF files.")
    ukraine.add_argument("--start-year", type=int, default=2013)
    ukraine.add_argument("--end-year", type=int, default=2023)
    ukraine.add_argument("--first-band-year", type=int, default=2000)

    regions = subparsers.add_parser("regions", help="Create region-level binary cropland maps.")
    regions.add_argument("--boundary", required=True, help="Region boundary GeoJSON or vector file.")
    regions.add_argument("--masked-cropmap-dir", required=True, help="Directory containing masked_cropmap_YEAR.tif files.")
    regions.add_argument("--output-dir", required=True, help="Directory for region cropmap outputs.")
    regions.add_argument("--years", type=int, nargs="+", default=list(range(2013, 2020)))
    regions.add_argument("--cropland-values", type=int, nargs="+", default=[10, 11, 12, 20])
    regions.add_argument("--threshold", type=int, default=5)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.command == "mask-ukraine":
        create_ukraine_cropmaps(
            cropmap_dir=args.cropmap_dir,
            boundary_file=args.boundary,
            output_dir=args.output_dir,
            start_year=args.start_year,
            end_year=args.end_year,
            first_band_year=args.first_band_year,
        )
    elif args.command == "regions":
        file_paths = [str(Path(args.masked_cropmap_dir) / f"masked_cropmap_{year}.tif") for year in args.years]
        generate_cropmaps_by_region(
            geojson_file=args.boundary,
            file_paths=file_paths,
            output_base_dir=args.output_dir,
            cropland_values=args.cropland_values,
            threshold=args.threshold,
        )


if __name__ == "__main__":
    main()
