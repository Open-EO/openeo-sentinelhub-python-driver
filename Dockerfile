FROM python:3.6.6
ADD . /
RUN pip3 install pipenv
RUN chmod +x wait-for-it.sh
RUN pipenv install --system --deploy
