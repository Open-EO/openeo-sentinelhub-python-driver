#!/bin/bash

rm -rf ./openeo-processes
git clone --depth 1 -c advice.detachedHead=false --branch 1.2.0  https://github.com/Open-EO/openeo-processes.git ./openeo-processes
cp ./openeo-processes/*.json ./rest/process_definitions/
cp ./openeo-processes/proposals/*.json ./rest/process_definitions/
rm -rf ./openeo-processes
