# Running integration tests

Requirements:
- Python 3.6
- pipenv
- Docker + docker-compose


## Preparation

- in the root directory of the project copy `.env.example` to `.env`  and enter valid variables

- make sure process definitions have been downloaded (by running `download-process-definitions.sh`)

## Running tests

Procedure for running tests:
```
$ docker-compose up -d
$ cd rest/
$ pipenv install --dev
$ pipenv shell
<shell> $ cd ../tests/
<shell> $ pytest -x -v test_integration.py
```

Or run just chosen tests:
```
<shell> $ pytest -x -v test_integration.py -k test_root
```
