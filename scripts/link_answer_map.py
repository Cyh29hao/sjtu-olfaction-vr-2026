"""Add reversible in-deck Q&A navigation to the editable PPTX and its PDFs."""
import argparse
import json
import posixpath
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import fitz
from lxml import etree

from verify_release import NS, ordered_slides

REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
LABELS = {
    "S05": "理论到装置",
    "T02": "动作释香",
    "A02": "辨香难度",
    "A03": "在场感",
    "A04": "放松对照",
}


def link_specs():
    for i, (target, label) in enumerate(LABELS.items()):
        yield "QA", target, label, (247 + 191 * i, 620, 174, 31)
        yield target, "QA", "返回答辩总图", (1021, 12, 175, 33)


def xml_bytes(element):
    return etree.tostring(element, encoding="UTF-8", xml_declaration=True, standalone=True)


def add_button(slide, relationship, label, bounds):
    presentation = "{"+NS["p"]+"}"
    drawing = "{"+NS["a"]+"}"
    tree = slide.find("p:cSld/p:spTree", NS)
    shape_id = max(int(x) for x in tree.xpath(".//p:cNvPr/@id", namespaces=NS)) + 1
    shape = etree.SubElement(tree, presentation+"sp")
    nv = etree.SubElement(shape, presentation+"nvSpPr")
    props = etree.SubElement(nv, presentation+"cNvPr", id=str(shape_id), name="答辩导航 "+label)
    etree.SubElement(props, drawing+"hlinkClick", {"{"+REL+"}id": relationship, "action":"ppaction://hlinksldjump"})
    etree.SubElement(nv, presentation+"cNvSpPr", txBox="1")
    etree.SubElement(nv, presentation+"nvPr")
    style = etree.SubElement(shape, presentation+"spPr")
    transform = etree.SubElement(style, drawing+"xfrm")
    x, y, width, height = (str(round(coordinate*9525)) for coordinate in bounds)
    etree.SubElement(transform, drawing+"off", x=x, y=y)
    etree.SubElement(transform, drawing+"ext", cx=width, cy=height)
    geometry = etree.SubElement(style, drawing+"prstGeom", prst="rect")
    etree.SubElement(geometry, drawing+"avLst")
    fill = etree.SubElement(style, drawing+"solidFill")
    etree.SubElement(fill, drawing+"srgbClr", val="E9F2F8")
    body = etree.SubElement(shape, presentation+"txBody")
    etree.SubElement(body, drawing+"bodyPr", anchor="ctr", wrap="none", lIns="0", rIns="0", tIns="0", bIns="0")
    etree.SubElement(body, drawing+"lstStyle")
    paragraph = etree.SubElement(body, drawing+"p")
    etree.SubElement(paragraph, drawing+"pPr", algn="ctr")
    run = etree.SubElement(paragraph, drawing+"r")
    run_props = etree.SubElement(run, drawing+"rPr", lang="zh-CN", sz="1350", b="1")
    run_fill = etree.SubElement(run_props, drawing+"solidFill")
    etree.SubElement(run_fill, drawing+"srgbClr", val="175F8B")
    etree.SubElement(run_props, drawing+"latin", typeface="微软雅黑")
    etree.SubElement(run_props, drawing+"ea", typeface="微软雅黑")
    etree.SubElement(run, drawing+"t").text = label


def wire_pptx(source, target, slides):
    if source.resolve() == target.resolve():
        raise ValueError("Use separate source and output PPTX files")
    with ZipFile(source) as archive:
        order = ordered_slides(archive)
        parts = {name: archive.read(name) for name in archive.namelist()}
    by_id = dict(zip((slide["id"] for slide in slides), order, strict=True))
    for page_id, destination, label, bounds in link_specs():
        part = by_id[page_id]
        folder, name = posixpath.split(part)
        rel_part = posixpath.join(folder, "_rels", name+".rels")
        rels = etree.fromstring(parts[rel_part])
        rel_id = "rId"+str(max((int(r.get("Id")[3:]) for r in rels if r.get("Id","")[3:].isdigit()), default=0)+1)
        slide = etree.fromstring(parts[part])
        if slide.xpath(f'//p:cNvPr[@name="答辩导航 {label}"]', namespaces=NS):
            raise ValueError(f"Duplicate Q&A button on {page_id}: {label}")
        etree.SubElement(rels, "{"+PACKAGE_REL+"}Relationship", Id=rel_id, Type=REL+"/slide",
                         Target=posixpath.relpath(by_id[destination], folder))
        add_button(slide, rel_id, label, bounds)
        parts[part] = xml_bytes(slide)
        parts[rel_part] = xml_bytes(rels)
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)


def wire_pdf(source, target, slides, main_only=False):
    if source.resolve() == target.resolve():
        raise ValueError("Use separate source and output PDF files")
    if main_only:
        slides = [slide for slide in slides if slide["role"] != "backup"]
    page_index = {slide["id"]: index for index, slide in enumerate(slides)}
    with fitz.open(source) as document:
        if document.page_count != len(slides):
            raise ValueError("PDF page count differs from slide sequence")
        affected = {page_index[src] for src, _, _, _ in link_specs()}
        for index in affected:
            page = document[index]
            for existing in page.get_links():
                if existing["kind"] == fitz.LINK_GOTO:
                    page.delete_link(existing)
        for page_id, destination, _, (x,y,w,h) in link_specs():
            page = document[page_index[page_id]]
            sx, sy = page.rect.width/1280, page.rect.height/720
            page.insert_link({"kind":fitz.LINK_GOTO,
                              "from":fitz.Rect(x*sx,y*sy,(x+w)*sx,(y+h)*sy),
                              "page":page_index[destination], "to":fitz.Point(0,0)})
        document.save(target, garbage=3, deflate=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--deck", type=Path, default=Path("content/deck.json"))
    parser.add_argument("--main-only", action="store_true")
    args = parser.parse_args()
    slides = json.loads(args.deck.read_text(encoding="utf-8"))["slides"]
    if args.input.suffix.lower() == ".pptx":
        wire_pptx(args.input, args.output, slides)
    else:
        wire_pdf(args.input, args.output, slides, args.main_only)


if __name__ == "__main__":
    main()
