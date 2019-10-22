# Running integration tests

Requirements:
- Python 3.6
- pipenv
- Docker + docker-compose

First copy `.env.example` to `.env` in the root directory of the project and enter valid variables.

Make sure process definitions have been downloaded (by running `download-process-definitions.sh`).

Procedure for running tests:
```
$ docker-compose up -d
$ cd tests/
$ pipenv shell
<shell> $ pipenv install --dev
<shell> $ pytest -x -v test_integration.py
```

Or run just chosen tests:
```
<shell> $ pytest -x -v test_integration.py -k test_root
```
