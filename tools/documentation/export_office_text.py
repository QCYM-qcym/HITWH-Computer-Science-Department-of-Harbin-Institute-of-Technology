"""从 DOCX/PPTX 抽取可审阅文本；不修改源文件或复现原排版。"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def text(node, namespace=W):
    return "".join(t.text or "" for t in node.iter(namespace + "t"))


def extract(source: Path) -> str:
    blocks = ["# " + source.stem, "此为正文抽取版，段落、表格及幻灯片文本供审阅；原稿排版和图片另行维护。"]
    with ZipFile(source) as archive:
        if source.suffix.lower() == ".docx":
            body = ET.fromstring(archive.read("word/document.xml")).find(W + "body")
            for node in body:
                if node.tag == W + "p":
                    value = text(node)
                    if value.strip():
                        blocks.append(value)
                elif node.tag == W + "tbl":
                    rows = [[text(cell).replace("|", "\\|").replace("\n", " ")
                             for cell in row.findall(W + "tc")] for row in node.findall(W + "tr")]
                    if rows:
                        width = max(map(len, rows))
                        rows = [row + [""] * (width - len(row)) for row in rows]
                        table = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
                        table += ["| " + " | ".join(row) + " |" for row in rows[1:]]
                        blocks.append("\n".join(table))
        elif source.suffix.lower() == ".pptx":
            names = sorted((n for n in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                           key=lambda n: int(re.search(r"(\d+)\.xml", n).group(1)))
            for number, name in enumerate(names, 1):
                slide = ET.fromstring(archive.read(name))
                hidden = "（隐藏备用页）" if slide.attrib.get("show") == "0" else ""
                blocks.append(f"## 第{number}页{hidden}")
                blocks += [text(p, A) for p in slide.iter(A + "p") if text(p, A).strip()]
        else:
            raise ValueError("仅支持DOCX与PPTX")
    return "\n\n".join(blocks) + "\n"


def redact(value: str, config: dict) -> str:
    for old, new in config.get("replacements", {}).items():
        value = value.replace(old, new)
    for term in config.get("deny_terms", []):
        if term:
            value = value.replace(term, "[已脱敏]")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--redactions", type=Path, required=True, help="本地脱敏配置，禁止公开提交")
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve():
        raise ValueError("输出路径须与源文件不同")
    config = json.loads(args.redactions.read_text(encoding="utf-8"))
    value = redact(extract(args.source), config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(value, encoding="utf-8")


if __name__ == "__main__":
    main()

