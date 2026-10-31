from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import UnsupportedFileError
from app.core.security import ensure_within_directory, sanitize_filename
from app.utils.file_handlers import validate_upload
from app.utils.validators import is_valid_uuid, validate_marks


def test_uuid_validation():
    assert is_valid_uuid(str(uuid.uuid4()))
    assert not is_valid_uuid("123") and not is_valid_uuid("") and not is_valid_uuid(None)


def test_marks_validation():
    assert validate_marks(50, 100) == []
    assert validate_marks(101, 100) == ["Obtained marks exceed total marks."]
    assert validate_marks(None, 100)
    assert validate_marks(5, 0)


@pytest.mark.parametrize("name,content", [
    ("marks.csv", b"subject,obtained,total\nMath,50,100\n"),
    ("m.pdf", b"%PDF-1.7 ..."), ("m.png", b"\x89PNG\r\n\x1a\nxx"), ("m.jpg", b"\xff\xd8\xffxx"), ("m.xlsx", b"PK\x03\x04xx"),
])
def test_valid_uploads(name, content):
    assert validate_upload(name, content, 10)


@pytest.mark.parametrize("name,content", [
    ("m.exe", b"MZ"), ("m.pdf", b"not a pdf"), ("m.png", b"GIF89a"), ("m.csv", b""), ("m.csv", b"a\x00b"), ("noext", b"x"),
])
def test_rejected_uploads(name, content):
    with pytest.raises(UnsupportedFileError):
        validate_upload(name, content, 10)


def test_oversized_upload():
    with pytest.raises(UnsupportedFileError):
        validate_upload("m.csv", b"a" * (2 * 1024 * 1024), 1)


def test_filename_sanitizing_and_traversal(tmp_path):
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("my marks (1).csv") == "my_marks_1_.csv"
    with pytest.raises(UnsupportedFileError):
        ensure_within_directory(tmp_path, tmp_path.parent / "elsewhere.txt")


def test_pydantic_schemas():
    pytest.importorskip("pydantic")
    from pydantic import ValidationError

    from app.schemas.academic import AcademicResult
    from app.schemas.analysis import ImprovementRecommendation, Priority
    from app.schemas.chatbot import ChatRequest
    from app.schemas.student import StudentProfile

    profile = StudentProfile(name=" Ayesha ", board="AKU-EB", country="Pakistan", grade="HSSC 1", academic_year="2025")
    assert profile.name == "Ayesha"
    with pytest.raises(ValidationError):
        StudentProfile(name="  ", board="x", country="x", grade="x", academic_year="x")
    with pytest.raises(ValidationError):
        StudentProfile(name="A", board="x", country="x", grade="x", academic_year="x", target_percentage=120)
    with pytest.raises(ValidationError):
        AcademicResult(rows=[])
    with pytest.raises(ValidationError):
        ChatRequest(message="")
    with pytest.raises(ValidationError):
        ImprovementRecommendation(subject="Math", priority=Priority.HIGH, evidence="e", actions=[], goal="g")
