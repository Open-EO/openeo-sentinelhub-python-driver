FROM public.ecr.aws/docker/library/python:3.9

RUN apt-get install git -y
RUN pip install pipenv

COPY ./ /rest
WORKDIR /rest

RUN pipenv requirements > requirements.txt
RUN pip install -r requirements.txt
RUN pip install gunicorn

CMD ["gunicorn","--bind","0.0.0.0:8000", "--timeout", "300", "--threads", "20" , "--forwarded-allow-ips", "*", "wsgi:app"]
