![Logo](https://images.squarespace-cdn.com/content/v1/61ccd15eb71fc5016709e662/ff2e09a6-3681-4bb6-ad4f-28b6d113bf9d/Levitree_Logo2.png?format=1500w)

[![GPLv3 License](https://img.shields.io/badge/License-GPL%20v3-yellow.svg)](https://opensource.org/licenses/)

# Real World Integration Server API

RWIS-API controls and monitors various hardware devices connected to the control system.

```bash
ghcr.io/acvigue/levitree-rwis-api:main (linux/arm64,linux/amd64,linux/arm/v7)
```

## Features

These currently include:

- Variable Frequency Drives connected over Modbus RTU

Support is planned for:

- Ultrasonic distance sensors
- Sensors connected over I2C based ADC

## Configuration

To run this project, you will need to use the following environment variables

`CONFIG_PATH = *path to config file*`

`MODBUS_PATH = *path to modbus serial device*`

## Run Locally

```bash
poetry install
poetry run python -m sanic levitree_rwis_api.app
```

## Authors

- [@acvigue](https://www.github.com/acvigue)
