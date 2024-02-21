# Nendo Platform API server

<br>
<p align="left">
    <img src="https://okio.ai/docs/assets/nendo_logo.png" width="500" alt="Nendo Core">
</p>
<br>

<p align="left">
<a href="https://okio.ai" target="_blank">
    <img src="https://img.shields.io/website/https/okio.ai" alt="Website">
</a>
<a href="https://twitter.com/okio_ai" target="_blank">
    <img src="https://img.shields.io/twitter/url/https/twitter.com/okio_ai.svg?style=social&label=Follow%20%40okio_ai" alt="Twitter">
</a>
<a href="https://discord.gg/gaZMZKzScj" target="_blank">
    <img src="https://dcbadge.vercel.app/api/server/XpkUsjwXTp?compact=true&style=flat" alt="Discord">
</a>
</p>

---

The Nendo API Server is the backend component of [Nendo Platform](https://github.com/okio-ai/nendo-platform). It builds on Nendo and provides a set of powerful features for managing large libraries of audio files, organizing them in collections and running AI models on them.

**The most straightforward way to run Nendo API Server is as part of [Nendo Platform](https://github.com/okio-ai/nendo-platform), so it is recommended to refer to that repo for deployment instructions.**

## Features

- FastAPI server with swagger documentation.
- Uses a highly performant [PostgresDB implementation](https://github.com/okio-ai/nendo_plugin_library_postgres) of the Nendo Library.
- Scheduling of dockerized AI actions via Redis.
- User management based on email/password combinations. OAuth forthcoming.
- Extensible architecture that allows for quick integration of new application routes into the server.

## Requirements

The Nendo API Server requires a PostgresDB instance running either locally or remotely that is reachable from where the server is running. The default configuration assumes that the database is running on localhost, port 5432 and has a user called `nendo` with password `nendo` and a database `nendo`, for which the user has full rights. If your environment is different, use [environment variables to configure the server according to your setup](#configuration). Furthermore, to use the embedding features, make sure that the PostgresDB instance has the `pgvector` extension installed. Follow the instructions presented in the [README of the PostgresDB implementation](https://github.com/okio-ai/nendo_plugin_library_postgres#requirements) of the Nendo Library to set it up.

Furthermore, the Nendo API Server needs access to a Redis instance for scheduling of actions.

## Installation

To setup the Nendo API Server, just make sure you are running python >= 3.8 and < 3.11. Then install the dependencies:

```
pip install -r requirements.txt
```

## Running

To run a nendo API server instance locally on port 8000, just use the startup script `start_server.sh`.

Alternatively, you can start a new nendo server by calling uvicorn directly (the `--reload` flag enables hot-reloading)

```
cd nendo_server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

## Configuration

To configure the Nendo API Server, the use of environment variables is recommended. Refer to the [documentation](https://okio.ai/docs/platform/server/config/) for more information.

## Development

> **Tip**: We recommend using the [Nendo Platform](https://github.com/okio-ai/nendo-platform#development) for development, as it's very easy to set up. Just follow the instructions there and you'll be ready to work on the development of the Nendo API Server within minutes.

If you want to work on the development of the Nendo API Server without using docker, you can use the `start_server_dev.sh` script, which will enable hot-reloading.

To also work on the development of nendo, go to local path containing your nendo code and run

```
pip3 install -e ./
```

to install the package in editable mode. Now you can change nendo's core codebase and the changes will be reflected _upon restart_ of `nendo_server`.
