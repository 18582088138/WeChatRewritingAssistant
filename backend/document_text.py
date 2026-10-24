"""Read bounded Word document text without extracting or executing archive contents."""

import io
import zipfile
import xml.etree.ElementTree as ET


def docx_text(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        item = archive.getinfo("word/document.xml")
        if item.file_size > 6_000_000:
            raise ValueError("Word 文档正文解压后超过 6 MB")
        xml = archive.read(item)
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("Word 文档包含不支持的 XML 声明")
    root = ET.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    return "\n".join("".join(p.itertext()) for p in root.findall(".//w:p", namespace))
