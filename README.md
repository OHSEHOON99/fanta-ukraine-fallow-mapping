# FANTA-Based Ukraine Fallow Land Mapping

This repository contains a Python implementation of the Fallow-land Algorithm based on Neighborhood and Temporal Anomalies (FANTA) for mapping fallow croplands in Ukraine from NDVI and cropmap raster products.

The implementation is adapted from:

Wallace, C. S., Thenkabail, P., Rodriguez, J. R., & Brown, M. K. (2017). Fallow-land Algorithm based on Neighborhood and Temporal Anomalies (FANTA) to map planted versus fallowed croplands using MODIS data to assist in drought studies leading to water and food security assessments. GIScience & Remote Sensing, 54(2), 258-282. https://doi.org/10.1080/15481603.2017.1290913

## Repository Structure

- `fanta_ukraine_fallow_mapping/`: reusable Python modules for NDVI preprocessing, cropmap preparation, and FANTA fallow detection
- `scripts/`: command-line entry points for running each workflow stage
- `configs/`: example path and year settings
- `DATA_POLICY.md`: data and artifact scope for public use

Large raster inputs and generated GeoTIFF outputs are kept outside git.

## Workflow

The processing sequence is:

```text
source NDVI rasters
  -> regional NDVI bands
  -> monthly max NDVI and monthly NDVI range
  -> pure-crop statistics and TANDVI products
  -> MedianCD statistics
  -> Q1-Q4 FANTA masks
  -> final fallow mask
```

Cropmap rasters are processed in parallel with the NDVI workflow:

```text
source annual cropmaps
  -> Ukraine masked cropmaps
  -> regional binary cropland maps
  -> resampled cropmaps aligned to NDVI
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Example Commands

Preprocess NDVI files by region:

```bash
python scripts/process_ndvi.py \
  --input-dir data/raw/ndvi \
  --output-dir outputs/preprocessed \
  --jobs 5
```

Create Ukraine-level masked cropmaps:

```bash
python scripts/process_cropmap.py mask-ukraine \
  --cropmap-dir data/raw/cropmap \
  --boundary data/external/Ukraine_Polygon_GAUL2015.geojson \
  --output-dir outputs/cropmap/Ukraine \
  --start-year 2013 \
  --end-year 2023
```

Create region-level binary cropland maps:

```bash
python scripts/process_cropmap.py regions \
  --boundary data/external/Ukraine_Polygon_GAUL2015.geojson \
  --masked-cropmap-dir outputs/cropmap/Ukraine \
  --output-dir outputs/cropmap \
  --years 2013 2014 2015 2016 2017 2018 2019 \
  --threshold 5
```

Run the FANTA stages:

```bash
python scripts/run_fanta.py monthly \
  --preprocessed-dir outputs/preprocessed \
  --start-year 2013 \
  --end-year 2023

python scripts/run_fanta.py tandvi \
  --preprocessed-dir outputs/preprocessed \
  --pure-crop-start-year 2013 \
  --pure-crop-end-year 2019 \
  --start-year 2020 \
  --end-year 2023

python scripts/run_fanta.py resample-cropmaps \
  --ndvi-dir outputs/preprocessed \
  --cropmap-dir outputs/cropmap \
  --output-dir outputs/cropmap

python scripts/run_fanta.py median-cd \
  --base-dir outputs

python scripts/run_fanta.py fallow \
  --base-dir outputs \
  --start-year 2020 \
  --end-year 2023
```

## Outputs

Generated files are written to `outputs/` by convention. The main final products are:

- `FALLOW_q1_YEAR.tif`: TANDVI-based fallow mask
- `FALLOW_q2_YEAR.tif`: TANDVI range-based fallow mask
- `FALLOW_q3_YEAR.tif`: NDVI MedianCD-based fallow mask
- `FALLOW_q4_YEAR.tif`: NDVI range MedianCD-based fallow mask
- `Final_FALLOW_YEAR.tif`: final FANTA fallow mask
