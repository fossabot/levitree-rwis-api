import asyncio
from sanic.response import json
from sanic import BadRequest, Blueprint, InternalServerError, Request, Websocket
from sanic.log import logger
from sanic_ext import validate, openapi
import yaml
from dataclasses import asdict
from RequestTypes import SetVFDStateParams
from .VFDController import VFDController, VFD, VFDState

VFDBlueprint = Blueprint("vfd", url_prefix="/vfd")

@VFDBlueprint.websocket("/live")
async def live_state(request: Request, ws: Websocket):
    async for msg in ws:
        await ws.send(msg)

@VFDBlueprint.get("/")
@openapi.definition(
    summary="List all VFDs configured on the system",
    tag="VFD Control",
    response={"application/json": [VFD]}
)
async def get_vfd_list(request):
    if not hasattr(request.app.ctx, 'vfdController'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController = request.app.ctx.vfdController

    return json(controller.getVFDSArr())

@VFDBlueprint.get("/<vfd_id>")
@openapi.definition(
    summary="Get state of single VFD",
    tag="VFD Control",
    response={
        "application/json": VFDState
    },
)
async def get_vfd_state(request, vfd_id: str):
    if not hasattr(request.app.ctx, 'vfdController'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController = request.app.ctx.vfdController

    if not controller.hasVFD(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")

    vfdState = controller.getStateDict(vfd_id)

    return json(vfdState)

@VFDBlueprint.get("/<vfd_id>/<code>/<num_reg>")
@openapi.definition(
    summary="Get num_regs starting at code from VFD over Modbus",
    tag="VFD Control",
    response={
        "application/json": [int]
    },
)
async def get_vfd_coils(request, vfd_id: str, code: str, num_reg: int):
    if not hasattr(request.app.ctx, 'vfdController'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController = request.app.ctx.vfdController

    if not controller.hasVFD(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")

    vfdState = await controller.getCoils(vfd_id, code, num_reg)

    return json(vfdState)

@VFDBlueprint.get("/<vfd_id>/clear_alarm")
@openapi.definition(
    summary="Clear active alarm on VFD",
    tag="VFD Control",
)
async def clear_vfd_alarm(request, vfd_id: str):
    if not hasattr(request.app.ctx, 'vfdController'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController = request.app.ctx.vfdController

    if not controller.hasVFD(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")

    await controller.clearAlarm(vfd_id)

    return json({})

@VFDBlueprint.post("/<vfd_id>")
@openapi.definition(
    summary="Set state of single VFD",
    tag="VFD Control",
    body={
        "application/json": SetVFDStateParams.model_json_schema()
    },
)
@validate(json=SetVFDStateParams)
async def set_vfd_state(request, vfd_id: str, body: SetVFDStateParams):
    if not hasattr(request.app.ctx, 'vfdController'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController = request.app.ctx.vfdController

    if not controller.hasVFD(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")
    logger.info
    if body.frequency != None:
        request.app.add_task(controller.setFrequency(vfd_id, body.frequency), name="set_frequency")

    if body.drive_mode != None:
        request.app.add_task(controller.setDriveMode(vfd_id, body.drive_mode), name="set_drive_mode")

    return json({})

@VFDBlueprint.listener('before_server_start')
def open_serial_port(app):
    with open("config.yaml") as cfgFile:
        cfg = yaml.load(cfgFile, Loader=yaml.FullLoader)
        app.ctx.vfdController = VFDController(cfg["modbus_path"])
        for modbus_device in cfg["modbus_devices"]:
            if modbus_device["type"] == "VFD":
                app.ctx.vfdController.registerVFD(modbus_device["slave_id"], modbus_device["display_name"], modbus_device["name"], model=modbus_device["model"])
        app.add_task(app.ctx.vfdController.initializeModbus, name="init_modbus")
        app.add_task(app.ctx.vfdController.modbusConsumer, name="modbus_consumer")