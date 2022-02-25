#!/bin/bash

rm -rf ./openeo-processes
git clone https://github.com/Open-EO/openeo-processes.git ./openeo-processes
cp ./openeo-processes/*.json ./rest/process_definitions/
rm -rf ./openeo-processes
