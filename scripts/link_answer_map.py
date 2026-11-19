"""Wire title links, discreet return icons, and matching PDF destinations."""
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
DRAW = "{"+NS["a"]+"}"
PRES = "{"+NS["p"]+"}"
JUMP = "ppaction://hlinksldjump"


def link_specs(slides):
    by_id = {s["id"]:s for s in slides}
    overview = by_id["QA"]["map_rows"]
    targets = [item["target"] for item in overview]
    assert len(targets) == len(set(targets))
    for item in overview:
        content = by_id[item["target"]]
        backup = by_id[content["backup"]["target"]]
        assert backup["role"] == "backup", backup["id"]
        yield "QA", content["id"], item["anchor"], None
        yield content["id"], "QA", "nav-home", (1195, 10, 41, 39)
        yield content["id"], backup["id"], content["backup"]["anchor"], None
        yield backup["id"], "QA", "nav-home", (1195, 10, 41, 39)
        yield backup["id"], content["id"], "nav-back", (1150, 10, 41, 39)


def xml_bytes(element):
    return etree.tostring(element, encoding="UTF-8", xml_declaration=True, standalone=True)


def rel_path(part):
    folder, name = posixpath.split(part)
    return posixpath.join(folder, "_rels", name+".rels")


def named_shape(slide, name):
    shapes = slide.xpath("./p:cSld/p:spTree/p:sp[p:nvSpPr/p:cNvPr[@name=$n]]", namespaces=NS, n=name)
    if len(shapes) != 1:
        raise ValueError(f"Expected one {name!r} text shape, found {len(shapes)}")
    return shapes[0]


def add_icon(slide, name, bounds):
    tree = slide.find("p:cSld/p:spTree", NS)
    shape_id = max(int(x) for x in tree.xpath(".//p:cNvPr/@id", namespaces=NS)) + 1
    shape = etree.SubElement(tree, PRES+"sp")
    nv = etree.SubElement(shape, PRES+"nvSpPr")
    title = "返回答辩总图" if name == "nav-home" else "返回主讲页"
    etree.SubElement(nv, PRES+"cNvPr", id=str(shape_id), name=name, title=title, descr=title)
    etree.SubElement(nv, PRES+"cNvSpPr", txBox="1")
    etree.SubElement(nv, PRES+"nvPr")
    style = etree.SubElement(shape, PRES+"spPr")
    transform = etree.SubElement(style, DRAW+"xfrm")
    x, y, width, height = (str(round(v*9525)) for v in bounds)
    etree.SubElement(transform, DRAW+"off", x=x, y=y)
    etree.SubElement(transform, DRAW+"ext", cx=width, cy=height)
    geometry = etree.SubElement(style, DRAW+"prstGeom", prst="roundRect")
    etree.SubElement(geometry, DRAW+"avLst")
    fill = etree.SubElement(style, DRAW+"solidFill")
    etree.SubElement(fill, DRAW+"srgbClr", val="F2F6F7")
    body = etree.SubElement(shape, PRES+"txBody")
    etree.SubElement(body, DRAW+"bodyPr", anchor="ctr", wrap="none", lIns="0", rIns="0", tIns="0", bIns="0")
    etree.SubElement(body, DRAW+"lstStyle")
    paragraph = etree.SubElement(body, DRAW+"p")
    etree.SubElement(paragraph, DRAW+"pPr", algn="ctr")
    run = etree.SubElement(paragraph, DRAW+"r")
    props = etree.SubElement(run, DRAW+"rPr", lang="en-US", sz="1450")
    etree.SubElement(etree.SubElement(props, DRAW+"solidFill"), DRAW+"srgbClr", val="48636D")
    etree.SubElement(props, DRAW+"latin", typeface="Segoe UI Symbol")
    etree.SubElement(run, DRAW+"t").text = "⌂" if name == "nav-home" else "←"
    return shape


def wire_pptx(source, target, slides):
    with ZipFile(source) as archive:
        order = ordered_slides(archive)
        parts = {name: archive.read(name) for name in archive.namelist()}
    by_id = dict(zip((s["id"] for s in slides), order, strict=True))
    for page, destination, name, bounds in link_specs(slides):
        part = by_id[page]
        rel_part = rel_path(part)
        rels = etree.fromstring(parts[rel_part])
        ids = [int(r.get("Id")[3:]) for r in rels if r.get("Id","")[3:].isdigit()]
        rid = "rId"+str(max(ids, default=0)+1)
        slide = etree.fromstring(parts[part])
        shape = add_icon(slide, name, bounds) if bounds else named_shape(slide, name)
        props = shape.find("p:nvSpPr/p:cNvPr", NS)
        assert props.find("a:hlinkClick", NS) is None, (page, name)
        click = etree.Element(DRAW+"hlinkClick", {"{"+REL+"}id":rid, "action":JUMP}, tooltip=destination)
        props.insert(0, click)  # DrawingML requires the action before the extension list.
        etree.SubElement(rels, "{"+PACKAGE_REL+"}Relationship", Id=rid, Type=REL+"/slide",
                         Target=posixpath.relpath(by_id[destination], posixpath.dirname(part)))
        parts[part] = xml_bytes(slide)
        parts[rel_part] = xml_bytes(rels)
    with ZipFile(target, "w", ZIP_DEFLATED) as archive:
        for part, data in parts.items():
            archive.writestr(part, data)


def resolved_links(pptx, slides):
    with ZipFile(pptx) as archive:
        by_id = dict(zip((s["id"] for s in slides), ordered_slides(archive), strict=True))
        size = etree.fromstring(archive.read("ppt/presentation.xml")).find("p:sldSz", NS)
        width, height = (float(size.get(k)) for k in ("cx","cy"))
        for page, destination, name, _ in link_specs(slides):
            part = by_id[page]
            root = etree.fromstring(archive.read(part))
            shape = named_shape(root, name)
            click = shape.find("p:nvSpPr/p:cNvPr/a:hlinkClick", NS)
            assert click is not None and click.get("action") == JUMP, (page, name)
            rid = click.get("{"+REL+"}id")
            rels = etree.fromstring(archive.read(rel_path(part)))
            rel = next(r for r in rels if r.get("Id") == rid)
            target = posixpath.normpath(posixpath.join(posixpath.dirname(part), rel.get("Target")))
            assert target == by_id[destination], (page, name, destination)
            transform = shape.find("p:spPr/a:xfrm", NS)
            offset, extent = transform.find("a:off", NS), transform.find("a:ext", NS)
            x0, y0 = (int(offset.get(k)) for k in ("x","y"))
            w, h = (int(extent.get(k)) for k in ("cx","cy"))
            assert 0 <= x0 < x0+w <= width and 0 <= y0 < y0+h <= height, (page, name)
            yield page, destination, name, (x0/width, y0/height, (x0+w)/width, (y0+h)/height)


def wire_pdf(source, target, pptx, slides, main_only=False):
    page_index = {s["id"]:i for i, s in enumerate(
        s for s in slides if not main_only or s["role"] != "backup"
    )}
    links = [item for item in resolved_links(pptx, slides) if item[0] in page_index and item[1] in page_index]
    with fitz.open(source) as document:
        if document.page_count != len(page_index):
            raise ValueError("PDF page count differs from slide sequence")
        for index in set(page_index[page] for page, _, _, _ in links):
            page = document[index]
            for item in page.get_links():
                if item["kind"] == fitz.LINK_GOTO:
                    page.delete_link(item)
        for origin, destination, _, (x0,y0,x1,y1) in links:
            page = document[page_index[origin]]
            w,h = page.rect.width,page.rect.height
            page.insert_link({"kind":fitz.LINK_GOTO, "from":fitz.Rect(x0*w,y0*h,x1*w,y1*h),
                              "page":page_index[destination], "to":fitz.Point(0,0)})
        document.save(target, garbage=3, deflate=True)
    with fitz.open(target) as document:
        for s, t, name, (x0,y0,x1,y1) in links:
            page = document[page_index[s]]
            match = fitz.Rect(x0*page.rect.width,y0*page.rect.height,x1*page.rect.width,y1*page.rect.height)
            actual = [l for l in page.get_links() if l["kind"]==fitz.LINK_GOTO
                      and l["page"]==page_index[t] and (l["from"]&match).get_area() > match.get_area()*.98]
            assert len(actual)==1, (s,t,name)
    return len(links)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--deck", type=Path, default=Path("content/deck.json"))
    parser.add_argument("--pptx", type=Path, help="Wired editable PPTX used for matching PDF links")
    parser.add_argument("--main-only", action="store_true")
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("Input and output must be separate files")
    slides = json.loads(args.deck.read_text(encoding="utf-8"))["slides"]
    if args.input.suffix.lower() == ".pptx":
        wire_pptx(args.input, args.output, slides)
        print(len(list(resolved_links(args.output, slides))), "PowerPoint navigation targets verified")
    elif args.pptx is not None:
        print(wire_pdf(args.input, args.output, args.pptx, slides, args.main_only), "PDF navigation targets verified")
    else:
        parser.error("--pptx is required for PDF output")


if __name__ == "__main__":
    main()
