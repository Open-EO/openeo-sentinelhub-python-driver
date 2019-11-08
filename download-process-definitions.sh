#!/bin/bash
for file in $(find ./workers/process/ -type f -not -name "_*.py");
do
  base_filename=$(basename -- "$file")
  filename_json="${base_filename%.*}.json"
  if [ ! -f "./rest/process_definitions/$filename_json" ]
  then
    wget -P ./rest/process_definitions/ https://raw.githubusercontent.com/Open-EO/openeo-processes/0.4.2/$filename_json --no-clobber
  fi
done