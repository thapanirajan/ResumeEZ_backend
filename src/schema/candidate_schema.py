from typing import Optional

from pydantic import BaseModel


class UpdateCandidateSchema(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    current_role: Optional[str] = None
    experience_years: Optional[int] = None
