#!/bin/bash
for file in $(find ./workers/process/ -type f -not -name "_*.py");
do
  base_filename=$(basename -- "$file")
  process="${base_filename%.*}"

  # we can't download definitions for our extensions to the standard:
  if [ "$process" = "create_cube" -o "$process" = "assert_equals" ]
  then
    echo "Ignoring process: ${process} (extension)"
  else
    filename_json="${process}.json"
    if [ -f "./rest/process_definitions/$filename_json" ]
    then
      echo "Process definition already exists: ${process}"
    else
      wget -P ./rest/process_definitions/ https://raw.githubusercontent.com/Open-EO/openeo-processes/1.0.0/$filename_json --no-clobber
    fi
  fi
done
