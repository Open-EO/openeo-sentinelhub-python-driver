# Running the workers as a standalone service

## Installation instructions

Mandatory: whichever method you select, first copy `../.env.example` to `.env` and enter the variables there.

### Docker

```
$ docker-compose build
$ docker-compose up -d
```

### Local install

When installling GDAL, we must make sure that the versions of `libgdal-dev` (as reported by `ogrinfo`) and the one installed via `pip` are the same.

```
$ sudo add-apt-repository ppa:ubuntugis/ppa
$ sudo apt-get update
$ sudo apt-get install gdal-bin
$ sudo apt-get install libgdal-dev
$ ogrinfo --version
GDAL 2.2.2, released 2017/09/15
```

Python package `GDAL` fails to install (on Ubuntu and Debian at least) if paths to GDAL header C files are not specified:
```
$ export CPLUS_INCLUDE_PATH=/usr/include/gdal
$ export C_INCLUDE_PATH=/usr/include/gdal
$ pipenv install
```

However, the version of the GDAL package must match the version reported earlier, so unless it already matches, we must force install correct version:
```
$ ogrinfo --version
GDAL 2.2.2, released 2017/09/15
$ pipenv shell
<pipenv shell> $ pip install GDAL==2.2.2
```

## Running

```
$ pipenv shell
<pipenv shell> $ python main.py
```