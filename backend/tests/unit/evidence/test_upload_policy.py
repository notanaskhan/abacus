"""DEC-296 (DEC-58 c, Q-03-T016; ED-018 to ED-021): what an upload may be.

The bytes decide the type, the type must be on the allowlist and the name's extension must agree;
text is `text/csv` only when it parses as CSV; a PDF with active content is recognised (and kept,
never derived from); HEIC is recognised and kept as-is.
"""

from __future__ import annotations

import io
import zipfile
import zlib

import pytest

from abacus.modules.evidence.active_content import markers, reason_of
from abacus.modules.evidence.checks import ExtractedFields, active_content
from abacus.modules.evidence.extraction import extract
from abacus.modules.evidence.previews import render
from abacus.modules.evidence.uploads import (
    CSV,
    DOCM,
    GIF,
    HEIC,
    HEIF,
    MAX_UPLOAD_BYTES,
    PDF,
    TIFF,
    UPLOAD_EDGE_BYTES,
    UPLOAD_ROUTE_PATHS,
    XLSM,
    XLSX,
    UploadTooLarge,
    UploadTypeNotAllowed,
    allowed_type,
    checked,
    sniff,
)
from abacus.modules.evidence.words import extract_words
from abacus_tools.synthetic.documents import bank_statement_pdf

# A fixed timestamp: the bytes (and so the test ids made from them) don't depend on when the
# module was collected, so every pytest-xdist worker collects the same tests (DEC-335).
_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def _entry(name: str) -> zipfile.ZipInfo:
    return zipfile.ZipInfo(name, date_time=_ZIP_TIME)


def _zip(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        for name in names:
            package.writestr(_entry(name), "<x/>")
    return buffer.getvalue()


HEIC_BYTES = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + bytes(64)
HEIF_BYTES = b"\x00\x00\x00\x14ftypmif1\x00\x00\x00\x00mif1" + bytes(64)
TIFF_BYTES = b"II*\x00\x08\x00\x00\x00" + bytes(64)
GIF_BYTES = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"


def test_the_limit_is_50_mb_and_the_edge_leaves_the_route_room_to_answer() -> None:
    assert MAX_UPLOAD_BYTES == 50 * 1024 * 1024
    assert UPLOAD_EDGE_BYTES > MAX_UPLOAD_BYTES
    with pytest.raises(UploadTooLarge):
        checked(b"%PDF-1.4\n" + bytes(MAX_UPLOAD_BYTES), "statement.pdf")
    for path in (
        "/v1/engagements/e/request-items/i/uploads",
        "/v1/engagements/e/inbox",
        "/v1/engagements/e/acceptance/file",
        "/v1/engagements/e/letter/file",
    ):
        assert UPLOAD_ROUTE_PATHS.fullmatch(path), path
    assert not UPLOAD_ROUTE_PATHS.fullmatch("/v1/engagements")
    assert not UPLOAD_ROUTE_PATHS.fullmatch("/v1/engagements/e/request-items/i/uploads/x")


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (HEIC_BYTES, HEIC),
        (HEIF_BYTES, HEIF),
        (TIFF_BYTES, TIFF),
        (b"MM\x00*" + bytes(16), TIFF),
        (GIF_BYTES, GIF),
        (_zip("[Content_Types].xml", "xl/workbook.xml", "xl/vbaProject.bin"), XLSM),
        (_zip("[Content_Types].xml", "word/document.xml", "word/vbaProject.bin"), DOCM),
        (b"date;amount\n2025-12-31;100.00\n", CSV),
        (b"\xef\xbb\xbfaccount\tamount\n1100\t5\n", CSV),
    ],
)
def test_types_are_recognised_by_their_bytes(content: bytes, expected: str) -> None:
    assert sniff(content) == expected


@pytest.mark.parametrize(
    "content",
    [
        b"<html><script>alert(1)</script></html>",
        b'  <svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        b"<?xml version='1.0'?><a,b/>",
        b"alert(1)",
        b"Dear Sir\nPlease find attached\n",
        b'a,"b\n',  # an unterminated quote does not parse strictly
    ],
)
def test_text_that_is_not_csv_is_not_kept_as_csv(content: bytes) -> None:
    assert sniff(content) != CSV


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("statement.pdf", bank_statement_pdf()),
        ("STATEMENT.PDF", bank_statement_pdf()),
        ("IMG_0412.HEIC", HEIC_BYTES),
        ("photo.heif", HEIF_BYTES),
        ("scan.tif", TIFF_BYTES),
        ("scan.tiff", TIFF_BYTES),
        ("logo.gif", GIF_BYTES),
        ("trial balance.csv", b"account,amount\n1100,5\n"),
        ("aging.xlsx", _zip("[Content_Types].xml", "xl/workbook.xml")),
        ("letter.docx", _zip("[Content_Types].xml", "word/document.xml")),
    ],
)
def test_an_allowed_type_with_an_agreeing_name_is_kept(name: str, content: bytes) -> None:
    assert allowed_type(content, name) == sniff(content)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("statement.html", bank_statement_pdf()),  # the bytes are a PDF, the name is not
        ("statement", bank_statement_pdf()),  # no extension at all
        ("aging.pdf", _zip("[Content_Types].xml", "xl/workbook.xml")),
        ("aging.xlsm", _zip("[Content_Types].xml", "xl/workbook.xml")),
        ("aging.xlsx", _zip("[Content_Types].xml", "xl/workbook.xml", "xl/vbaProject.bin")),
        ("letter.docm", _zip("[Content_Types].xml", "word/document.xml")),
        ("letter.doc", bytes.fromhex("d0cf11e0a1b11ae1") + bytes(64)),
        ("book.xls", bytes.fromhex("d0cf11e0a1b11ae1") + bytes(64)),
        ("notes.txt", b"account,amount\n1100,5\n"),
        ("run.csv", b"alert(1)"),
        ("page.csv", b"<html><body>a,b</body></html>"),
        ("photo.png", b"<html><body onload=alert(1)></body></html>"),
    ],
)
def test_anything_else_is_refused(name: str, content: bytes) -> None:
    with pytest.raises(UploadTypeNotAllowed):
        allowed_type(content, name)


def _objstm_pdf(inner: bytes) -> bytes:
    body = zlib.compress(inner)
    return (
        b"%PDF-1.5\n4 0 obj\n<< /Type /ObjStm /N 1 /First 4 /Filter /FlateDecode /Length "
        + str(len(body)).encode()
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n%%EOF\n"
    )


@pytest.mark.parametrize(
    ("content", "found"),
    [
        (b"%PDF-1.7\n<< /OpenAction 5 0 R >> << /S /JavaScript /JS (x) >>", "javascript"),
        (b"%PDF-1.7\n<< /Names << /J#61vaScript 3 0 R >> >>", "javascript"),
        (b"%PDF-1.7\n<< /AA << /O << /S /Launch /F (cmd.exe) >> >> >>", "launch_action"),
        (b"%PDF-1.7\n<< /Names << /EmbeddedFiles 2 0 R >> >>", "embedded_file"),
        (_objstm_pdf(b"<< /S /JavaScript /JS (app.alert(1)) >>"), "javascript"),
    ],
)
def test_active_content_is_found_however_it_is_spelled(content: bytes, found: str) -> None:
    assert reason_of(content) == found


def test_a_plain_statement_and_a_view_action_are_not_active_content() -> None:
    assert markers(bank_statement_pdf()) == ()
    assert markers(b"%PDF-1.7\n<< /OpenAction [3 0 R /Fit] >>") == ()
    assert markers(b"not a pdf /JavaScript") == ()


def test_an_active_pdf_is_never_extracted_rendered_or_read_for_words() -> None:
    content = bank_statement_pdf() + b"\n<< /OpenAction << /S /JavaScript /JS (x) >> >>\n"
    assert (extract(content, PDF).status, extract(content, PDF).reason) == (
        "not_extracted",
        "active_content",
    )
    assert (render(content, PDF).kind, render(content, PDF).reason) == ("none", "active_content")
    assert extract_words(content, PDF).status == "not_applicable"
    fields = ExtractedFields("not_extracted", "active_content", *([None] * 8))
    flag = active_content(fields)
    assert flag is not None
    assert (flag.code, flag.outcome, flag.audience) == ("active_content", "problem", "firm")


def test_heic_is_kept_not_extracted_with_a_reason_and_not_previewed() -> None:
    assert (extract(HEIC_BYTES, HEIC).status, extract(HEIC_BYTES, HEIC).reason) == (
        "not_extracted",
        "format_not_supported",
    )
    assert render(HEIC_BYTES, HEIC).kind == "none"


def test_xlsx_is_still_extracted_by_its_name() -> None:
    assert allowed_type(_zip("[Content_Types].xml", "xl/workbook.xml"), "a.xlsx") == XLSX


# --- security review (DEC-299): fail closed, more forms, bounded, Office packages ---------------


def _objstm(
    body: bytes, header: bytes = b"/Filter /FlateDecode", length: bytes | None = None
) -> bytes:
    size = length if length is not None else str(len(body)).encode()
    return (
        b"%PDF-1.5\n4 0 obj\n<< /Type /ObjStm /N 1 /First 4 "
        + header
        + b" /Length "
        + size
        + b" >>\nstream\n"
        + body
        + b"\nendstream\nendobj\n%%EOF\n"
    )


@pytest.mark.parametrize(
    "content",
    [
        _objstm(b"3c3c202f4a53203e3e", b"/Filter /ASCIIHexDecode"),  # a filter it doesn't decode
        _objstm(b"<~...~>", b"/Filter /ASCII85Decode"),
        _objstm(b"\x80\x0b", b"/Filter /LZWDecode"),
        _objstm(zlib.compress(b"x"), b"/Filter [/FlateDecode /ASCIIHexDecode]"),  # a chain
        _objstm(zlib.compress(b"x"), b"/Filter /FlateDecode /DecodeParms << /Predictor 12 >>"),
        _objstm(b"not deflate data", b"/Filter /FlateDecode"),  # decompression error
        _objstm(zlib.compress(b"x"), length=b"9 0 R"),  # an indirect length
        _objstm(zlib.compress(b"x") + b"endstream junk", length=b"3"),  # a length that lies
        b"%PDF-1.5\n4 0 obj << /Foo (obj) /Type /ObjStm /Filter /LZWDecode /Length 2 >>\n"
        b"stream\nab\nendstream\n",  # `(obj)` before /ObjStm
        b"%PDF-1.5\n4 0 obj << /Foo (an unterminated string /Type /ObjStm >>\nstream\n",
    ],
)
def test_dec299_an_object_stream_it_cannot_fully_decode_is_flagged(content: bytes) -> None:
    assert markers(content) == ("unscannable",)


def test_dec299_too_many_object_streams_is_flagged_and_bounded_in_time() -> None:
    import time

    one = _objstm(zlib.compress(b"<< /Type /Font >>"))[len(b"%PDF-1.5\n") :]
    content = b"%PDF-1.5\n" + one * 3000
    started = time.monotonic()
    assert markers(content) == ("unscannable",)
    assert time.monotonic() - started < 5


@pytest.mark.parametrize(
    ("content", "found"),
    [
        (b"%PDF-1.7\n1 0 obj << /S /javascript >> endobj", "javascript"),  # case
        (b"%PDF-1.7\n1 0 obj << /XFA 3 0 R >> endobj", "xfa_form"),
        (b"%PDF-1.7\n1 0 obj << /Subtype /RichMedia >> endobj", "rich_media"),
        (b"%PDF-1.7\n1 0 obj << /S /GoToE /T << /R /C >> >> endobj", "goto_embedded"),
        (b"%PDF-1.7\n1 0 obj << /S /SubmitForm /F (x) >> endobj", "submit_form"),
        (b"%PDF-1.7\n1 0 obj << /S /ImportData >> endobj", "import_data"),
        (
            b"%PDF-1.7\n1 0 obj << /Subtype /FileAttachment "
            b"/FS << /EF << /F 4 0 R >> >> >> endobj",
            "embedded_file",
        ),
        (b"%PDF-1.7\n1 0 obj << /S /L#61unch >> endobj", "launch_action"),
    ],
)
def test_dec299_more_forms_of_active_content_are_found(content: bytes, found: str) -> None:
    assert reason_of(content) == found


def test_dec299_a_scan_that_dies_or_overruns_is_flagged(monkeypatch: pytest.MonkeyPatch) -> None:
    from abacus.kernel.isolation import IsolationFailed
    from abacus.modules.evidence import uploads

    def dies(*_args: object, **_kwargs: object) -> object:
        raise IsolationFailed

    monkeypatch.setattr(uploads, "run_isolated_with", dies)
    assert uploads.active_content_of(bank_statement_pdf()) == "unscannable"


def _office(main: str, parts: list[tuple[str, bytes]], types: bytes = b"") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as package:
        package.writestr(
            _entry("[Content_Types].xml"),
            b'<?xml version="1.0"?><Types><Override PartName="/x" ContentType="'
            + (types or b"application/xml")
            + b'"/></Types>',
        )
        package.writestr(_entry(main), "<x/>")
        for name, data in parts:
            package.writestr(_entry(name), data)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            _office(
                "xl/workbook.xml", [], b"application/vnd.ms-excel.sheet.macroEnabled.main+xml"
            ),
            XLSM,
        ),
        (_office("xl/workbook.xml", [("XL/VBAPROJECT.BIN", b"\xd0\xcf")]), XLSM),  # any case
        (_office("xl/workbook.xml", [("xl/macrosheets/sheet1.xml", b"<x/>")]), XLSM),
        (_office("word/document.xml", [("word/activeX/activeX1.xml", b"<x/>")]), DOCM),
        (_office("word/document.xml", [("word/embeddings/oleObject1.bin", b"\xd0")]), DOCM),
        (
            _office(
                "word/document.xml",
                [
                    (
                        "word/_rels/settings.xml.rels",
                        b'<Relationships><Relationship Id="r1" Target="http://x.invalid/t.dotm" '
                        b'TargetMode="External"/></Relationships>',
                    )
                ],
            ),
            DOCM,  # a remote template
        ),
        (
            _office(
                "word/document.xml",
                [
                    (
                        "word/_rels/settings.xml.rels",
                        b'<Relationships><Relationship Id="r1" Type="http://schemas.openxmlformats'
                        b'.org/officeDocument/2006/relationships/attachedTemplate" '
                        b'Target="http://x.invalid/t.dotm" TargetMode="External"/>'
                        b"</Relationships>",
                    )
                ],
            ),
            DOCM,  # a remote template, typed
        ),
        (
            _office(
                "xl/workbook.xml",
                [
                    (
                        "xl/worksheets/_rels/sheet1.xml.rels",
                        b'<Relationships><Relationship Id="r1" Type="http://schemas.openxmlformats'
                        b'.org/officeDocument/2006/relationships/hyperlink" '
                        b'Target="https://x.invalid/statement" TargetMode="External"/>'
                        b"</Relationships>",
                    )
                ],
            ),
            XLSX,  # an ordinary hyperlink is not code
        ),
        (
            _office(
                "xl/workbook.xml",
                [
                    (
                        "xl/worksheets/_rels/sheet1.xml.rels",
                        b'<Relationships><Relationship Id="r1" Type="http://schemas.openxmlformats'
                        b'.org/officeDocument/2006/relationships/hyperlink" '
                        b'Target="https://x.invalid/a" TargetMode="External"/>'
                        b'<Relationship Id="r2" Type="http://schemas.openxmlformats.org/'
                        b'officeDocument/2006/relationships/oleObject" '
                        b'Target="file:///x.invalid/o.bin" TargetMode="External"/>'
                        b"</Relationships>",
                    )
                ],
            ),
            XLSM,  # a hyperlink beside an external OLE link
        ),
        (_office("xl/workbook.xml", []), XLSX),  # the control
        (
            _office("word/document.xml", []),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_dec299_office_packages_with_code_or_external_links_are_macro_enabled(
    content: bytes, expected: str
) -> None:
    assert sniff(content) == expected
