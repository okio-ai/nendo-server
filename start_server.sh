#!/bin/bash

cd nendo_server && python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload --log-level debug --log-config ./logger/conf.yaml
