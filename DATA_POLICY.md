# Data and Artifact Scope

This repository is structured as public research code. It contains reusable Python modules and command-line scripts, but not large raster inputs or generated GeoTIFF outputs.

## Expected Local Inputs

Place source data under a local `data/` workspace, for example:

```text
data/raw/ndvi/
data/raw/cropmap/
data/external/Ukraine_Polygon_GAUL2015.geojson
```

Typical external inputs include:

- NDVI GeoTIFF products with year and day-of-year metadata
- annual cropmap GeoTIFF products
- Ukraine administrative boundary vectors

Use the original data providers' citation, license, and redistribution terms when reproducing the workflow.

## Generated Artifacts

Generated rasters, YAML statistics, and intermediate products should be written to `outputs/` locally:

```text
outputs/preprocessed/
outputs/cropmap/
outputs/preprocessed/<REGION>/monthly_max/
outputs/preprocessed/<REGION>/range/
outputs/preprocessed/<REGION>/tandvi/
outputs/preprocessed/<REGION>/tandvirange/
outputs/preprocessed/<REGION>/fanta/
```

These generated artifacts are intentionally not committed because they are large and reproducible from the input data and scripts.
