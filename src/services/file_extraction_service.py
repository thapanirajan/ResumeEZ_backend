
import io
import requests
from fastapi import UploadFile, HTTPException

class FileExtractionService:
    @staticmethod
    async def extract_text(file: UploadFile) -> str:
        filename = file.filename.lower()
        content = await file.read()
        await file.seek(0)
        return FileExtractionService._process_content(content, filename)

    @staticmethod
    def extract_from_url(url: str) -> str:
        try:
            response = requests.get(url)
            response.raise_for_status()
            content = response.content
            # Try to guess extension from URL or content-type headers? 
            # For simplicity, check URL end.
            filename = url.split("?")[0].lower()
            return FileExtractionService._process_content(content, filename)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to download file from URL: {str(e)}")

    @staticmethod
    def _process_content(content: bytes, filename: str) -> str:
        file_obj = io.BytesIO(content)
        
        if filename.endswith('.pdf'):
            return FileExtractionService._extract_from_pdf(file_obj)
        elif filename.endswith('.docx') or filename.endswith('.doc'):
            if filename.endswith('.doc'):
                 raise HTTPException(status_code=400, detail="Legacy .doc format not supported. Please convert to .docx or PDF.")
            return FileExtractionService._extract_from_docx(file_obj)
        else:
            # Fallback or error
            raise HTTPException(status_code=400, detail="Unsupported file format. Please use PDF or DOCX.")

    @staticmethod
    def _extract_from_pdf(file_obj) -> str:
        try:
            reader = PyPDF2.PdfReader(file_obj)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            print(f"Error reading PDF: {e}")
            raise HTTPException(status_code=400, detail="Could not read PDF file content")

    @staticmethod
    def _extract_from_docx(file_obj) -> str:
        try:
            doc = docx.Document(file_obj)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            return text
        except Exception as e:
            print(f"Error reading DOCX: {e}")
            raise HTTPException(status_code=400, detail="Could not read DOCX file content")
