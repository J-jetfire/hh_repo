FROM python:3.10.9-slim-buster

RUN apt-get update && \
    apt-get install -y gcc libpq-dev && \
    apt clean && \
    rm -rf /var/cache/apt/*

COPY ./requirements.txt /src/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /src/requirements.txt

COPY . /src
COPY ./scripts /src/scripts

WORKDIR /src

RUN chmod +x ./scripts/start-prod.sh

CMD ["/src/scripts/start-prod.sh"]