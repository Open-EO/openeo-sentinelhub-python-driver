# Running tests

Requirements:
- Python 3.6
- pipenv
- Docker + docker-compose

First copy `.env.example` to `.env` in the root directory of the project and enter valid variables. 

The tests need fixtures which are not saved in the repository, but must instead be fetched from Sentinel Hub (by using `load_fixtures.sh`).

Procedure for running tests:
```
$ docker-compose up -d
$ cd tests/
$ ./load_fixtures.sh
$ pipenv shell
<shell> $ pipenv install --dev
<shell> $ pytest -x -v
```

Or run separate test files:
```
<shell> $ pytest -x -v test_process.py
```

Or run just chosen tests:
```
<shell> $ pytest -x -v test_integration.py -k test_root
```



