from fastapi import APIRouter


recruiter_router = APIRouter(tags=["Recruiter"])

@recruiter_router.post("/")
async def recruiter_job():
    pass
