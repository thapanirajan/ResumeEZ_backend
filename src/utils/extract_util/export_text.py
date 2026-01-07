from typing import Any

import PyPDF2

def extract_text_from_pdf(pdf_file: str) -> list[Any]:
    with open(pdf_file,'rb') as pdf:
        reader = PyPDF2.PdfReader(pdf,strict=False)
        pdf_text = []
        for page in reader.pages:
            content = page.extract_text()
            pdf_text.append(content)
        return  pdf_text

if '__main__' == __name__:
    extracted_text = extract_text_from_pdf('resume.pdf')
    for text in extracted_text:
        print(text)