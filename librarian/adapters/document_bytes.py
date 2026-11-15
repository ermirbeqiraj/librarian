from pathlib import Path

FORM_DATA = b"Content-Disposition: form-data"
PDF_START = b"%PDF-"
PDF_END = b"%%EOF"


def document_bytes(path: Path) -> bytes:
    """The file's bytes, or the PDF inside it when a download saved the whole form-data upload."""
    data = path.read_bytes()
    if not data.startswith(b"--") or FORM_DATA not in data[:1024]:
        return data
    start = data.find(PDF_START)
    end = data.rfind(PDF_END)
    if start < 0 or end < start:
        return data
    return data[start : end + len(PDF_END)]
