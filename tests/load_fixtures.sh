#!/bin/bash
set -e
mkdir -p fixtures/
curl -s 'https://services.sentinel-hub.com/ogc/wms/cd280189-7c51-45a6-ab05-f96a76067710?service=WMS&request=GetMap&layers=1_TRUE_COLOR&styles=&format=image%2Fpng&transparent=true&version=1.1.1&showlogo=false&name=Sentinel-2%20L1C&width=32&height=32&preview=3&pane=activeLayer&maxcc=100&evalscriptoverrides=&time=2017-01-01%2F2017-02-01&srs=EPSG%3A4326&bbox=16.1,47.2,16.7,48.6' > fixtures/s2l1c_truecolor_32x32.png
