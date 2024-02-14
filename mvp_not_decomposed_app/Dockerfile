FROM python:3.10.4
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN ulimit -s unlimited
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY . /code/