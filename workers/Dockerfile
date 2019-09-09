# There is no need for us to run pipenv in the container, so we don't. However
# we need to convert Pipfile(.lock) to requirements.txt, so that we can use
# pip install. This intermediate build container takes care of that:
FROM python:3.6-buster as python-requirements
COPY ./Pipfile ./Pipfile.lock /src/
WORKDIR /src/
RUN \
    pip install --upgrade pipenv && \
    pipenv lock -r > /requirements.txt


# Python 3.6 on Debian buster:
FROM python:3.6-buster
COPY --from=python-requirements /requirements.txt /requirements.txt
WORKDIR /src/
RUN \
    apt-get update && \
    apt-get install -y -q python3-gdal libgdal-dev && \
    export CPLUS_INCLUDE_PATH=/usr/include/gdal && \
    export C_INCLUDE_PATH=/usr/include/gdal && \
    pip install -r /requirements.txt && \
    pip install GDAL===2.4.0
COPY . /src/
CMD ["/usr/local/bin/python", "main.py"]