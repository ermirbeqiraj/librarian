from pathlib import Path

from librarian.adapters.readers.document_bytes import document_bytes

PDF = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF"


def test_unwraps_a_pdf_saved_with_its_form_data_upload(tmp_path: Path) -> None:
    path = tmp_path / "a.pdf"
    path.write_bytes(
        b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="a.pdf"\r\n'
        b"Content-Type: application/pdf\r\n\r\n" + PDF + b"\r\n\r\n--boundary--\r\n"
    )
    assert document_bytes(path) == PDF


def test_leaves_other_files_as_they_are(tmp_path: Path) -> None:
    path = tmp_path / "a.docx"
    path.write_bytes(b"PK\x03\x04 embeds " + PDF)
    assert document_bytes(path) == b"PK\x03\x04 embeds " + PDF
