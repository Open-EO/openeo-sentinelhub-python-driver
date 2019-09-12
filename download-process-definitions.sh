#!/bin/bash
for file in $(find ./workers/process/ -type f -not -name "_*.py");
do
	full_filename=$(basename -- "$file")
	filename="${full_filename%.*}"
    wget -P ./rest/process_definitions/ https://raw.githubusercontent.com/Open-EO/openeo-processes/0.4.2/$filename.json --no-clobber
done