FROM python:3.10
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN ulimit -s unlimited
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY ./app /code/app
COPY ./static /code/static
COPY ./static/locations.json /code/static/locations.json