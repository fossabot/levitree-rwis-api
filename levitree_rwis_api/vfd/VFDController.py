from enum import Enum
from typing import Dict
from sanic.log import logger
from async_modbus import core, AsyncRTUClient

from serial import SerialException
from . import VFDTypes, Frenic
import asyncio
import math
from aioretry import (
    retry,
    RetryPolicyStrategy,
    RetryInfo
)

def retry_policy(info: RetryInfo) -> RetryPolicyStrategy:
    return (info.fails > 10), (info.fails - 1) % 3 * 0.1

class VFDController:
    vfds: Dict[str, VFDTypes.VFD] = {}
    serial_path = ""
    client: AsyncRTUClient = None
    client_lock = asyncio.Lock()

    def __init__(self, serial_path):
        self.serial_path = serial_path

    def register_vfd(self, slave_id: int, display_name: str, id: str, model="Frenic"):
        newVFD = VFDTypes.VFD()
        newVFD.display_name = display_name
        newVFD.slave_id = slave_id
        newVFD.id = id
        newVFD.model = model

        self.vfds[id] = newVFD

        logger.info(f"Registering VFD {slave_id} with name {display_name}")

    def has_vfd(self, id: str) -> bool:
        return (id in self.vfds)
    
    def get_vfds(self) -> Dict[str, VFDTypes.VFD]:
        return self.vfds

    def get_vfd_state(self, vfd_id: str, ext_rep=False) -> VFDTypes.VFDState:
        return self.vfds[vfd_id].state.model_dump()

    async def read_vfd_registers(self, vfd_id: str, start_code: str, num: int):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            async with self.client_lock:
                state = await asyncio.wait_for(self.client.read_holding_registers(vfd.slave_id, Frenic.function_code_to_coil(start_code), num), timeout=0.4)
                return state
        else:
            logger.error(f"Cannot update state for VFD {vfd.display_name} as {vfd.model} is unimplemented!")
    
    async def __updateState(self, vfd_id: str):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            #We're starting read at M05, 10 regs, to M15.
            async with self.client_lock:
                state = await asyncio.wait_for(self.client.read_holding_registers(vfd.slave_id, Frenic.function_code_to_coil("M05"), 10), timeout=0.4)

                tgt_freq = float(state[0] / 100)
                freq = float(state[4] / 100)
                input_power = float(state[5] / 100)
                output_current = float(state[6] / 100)
                output_voltage = float(state[7] / 10)
                operation_command = state[8]
                operation_status = state[9]
                tgt_drive_mode = VFDTypes.DriveMode.OFFLINE
                if operation_command & 0b1:
                    tgt_drive_mode = VFDTypes.DriveMode.FORWARD
                elif operation_command & 0b10:
                    tgt_drive_mode = VFDTypes.DriveMode.REVERSE
                else:
                    tgt_drive_mode = VFDTypes.DriveMode.STOP
                cur_drive_mode = VFDTypes.DriveMode.OFFLINE
                if operation_status & 0b1:
                    cur_drive_mode = VFDTypes.DriveMode.FORWARD
                elif operation_status & 0b10:
                    cur_drive_mode = VFDTypes.DriveMode.REVERSE
                else:
                    cur_drive_mode = VFDTypes.DriveMode.STOP

                vfd.state.tgt_frequency = tgt_freq
                vfd.state.cur_frequency = freq

                vfd.state.input_power = input_power
                vfd.state.output_voltage = output_voltage
                vfd.state.output_current = output_current

                vfd.state.tgt_drive_mode = tgt_drive_mode
                vfd.state.cur_drive_mode = cur_drive_mode

                #Get max allowed run frequency from unit - this populates range sliders
                state = await asyncio.wait_for(self.client.read_holding_registers(vfd.slave_id, Frenic.function_code_to_coil("F03"), 1), timeout=0.4) #DF 22
                max_freq = int(state[0] / 10)
                vfd.state.max_frequency = max_freq
        else:
            logger.error(f"Cannot update state for VFD {vfd.display_name} as {vfd.model} is unimplemented!")
    
    @retry(retry_policy)
    async def set_frequency(self, vfd_id: str, frequency: float):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            regVal = math.floor(frequency * 100)
            async with self.client_lock:
                await asyncio.wait_for(self.client.write_register(vfd.slave_id, Frenic.function_code_to_coil("S05"), regVal),timeout=0.4) #DF 22
                logger.info(f"VFD {vfd.display_name} frequency updated to {frequency}Hz")
                vfd.state.tgt_frequency = frequency

    @retry(retry_policy)
    async def set_drive_mode(self, vfd_id: str, drive_mode: VFDTypes.DriveMode):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            if drive_mode == VFDTypes.DriveMode.FORWARD:
                regVal = 1
            elif drive_mode == VFDTypes.DriveMode.REVERSE:
                regVal = 2
            elif drive_mode == VFDTypes.DriveMode.STOP:
                regVal = 0
            else:
                return
            async with self.client_lock:
                await asyncio.wait_for(self.client.write_register(vfd.slave_id, Frenic.function_code_to_coil("S06"), regVal),timeout=0.4) #DF 14
                logger.info(f"VFD {vfd.display_name} drive mode updated to {repr(drive_mode)}")
                vfd.state.tgt_drive_mode = drive_mode

    @retry(retry_policy)
    async def clear_alarm(self, vfd_id: str):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            async with self.client_lock:
                await asyncio.wait_for(self.client.write_register(vfd.slave_id, Frenic.function_code_to_coil("S06"), 0b1000000000000000),timeout=0.4) #DF 14
                logger.info(f"VFD {vfd.display_name} alarm cleared")
    
    async def modbus_polling_loop(self):
        while True:
            await asyncio.sleep(0.2)
            if self.client is not None:
                for vfd in self.vfds:
                    vfd = self.vfds[vfd]
                    try:
                        await self.__updateState(vfd.id)
                        vfd.poll_fail_count = 0
                        await asyncio.sleep(0.1)
                    except SerialException as e:
                        if e.errno == 2:
                            logger.error(f"The serial port could not be opened!")
                            #exit(1)
                    except Exception:
                        vfd.poll_fail_count = vfd.poll_fail_count + 1
                        if vfd.poll_fail_count > 5:
                            self.initialize_modbus()
                        elif vfd.poll_fail_count > 10:
                            vfd.state.drive_mode = VFDTypes.DriveMode.OFFLINE
                            logger.error(f"Could not get VFD state: {vfd.display_name} as a serial exception occured!")
                                

    def initialize_modbus(self):
        logger.info("Initializing Modbus communications")
        self.client = core.modbus_for_url(self.serial_path, {"baudrate":9600, "parity":"E"})