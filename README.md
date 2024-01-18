![Logo](https://images.squarespace-cdn.com/content/v1/61ccd15eb71fc5016709e662/ff2e09a6-3681-4bb6-ad4f-28b6d113bf9d/Levitree_Logo2.png?format=1500w)

[![GPLv3 License](https://img.shields.io/badge/License-GPL%20v3-yellow.svg)](https://opensource.org/licenses/)

# Real World Integration Server API

RWIS-API controls and monitors various hardware devices connected to the control system.

## Features

These currently include:

- Variable Frequency Drives connected over Modbus RTU

Support is planned for:

- Ultrasonic distance sensors
- Sensors connected over I2C based ADC

## Configuration

To run this project, you will need to add the following environment variables to your .env file

`API_KEY`

`ANOTHER_API_KEY`

## Run Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m sanic server
```

## Authors

- [@acvigue](https://www.github.com/acvigue)
