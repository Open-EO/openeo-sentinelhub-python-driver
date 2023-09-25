# use base aws lambda docker image for python (all the sources listed bellow)
# https://www.cloudtechsimplified.com/run-docker-containers-images-from-ecr-in-aws-lambda-along-with-cicd-python/
# https://docs.aws.amazon.com/lambda/latest/dg/python-image.html#python-image-instructions
# https://gallery.ecr.aws/lambda/python/
# https://zebradil.me/post/2018-05-25-pipenv-for-aws-lambda/
# https://stackoverflow.com/questions/48381918/how-do-i-install-git-using-aws-lambda
# https://stackoverflow.com/a/68787552
FROM public.ecr.aws/lambda/python:3.9

# install pipenv and git that are needed to install dependencies
RUN yum -y install git
RUN pip install pipenv

# copy the /rest folder
COPY ./ ${LAMBDA_TASK_ROOT}

# create requirements.txt file and
# install dependencies with pip
RUN pipenv requirements > requirements.txt
RUN pip install -r requirements.txt

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
# app.app is the same as in zappa_settings.json.template
CMD [ "app.app" ]