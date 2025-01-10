# FANTA-based Ukraine Fallow Land Mapping

This repository contains the implementation of **Fallow-land Algorithm based on Neighborhood and Temporal Anomalies (FANTA)** for mapping fallow lands in **Ukraine** using satellite imagery data.

## Overview

The FANTA algorithm was developed by **Wallace et al. (2017)** to distinguish between planted and fallowed croplands using temporal and spatial anomalies in vegetation indices. This implementation adapts the FANTA approach for high-resolution NDVI data in Ukraine, focusing on detecting fallow lands during 2020–2023.

## Features
- **Q1 & Q2:** TANDVI and TANDVIrange-based fallow detection.
- **Q3 & Q4:** NDVI and NDVI Range-based fallow detection.
- **Final Output:** Aggregation of multiple fallow detection criteria to produce a final fallow land map.

## Data Sources
- **Satellite Imagery:** High-resolution NDVI data for Ukraine (2013–2023).
- **Boundary Data:** Administrative boundaries for Ukraine from FAO GAUL dataset.

## Reference
Wallace, C. S., Thenkabail, P., Rodriguez, J. R., & Brown, M. K. (2017).  
Fallow-land Algorithm based on Neighborhood and Temporal Anomalies (FANTA)  
to map planted versus fallowed croplands using MODIS data to assist in  
drought studies leading to water and food security assessments.  
GIScience & Remote Sensing, 54(2), 258-282.  
[https://doi.org/10.1080/15481603.2017.1290913](https://doi.org/10.1080/15481603.2017.1290913)
