#!/bin/bash
set -o allexport
[[ -f .env ]] && source .env
set +o allexport

set -e
set -x

mkdir -p workers/tests/fixtures/

# S2L1C:
curl -s "https://services.sentinel-hub.com/ogc/wfs/${SENTINELHUB_INSTANCE_ID}?SERVICE=wfs&REQUEST=GetFeature&TYPENAMES=S2.TILE&BBOX=42.06347%2C12.32271%2C42.07112%2C12.33572&OUTPUTFORMAT=application%2Fjson&SRSNAME=EPSG%3A4326&TIME=2019-08-16T00%3A00%3A00%2F2019-08-18T23%3A59%3A59&MAXCC=100.0&MAXFEATURES=100&FEATURE_OFFSET=0" > tests/fixtures/response_load_collection_s2l1c.json
curl -s "https://services.sentinel-hub.com/ogc/wcs/${SENTINELHUB_INSTANCE_ID}?SERVICE=wcs&MAXCC=100.0&ShowLogo=False&Transparent=True&EvalScript=cmV0dXJuIFtCMDEsIEIwMiwgQjAzLCBCMDQsIEIwNSwgQjA2LCBCMDcsIEIwOCwgQjhBLCBCMDksIEIxMCwgQjExLCBCMTJdOw%3D%3D&BBOX=42.06347%2C12.32271%2C42.07112%2C12.33572&FORMAT=image%2Ftiff%3Bdepth%3D32f&CRS=EPSG%3A4326&TIME=2019-08-17T10%3A19%3A14%2F2019-08-17T10%3A19%3A14&RESX=10m&RESY=10m&COVERAGE=${SENTINELHUB_LAYER_ID_S2L1C}&REQUEST=GetCoverage&VERSION=1.1.2" > tests/fixtures/response_load_collection_s2l1c.tiff

# S1GRD:
curl -s "https://services.sentinel-hub.com/ogc/wfs/${SENTINELHUB_INSTANCE_ID}?SERVICE=wfs&REQUEST=GetFeature&TYPENAMES=DSS3&BBOX=42.06347%2C12.32271%2C42.07112%2C12.33572&OUTPUTFORMAT=application%2Fjson&SRSNAME=EPSG%3A4326&TIME=2019-08-16T00%3A00%3A00%2F2019-08-17T05%3A19%3A11&MAXCC=100.0&MAXFEATURES=100&FEATURE_OFFSET=0" > tests/fixtures/response_load_collection_s1grdiw.json
curl -s "https://services.sentinel-hub.com/ogc/wcs/${SENTINELHUB_INSTANCE_ID}?SERVICE=wcs&MAXCC=100.0&ShowLogo=False&Transparent=True&EvalScript=cmV0dXJuIFtWViwgVkhdOw%3D%3D&BBOX=42.06347%2C12.32271%2C42.07112%2C12.33572&FORMAT=image%2Ftiff%3Bdepth%3D32f&CRS=EPSG%3A4326&TIME=2019-08-17T05%3A19%3A10%2F2019-08-17T05%3A19%3A10&RESX=10m&RESY=10m&COVERAGE=S1GRD&REQUEST=GetCoverage&VERSION=1.1.2" > tests/fixtures/response_load_collection_s1grdiw.tiff
