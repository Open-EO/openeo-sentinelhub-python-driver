## Installation instructions

Mandatory: whichever method you select, first copy `.env.example` to `.env` and enter the variables there.

### Docker

In root folder, start up the supporting services.

```
$ docker-compose up -d --build dynamodb
$ docker-compose up -d --build minio
$ docker-compose up -d --build createbuckets
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

### Environment variables

Endpoint url of the local `AWS S3` service has to be specified as an enviroment variable `DATA_AWS_S3_ENDPOINT_URL`. By default, local `S3` runs on `http://localhost:9000`. 

```
export DATA_AWS_S3_ENDPOINT_URL="http://localhost:9000" 
```

### Starting up the workers service

```
$ pipenv shell
<pipenv shell> $ python main.py
```
