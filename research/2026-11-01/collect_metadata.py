"""Fetch bibliographic records from DOI registries and Europe PMC; no credentials."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private"
PRIVATE.mkdir(exist_ok=True)
SEEDS = [
    ("P01", "10.1145/3665243", "综述与设计地图"),
    ("P02", "10.1038/s41467-023-37678-4", "设备与气味释放"),
    ("P03", "10.1038/s41467-024-48884-z", "设备与气味释放"),
    ("P04", "10.1038/s41467-024-50261-9", "设备与气味释放"),
    ("P05", "10.1016/j.ijhcs.2022.102928", "设备与气味释放"),
    ("P06", "10.1007/s11042-015-2971-0", "可复用装置与HCI"),
    ("P07", "10.1541/ieejsmas.128.451", "综述与设计地图"),
    ("P08", "10.1541/ieejsmas.138.337", "设备与增强嗅觉"),
    ("P09", "10.1016/S0092-8674(00)80581-4", "嗅觉编码与数字化"),
    ("P10", "10.1126/science.ade4401", "嗅觉编码与数字化"),
    ("P11", "10.1126/science.1249168", "嗅觉编码与争议"),
    ("P12", "10.7554/eLife.07865", "嗅觉编码与争议"),
    ("P13", "10.3389/frvir.2020.571812", "多感官与在场感"),
    ("P14", "10.1177/2041669521989731", "多感官与记忆"),
    ("P15", "10.1016/j.chb.2015.08.007", "放松与健康边界"),
    ("P16", "10.1177/17456916211014196", "放松与健康边界"),
    ("P17", "10.1016/j.buildenv.2025.112608", "建筑与真实场景"),
    ("P18", "10.1016/j.vrih.2025.10.001", "建筑与真实场景"),
    ("P19", "10.3389/fnins.2023.1200448", "嗅觉训练与健康边界"),
    ("P20", "10.1002/lary.20101", "嗅觉训练与健康边界"),
    ("P21", "10.1007/s00405-025-09936-2", "嗅觉训练与健康边界"),
    ("P22", "10.1109/ACCESS.2025.3622742", "临床综述"),
    ("P23", "10.1145/2556288.2557008", "可复用装置与HCI"),
    ("P24", "10.3390/mti10080085", "游戏与在场感"),
    ("P25", "10.2312/egve.20241374", "设备与气味释放"),
    ("P26", "10.1038/s41598-019-46099-7", "自然场景与放松"),
    ("P27", "10.1109/VR.1999.756955", "多感官与记忆"),
    ("P28", "10.48550/arXiv.2507.07911", "前沿预印本-压力"),
    ("P29", "10.48550/arXiv.2604.07699", "前沿预印本-训练"),
    ("P30", "10.48550/arXiv.2609.32975", "前沿预印本-导航"),
    ("P31", "10.48550/arXiv.2609.32992", "前沿预印本-导航"),
    ("P32", "10.48550/arXiv.2509.11342", "前沿预印本-社交"),
    ("P33", "10.48550/arXiv.2509.11347", "前沿预印本-导航"),
    ("P34", "10.1016/0092-8674(91)90418-X", "嗅觉科学基础"),
]


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "OlfactionCourseResearch/1.0 (bibliographic verification)"})
    with urllib.request.urlopen(request, timeout=18) as response:
        return json.load(response)


def collect(seed):
    identifier, doi, topic = seed
    item = {"id": identifier, "doi": doi, "topic": topic,
            "doi_url": "https://doi.org/" + doi,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "errors": []}
    if "arxiv" in doi.lower():
        item.update(status="preprint_metadata_pending", url="https://arxiv.org/abs/" + doi.split("arXiv.", 1)[1])
        return item
    try:
        url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
        message = get_json(url)["message"]
        (PRIVATE / (identifier + "-crossref.json")).write_text(json.dumps(message, ensure_ascii=False, indent=2), encoding="utf-8")
        item.update(title=" ".join(message.get("title", [])), authors=message.get("author", []),
                    venue="; ".join(message.get("container-title", [])), type=message.get("type"),
                    published=message.get("published", {}).get("date-parts", []),
                    license=message.get("license", []), links=message.get("link", []),
                    metadata_source=url, status="doi_metadata_verified")
        if message.get("abstract"):
            item["abstract_text"] = re.sub(r"<[^>]+>", " ", message["abstract"])
            item["abstract_source"] = "Crossref publisher-deposited abstract"
    except Exception as exc:
        item["errors"].append("Crossref: " + type(exc).__name__)
        item["status"] = "metadata_not_verified"
    try:
        query = urllib.parse.urlencode({"query": 'DOI:"' + doi + '"', "format": "json", "resultType": "core"})
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?" + query
        records = get_json(url).get("resultList", {}).get("result", [])
        if records:
            record = records[0]
            (PRIVATE / (identifier + "-europepmc.json")).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            item["pmid"] = record.get("id")
            item["pmcid"] = record.get("pmcid")
            item["europepmc_source"] = url
            if record.get("abstractText"):
                item["abstract_text"] = re.sub(r"<[^>]+>", " ", record["abstractText"])
                item["abstract_source"] = "Europe PMC indexed original abstract"
    except Exception as exc:
        item["errors"].append("Europe PMC: " + type(exc).__name__)
    (PRIVATE / (identifier + "-record.json")).write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    return item


if __name__ == "__main__":
    result = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        for task in as_completed([executor.submit(collect, seed) for seed in SEEDS]):
            item = task.result()
            result.append(item)
            print(item["id"], item["status"], item.get("title", ""), flush=True)
    result.sort(key=lambda item: item["id"])
    (PRIVATE / "metadata.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Verified:", sum(item["status"] == "doi_metadata_verified" for item in result), "of", len(result))
