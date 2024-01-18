from enum import IntEnum
from typing import List
from pydantic import BaseModel, Field, validator

class DriveMode(IntEnum):
    STOP = 0
    FORWARD = 1
    REVERSE = 2
    OFFLINE = 254

class ReadRegistersResponse(BaseModel):
    error: bool = Field(default=False, description='Self explanatory')
    registers: List[int] = Field(default=[], description='Array of uint16 register values', examples=[[0,1,2], [25564, 0, 124, 5]])

class VFDState(BaseModel):
    cur_frequency: float = Field(default=0, description='Current operating frequency (Hz)', examples=[44.2, 60.0, 0.0])
    tgt_frequency: float = Field(default=0, description='Target / set operating frequency (Hz)', examples=[44.2, 60.0, 0.0])
    cur_drive_mode: DriveMode = Field(default=DriveMode.OFFLINE, description='Current drive mode', examples=[DriveMode.FORWARD, DriveMode.REVERSE, DriveMode.STOP])
    tgt_drive_mode: DriveMode = Field(default=DriveMode.OFFLINE, description='Target / set drive mode', examples=[DriveMode.FORWARD, DriveMode.REVERSE, DriveMode.STOP])
    output_voltage: float = Field(default=0, description='Output voltage (V)', examples=[120.0, 240.0, 22.4])
    output_current: float = Field(default=0, description='Output current (A)', examples=[44.2,0.1,93.2])
    input_power: float = Field(default=0, description='Input power (W)', examples=[9.02, 11.22])
    max_frequency: float = Field(default=0, description='Max supported frequency (Hz)', examples=[0.0,60.0,120.0])

class VFD(BaseModel):
    state: VFDState = Field(default=VFDState(), description='Current device state')
    slave_id: int = Field(default=0, description='Configured modbus slave ID', examples=[1,2,4,5])
    display_name: str = Field(default=0, description='Device display name', examples=["My VFD", "Big VFD"])
    id: str = Field(default=0, description='Device internal ID', examples=["VFD1", "BigVFD"])
    model: str = Field(default="Frenic", description='Device brand', examples=["Frenic"])
    poll_fail_count: int = Field(default=0, description='Poll fail count', examples=[0,10])

class StatelessVFD(BaseModel):
    slave_id: int = Field(default=0, description='Configured modbus slave ID', examples=[1,2,4,5])
    display_name: str = Field(default=0, description='Device display name', examples=["My VFD", "Big VFD"])
    id: str = Field(default=0, description='Device internal ID', examples=["VFD1", "BigVFD"])
    model: str = Field(default="Frenic", description='Device brand', examples=["Frenic"])
    poll_fail_count: int = Field(default=0, description='Poll fail count', examples=[0,10])

class SetVFDDriveModeParams(BaseModel):
    drive_mode: DriveMode = Field(default=DriveMode.STOP, description='Target drive mode')

    @validator('drive_mode')
    def assert_drive_mode(cls, drive_mode):
        assert drive_mode is not None, 'drive_mode is required'
        assert drive_mode >= 0 and drive_mode <= 2, 'drive_mode is not one of DriveMode.STOP<0>, DriveMode.FORWARD<1>, or DriveMode.REVERSE<2>'
        return drive_mode

class SetVFDFrequencyParams(BaseModel):
    frequency: float = Field(default=0, description='Target frequency')

    @validator('frequency')
    def assert_freq(cls, frequency):
        assert frequency is not None, 'frequency is required'
        assert frequency >= 0, 'frequency may not be negative'
        assert frequency <= 120, 'frequency may not be greater than 120'
        return frequency