from pydantic import BaseModel

class ResponseModel(BaseModel):
    status: str
    data: dict
    message: str