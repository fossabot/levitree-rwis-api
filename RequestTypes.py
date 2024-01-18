from typing import Optional
from pydantic import BaseModel, validator
from vfd.VFDController import DriveMode

class SetVFDStateParams(BaseModel):
    frequency: Optional[float] = None
    drive_mode: Optional[DriveMode] = None

    @validator('frequency')
    def assert_freq(cls, v):
        assert v >= 0, 'frequency may not be negative'
        assert v <= 100, 'frequency may not be greater than 100'
        return v
    
class SetAutopilotStateParams(BaseModel):
    state: Optional[bool] = None
    target_distance: Optional[int] = None
    target_flow_rate: Optional[int] = None