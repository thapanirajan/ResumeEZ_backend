from pydantic import BaseModel

class JobCreateSchema(BaseModel):
    title: str
    description: str
    location: str


