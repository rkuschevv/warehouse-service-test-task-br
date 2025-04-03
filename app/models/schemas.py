from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

class MovementData(BaseModel):
    movement_id: str
    warehouse_id: str
    timestamp: datetime
    event: Literal["arrival", "departure"]
    product_id: str
    quantity: int

class KafkaMessage(BaseModel):
    id: str
    source: str
    specversion: str
    type: str
    datacontenttype: str
    dataschema: str
    time: int
    subject: str
    destination: str
    data: MovementData

class WarehouseState(BaseModel):
    warehouse_id: str
    product_id: str
    quantity: int

class MovementInfo(BaseModel):
    movement_id: str
    source_warehouse: Optional[str] = None
    destination_warehouse: Optional[str] = None
    product_id: str
    departure_time: Optional[datetime] = None
    arrival_time: Optional[datetime] = None
    time_difference_seconds: Optional[float] = None
    departure_quantity: Optional[int] = None
    arrival_quantity: Optional[int] = None
    quantity_difference: Optional[int] = None 