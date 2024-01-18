import asyncio
from json import dumps
import yaml

from sanic.response import json
from sanic import BadRequest, Blueprint, InternalServerError, Request, Websocket
from sanic_ext import validate, openapi
from sanic_ext.extensions.openapi.definitions import Response

from levitree_rwis_api import AppTypes

from . import VFDTypes, VFDController

VFDBlueprint = Blueprint("VFDBlueprint", url_prefix="/vfds")

@VFDBlueprint.websocket("/live_state")
@openapi.definition(
    summary="Subscribe to live state changes of all VFDs attached to system",
    tag="VFD Control"
)
async def live_state(request: Request, ws: Websocket):
    if not hasattr(request.app.ctx, 'vfd_controller'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController.VFDController = request.app.ctx.vfd_controller
    while True:
        dataDict = {}
        for vfd in controller.get_vfds_dict():
            dataDict[vfd] = controller.get_vfd_state(vfd, ext_rep=True)
        data = dumps(dataDict)
        await ws.send(data)
        await asyncio.sleep(0.2)

@VFDBlueprint.get("/")
@openapi.definition(
    summary="List VFDs",
    tag="VFD Control",
    response=[Response({"application/json": VFDTypes.StatelessVFD.model_json_schema()}, 200, "Success")]
)
async def get_vfd_list(request):
    if not hasattr(request.app.ctx, 'vfd_controller'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController.VFDController = request.app.ctx.vfd_controller

    return json(controller.get_vfds_arr(state=False))

@VFDBlueprint.get("/<vfd_id>/state")
@openapi.definition(
    summary="Get VFD state",
    tag="VFD Control",
    response=[Response({"application/json": VFDTypes.VFDState.model_json_schema()}, 200, "Success")]
)
async def get_vfd_state(request, vfd_id: str):
    if not hasattr(request.app.ctx, 'vfd_controller'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController.VFDController = request.app.ctx.vfd_controller

    if not controller.has_vfd(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")

    vfdState = controller.get_vfd_state(vfd_id, ext_rep=True)

    return json(vfdState)

@VFDBlueprint.get("/<vfd_id>/read/<code>/<num_regs>")
@openapi.definition(
    summary="Read VFD registers",
    tag="VFD Control",
    response=[Response({"application/json": VFDTypes.ReadRegistersResponse.model_json_schema()}, 200, "Success")]
)
async def read_vfd_registers(request, vfd_id: str, code: str, num_regs: int):
    if not hasattr(request.app.ctx, 'vfd_controller'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController.VFDController = request.app.ctx.vfd_controller

    if not controller.hasVFD(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")

    register_array = await controller.read_vfd_registers(vfd_id, code, num_regs)

    return json({"error": False, "registers": register_array})

@VFDBlueprint.get("/<vfd_id>/clear_alarm")
@openapi.definition(
    summary="Clear alarm",
    tag="VFD Control",
    response=[Response({"application/json": AppTypes.GenericResponse.model_json_schema()}, 200, "Success")]
)
async def clear_vfd_alarm(request, vfd_id: str):
    if not hasattr(request.app.ctx, 'vfd_controller'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController.VFDController = request.app.ctx.vfd_controller

    if not controller.has_vfd(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")

    await controller.clear_alarm(vfd_id)

    return json({"error": False, "message": "Alarm cleared"})

@VFDBlueprint.post("/<vfd_id>/drive_mode")
@openapi.definition(
    summary="Set drive mode",
    tag="VFD Control",
    body={"application/json": VFDTypes.SetVFDDriveModeParams.model_json_schema()},
    response=[Response({"application/json": AppTypes.GenericResponse.model_json_schema()}, 200, "Success")]
)
@validate(json=VFDTypes.SetVFDDriveModeParams)
async def set_vfd_drive_mode(request, vfd_id: str, body: VFDTypes.SetVFDDriveModeParams):
    if not hasattr(request.app.ctx, 'vfd_controller'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController.VFDController = request.app.ctx.vfd_controller

    if not controller.has_vfd(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")

    await controller.set_drive_mode(vfd_id, body.drive_mode)

    return json({"error": False, "message": f"Drive mode updated to {body.drive_mode.name}"})

@VFDBlueprint.post("/<vfd_id>/frequency")
@openapi.definition(
    summary="Set frequency",
    tag="VFD Control",
    body={"application/json": VFDTypes.SetVFDFrequencyParams.model_json_schema()},
    response=[Response({"application/json": AppTypes.GenericResponse.model_json_schema()}, 200, "Success")]
)
@validate(json=VFDTypes.SetVFDFrequencyParams)
async def set_vfd_state(request, vfd_id: str, body: VFDTypes.SetVFDFrequencyParams):
    if not hasattr(request.app.ctx, 'vfd_controller'):
        raise InternalServerError("VFD subsystem not initialized!")
    controller: VFDController.VFDController = request.app.ctx.vfd_controller

    if not controller.has_vfd(vfd_id):
        raise BadRequest(f"VFD {vfd_id} does not exist!")

    await controller.set_frequency(vfd_id, body.frequency)

    return json({"error": False, "message": f"Frequency updated to {body.frequency} Hz"})



@VFDBlueprint.listener('before_server_start')
def open_serial_port(app):
    with open("config.yaml") as cfgFile:
        cfg = yaml.load(cfgFile, Loader=yaml.FullLoader)
        app.ctx.vfd_controller = VFDController.VFDController(cfg["modbus_path"])
        for modbus_device in cfg["modbus_devices"]:
            if modbus_device["type"] == "VFD":
                app.ctx.vfd_controller.register_vfd(modbus_device["slave_id"], modbus_device["display_name"], modbus_device["name"], model=modbus_device["model"])
        app.add_task(app.ctx.vfd_controller.initialize_modbus, name="init_modbus")
        app.add_task(app.ctx.vfd_controller.modbus_polling_loop, name="modbus_consumer")