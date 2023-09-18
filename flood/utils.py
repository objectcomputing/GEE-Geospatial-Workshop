import ee
import folium

import rasterio
import numpy as np
import pandas as pd
from google.cloud import storage
import io
import logging
from tqdm.notebook import tqdm
from shapely.geometry import Polygon



# Define a method for displaying Earth Engine image tiles to folium map.
def add_ee_layer(self, ee_image_object, vis_params, name):
    map_id_dict = ee.Image(ee_image_object).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict['tile_fetcher'].url_format,
        attr="Map Data © OCI | Google Earth Engine",
        name=name,
        overlay=True,
        control=True
    ).add_to(self)
    


logging.basicConfig(level=logging.INFO)

def raster_to_tabular(bucket_name, file_name, band_names):
    logging.info("Starting raster to tabular conversion...")
    
    if not band_names or not isinstance(band_names, list):
        raise ValueError("Band names must be provided as a list.")

    logging.info("Connecting to Google Cloud Storage...")
    client = storage.Client()
    bucket = client.get_bucket(bucket_name)
    blob = bucket.blob(file_name)
    blob_content = blob.download_as_bytes()

    logging.info("Reading raster into memory...")
    virtual_file = io.BytesIO(blob_content)

    with rasterio.open(virtual_file) as src:
        array = src.read()
        transform = src.transform

    logging.info("Calculating x and y coordinates...")
    x, y = np.meshgrid(
        np.arange(array.shape[2]) * transform[0] + transform[2],
        np.arange(array.shape[1]) * transform[4] + transform[5]
    )

    logging.info("Calculating corners of each pixel...")
    x1 = x
    y1 = y
    x2 = x1 + transform[0]
    y2 = y1 + transform[4]

    logging.info("Flattening and transposing arrays...")
    flattened_arrays = [band.flatten() for band in array]
    transposed_arrays = np.transpose(flattened_arrays)

    logging.info("Calculating centroids and creating polygons...")
    centroid_x, centroid_y = (x1 + x2) / 2, (y1 + y2) / 2
    polygons = [Polygon([(xi1, yi1), (xi2, yi1), (xi2, yi2), (xi1, yi2)]) for xi1, yi1, xi2, yi2 in tqdm(zip(x1.flatten(), y1.flatten(), x2.flatten(), y2.flatten()), total=x1.size, desc="Creating polygons")]
    
    logging.info("Converting to DataFrame...")
    df = pd.DataFrame(transposed_arrays, columns=band_names)
    df['x'], df['y'], df['geometry'] = centroid_x.flatten(), centroid_y.flatten(), polygons

    logging.info("Completed raster to tabular conversion.")
    return df
