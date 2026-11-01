from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private"


def retrieve(record):
    identifier = record["id"]
    if not record.get("pmcid"):
        return {"id": identifier, "status": "no_pmc_fulltext_id"}
    url = f'https://www.ebi.ac.uk/europepmc/webservices/rest/{record["pmcid"]}/fullTextXML'
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "OlfactionCourseResearch/1.0"})
        with urllib.request.urlopen(request, timeout=18) as response:
            raw = response.read()
        article = ET.fromstring(raw)
        (PRIVATE / (identifier + "-fulltext.xml")).write_bytes(raw)
        passages = []
        for element in article.findall(".//body//sec"):
            title = " ".join(element.findtext("title", "").split())
            for para in element.findall("p"):
                text = " ".join(" ".join(para.itertext()).split())
                if text:
                    passages.append({"section": title, "text": text})
        license_text = " ".join(" ".join(article.find(".//permissions").itertext()).split()) if article.find(".//permissions") is not None else "License not extracted"
        result = {"id": identifier, "status": "original_xml_accessed", "url": url,
                  "license": license_text, "paragraphs": passages}
        (PRIVATE / (identifier + "-passages.json")).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return {k: v for k, v in result.items() if k != "paragraphs"} | {"paragraph_count": len(passages)}
    except Exception as exc:
        return {"id": identifier, "status": "fulltext_access_failed", "error": type(exc).__name__, "url": url}


if __name__ == "__main__":
    selected = {"P02", "P03", "P10", "P12", "P13", "P14", "P19", "P21", "P26"}
    records = json.loads((PRIVATE / "metadata.json").read_text(encoding="utf-8"))
    result = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for task in as_completed([executor.submit(retrieve, p) for p in records if p["id"] in selected]):
            item = task.result()
            result.append(item)
            print(json.dumps(item, ensure_ascii=False), flush=True)
    (PRIVATE / "fulltext-access.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
