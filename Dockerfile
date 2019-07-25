FROM python:3.6.6
ADD . /
RUN pip3 install pipenv
RUN pipenv install --system --deploy
