import os
import uuid

FILE_SIGNATURES = {
    "pdf": b"%PDF-",
    "png": b"\x89PNG\r\n\x1a\n",
    "docx": b"PK\x03\x04",
}


def file_extension(filename):
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def is_valid_file(file, allowed_formats):
    extension = file_extension(file.filename)
    if extension not in allowed_formats:
        return False
    start = file.stream.read(8)
    file.stream.seek(0)
    return start.startswith(FILE_SIGNATURES[extension])


def save_upload(file, upload_folder):
    stored_name = f"{uuid.uuid4().hex}.{file_extension(file.filename)}"
    file.save(os.path.join(upload_folder, stored_name))
    return stored_name