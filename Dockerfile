FROM python:3.8-slim-bullseye AS nendo-server-base

ARG UID=1000
ARG GID=1000
ARG DOCKER_GID=999

# update apt
RUN apt update && apt -y upgrade

# install dependencies
RUN apt install -y \
    libpq-dev ffmpeg libportaudio2 \
    portaudio19-dev build-essential \
    libmpg123-dev rubberband-cli \
    gcc git zip docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# setup user
RUN groupadd -o -g $GID nendo
RUN useradd nendo --create-home -u $UID -g $GID -m -s /bin/bash 
RUN groupmod -g $DOCKER_GID docker
RUN usermod -aG docker nendo
USER nendo

ENV PATH="$PATH:/home/nendo/.local/bin"
WORKDIR /home/nendo/nendo-server

COPY requirements.txt .
RUN pip install -r requirements.txt

# copy all files
COPY . .

# install app dependencies
RUN pip install -r nendo_server/apps/*/requirements.txt

EXPOSE 8000

USER root
RUN mkdir /home/nendo/nendo_library
RUN chown -R nendo:nendo /home/nendo/
USER nendo
WORKDIR /home/nendo/nendo-server/nendo_server

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "logger/conf.yaml"]

FROM nendo-server-base AS nendo-server-dev

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug", "--log-config", "logger/conf.yaml"]

FROM nendo-server-base AS nendo-server-prod

CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000", "--log-level", "warning"]
