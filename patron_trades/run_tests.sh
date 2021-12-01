#!/bin/bash
set -euxo pipefail

coverage run -m pytest --capture=no --strict
coverage report -m
coverage html
