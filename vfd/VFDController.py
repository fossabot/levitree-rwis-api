from enum import Enum
from typing import Dict
from sanic.log import logger
from async_modbus import core, AsyncRTUClient
from dataclasses import dataclass, asdict
from json import dumps
import asyncio
import math
from aioretry import (
    retry,
    # Tuple[bool, Union[int, float]]
    RetryPolicyStrategy,
    RetryInfo
)

def retry_policy(info: RetryInfo) -> RetryPolicyStrategy:
    """
    - It will always retry up to 5 times
    - If fails for the first time, it will retry immediately,
    - If it fails again,
      aioretry will perform a 100ms delay before the second retry,
      200ms delay before the 3rd retry,
      the 4th retry immediately,
      100ms delay before the 5th retry,
      etc...
    """
    return (info.fails > 10), (info.fails - 1) % 3 * 0.1


from serial import SerialException

def frenicFunctionCodeToCoil(function_code: str) -> int:
    group = function_code[0:1]
    glt = {"F": 0, "E": 1, "C": 2, "P": 3, "H": 4, "A": 5, "b": 18, "r":10, "S": 7, "o": 6, "M": 8, "J": 13, "d": 19, "y": 14, "W": 15, "X": 16, "Z": 17}
    idn = int(function_code[1:])
    return glt[group]<<8 | idn

class DriveMode(Enum):
    STOP = 0
    FORWARD = 1
    REVERSE = 2
    OFFLINE = 254

@dataclass
class VFDState:
    cur_frequency: float = 0
    tgt_frequency: float = 0
    cur_drive_mode: DriveMode = DriveMode.OFFLINE
    tgt_drive_mode: DriveMode = DriveMode.OFFLINE
    output_voltage: float = 0
    output_current: float = 0
    input_power: float = 0
    max_frequency: float = 0

    def __init__(self):
        self.drive_mode = DriveMode.OFFLINE

@dataclass
class VFD:
    state: VFDState
    slave_id: int = 0
    display_name: str = ""
    id: str = ""
    model: str = ""
    poll_fail_count: int = 0

    def __init__(self):
        self.state = VFDState()

def custom_asdict_factory(data):

    def convert_value(obj):
        if isinstance(obj, Enum):
            return obj.value
        return obj

    return dict((k, convert_value(v)) for k, v in data)

class VFDController:
    vfds: Dict[str, VFD] = {}
    serial_path = ""
    client: AsyncRTUClient = None
    client_lock = asyncio.Lock()

    def __init__(self, serial_path):
        self.serial_path = serial_path

    def registerVFD(self, slave_id: int, display_name: str, id: str, model="Frenic"):
        newVFD = VFD()
        newVFD.display_name = display_name
        newVFD.slave_id = slave_id
        newVFD.id = id
        newVFD.model = model

        self.vfds[id] = newVFD

        logger.info(f"Registering VFD {slave_id} with name {display_name}")

    def hasVFD(self, id: str) -> bool:
        return (id in self.vfds)
    
    def getVFDS(self) -> Dict[str, VFD]:
        return self.vfds
    
    def getVFDSArr(self) -> []:
        d = []
        for vfd in self.vfds:
            d.append(asdict(self.vfds[vfd], dict_factory=custom_asdict_factory))
        return d

    def getState(self, vfd_id: str) -> VFDState:
        return self.vfds[vfd_id].state
    
    def getStateDict(self, vfd_id: str) -> Dict[any, any]:
        return asdict(self.vfds[vfd_id].state, dict_factory=custom_asdict_factory)
    
    async def getCoils(self, vfd_id: str, start_code: str, num: int):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            #We're starting read at M09, 6 regs, to M15.
            async with self.client_lock:
                state = await asyncio.wait_for(self.client.read_holding_registers(vfd.slave_id, frenicFunctionCodeToCoil(start_code), num), timeout=10) #DF 22
                return state
        else:
            logger.error(f"Cannot update state for VFD {vfd.display_name} as {vfd.model} is unimplemented!")
    
    async def updateState(self, vfd_id: str):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            #We're starting read at M05, 10 regs, to M15.
            async with self.client_lock:
                state = await asyncio.wait_for(self.client.read_holding_registers(vfd.slave_id, frenicFunctionCodeToCoil("M05"), 10), timeout=0.4)

                tgt_freq = float(state[0] / 100)
                freq = float(state[4] / 100)
                input_power = float(state[5] / 100)
                output_current = float(state[6] / 100)
                output_voltage = float(state[7] / 10)
                operation_command = state[8]
                operation_status = state[9]
                tgt_drive_mode = DriveMode.OFFLINE
                if operation_command & 0b1:
                    tgt_drive_mode = DriveMode.FORWARD
                elif operation_command & 0b10:
                    tgt_drive_mode = DriveMode.REVERSE
                else:
                    tgt_drive_mode = DriveMode.STOP
                cur_drive_mode = DriveMode.OFFLINE
                if operation_status & 0b1:
                    cur_drive_mode = DriveMode.FORWARD
                elif operation_status & 0b10:
                    cur_drive_mode = DriveMode.REVERSE
                else:
                    cur_drive_mode = DriveMode.STOP

                vfd.state.tgt_frequency = tgt_freq
                vfd.state.cur_frequency = freq

                vfd.state.input_power = input_power
                vfd.state.output_voltage = output_voltage
                vfd.state.output_current = output_current

                vfd.state.tgt_drive_mode = tgt_drive_mode
                vfd.state.cur_drive_mode = cur_drive_mode

                #Get max allowed run frequency from unit - this populates range sliders
                state = await asyncio.wait_for(self.client.read_holding_registers(vfd.slave_id, frenicFunctionCodeToCoil("F03"), 1), timeout=0.4) #DF 22
                max_freq = int(state[0] / 10)
                vfd.state.max_frequency = max_freq
        else:
            logger.error(f"Cannot update state for VFD {vfd.display_name} as {vfd.model} is unimplemented!")
    
    @retry(retry_policy)
    async def setFrequency(self, vfd_id: str, frequency: float):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            regVal = math.floor(frequency * 100)
            async with self.client_lock:
                await asyncio.wait_for(self.client.write_register(vfd.slave_id, frenicFunctionCodeToCoil("S05"), regVal),timeout=0.4) #DF 22
                logger.info(f"VFD {vfd.display_name} frequency updated to {frequency}Hz")
                vfd.state.tgt_frequency = frequency

    @retry(retry_policy)
    async def setDriveMode(self, vfd_id: str, drive_mode: DriveMode):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            if drive_mode == DriveMode.FORWARD:
                regVal = 1
            elif drive_mode == DriveMode.REVERSE:
                regVal = 2
            elif drive_mode == DriveMode.STOP:
                regVal = 0
            else:
                return
            async with self.client_lock:
                await asyncio.wait_for(self.client.write_register(vfd.slave_id, frenicFunctionCodeToCoil("S06"), regVal),timeout=0.4) #DF 14
                logger.info(f"VFD {vfd.display_name} drive mode updated to {repr(drive_mode)}")
                vfd.state.tgt_drive_mode = drive_mode

    @retry(retry_policy)
    async def clearAlarm(self, vfd_id: str):
        vfd = self.vfds[vfd_id]
        if vfd.model == "Frenic":
            async with self.client_lock:
                await asyncio.wait_for(self.client.write_register(vfd.slave_id, frenicFunctionCodeToCoil("S06"), 0b1000000000000000),timeout=0.4) #DF 14
                logger.info(f"VFD {vfd.display_name} alarm cleared")
    
    async def modbusConsumer(self):
        while True:
            await asyncio.sleep(0.2)
            if self.client is not None:
                for vfd in self.vfds:
                    vfd = self.vfds[vfd]
                    try:
                        await self.updateState(vfd.id)
                        vfd.poll_fail_count = 0
                        await asyncio.sleep(0.1)
                    except Exception:
                        vfd.poll_fail_count = vfd.poll_fail_count + 1
                        if vfd.poll_fail_count > 5:
                            self.initializeModbus()
                        elif vfd.poll_fail_count > 10:
                            vfd.state.drive_mode = DriveMode.OFFLINE
                            logger.error(f"Could not get VFD state: {vfd.display_name} as a serial exception occured!")
                                

    def initializeModbus(self):
        self.client = core.modbus_for_url(self.serial_path, {"baudrate":9600, "parity":"E"})