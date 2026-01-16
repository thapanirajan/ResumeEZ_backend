from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse

from src.config.supabase_config import supabase

upload_router = APIRouter(prefix="", tags=["Files"])
BUCKET_NAME = "document"


@upload_router.post("/file")
async def upload_route(file: UploadFile = File(...)):
    print("Incoming file upload:", file.filename)

    file_ext = file.filename.split(".")[-1]
    unique_filename = f"{uuid4().hex}.{file_ext}"
    print("Generated unique filename:", unique_filename)

    try:
        # Read file content
        file_content = await file.read()
        print("Read file content, length:", len(file_content))

        # Upload to Supabase Storage
        print("Uploading file to Supabase bucket:", BUCKET_NAME)
        upload_response = supabase.storage.from_(BUCKET_NAME).upload(unique_filename, file_content)
        print("Upload response:", upload_response)

        # Get public URL
        public_url_response = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)
        print("Public URL response:", public_url_response)

        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(unique_filename)
        print("Extracted public URL:", public_url)

        if not public_url:
            raise Exception("Failed to get public URL from Supabase response")

    except Exception as e:
        print("Exception during upload:", e)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    finally:
        await file.close()
        print("File closed")

    return JSONResponse(
        content={
            "filename": unique_filename,
            "original_name": file.filename,
            "url": public_url
        }
    )
