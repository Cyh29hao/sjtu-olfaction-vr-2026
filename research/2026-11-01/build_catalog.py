"""Build an auditable local reading pack; publication requires user approval."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / "private"

# These are reading notes, not substituted abstracts or unverified experimental results.
NOTES = {
"P01": ("分类综述", "核心地图", "归纳面向 HMD/CAVE 的嗅觉显示系统及设计挑战。", "先复用已有分类与系统比较表来建立检索地图，再回到具体原始研究；综述所述潜力不自动等于装置效果已被临床验证。", "注册摘要；作者机构题录", "Abstract；系统分类和比较表全文待获取"),
"P02": ("器件与系统原始研究", "核心案例", "用预装香料的微型气味发生器，展示贴近上唇与面罩两种无线界面。加热、机械结构和控制电路共同调节释放。", "适合讲清软件指令如何变成真实气味。器件响应、鼻端感知、退味和长期使用分开评估；应用演示不能直接当作治疗试验。", "原文局部核读", "Concepts and design principle；Electrical performance of OGs；Fig.1–3"),
"P03": ("器件与系统原始研究", "核心案例", "将机械开孔、加热与算法结合，研究低延迟 MR 和多通道嗅觉训练。", "标题中的 latency-free 需按具体系统读。原文训练演示含 11 名训练志愿者、14 名对照志愿者，以及单名感染后嗅觉障碍患者案例；单病例不足以归因于装置或推广疗效。", "原文局部核读", "Latency-free MR demonstration；Olfactory training demonstration；Fig.3–5"),
"P04": ("Comment／展望", "背景参考", "讨论嗅觉反馈和可穿戴装置在虚实交互中的进展。", "期刊明确标为 Comment，不能把它与原始装置论文相加，当作另一项独立效果验证。适合寻找引用线索与概念图。", "期刊原文页面", "文章类型 Comment；正文与参考文献"),
"P05": ("装置开发与验证", "核心案例", "把连续可调阀门的嗅觉装置装到 HTC Vive 手柄，支持气味强度与混合控制，用户可主动靠近虚拟物体嗅闻。", "主动闻一个物体比整屋持续发香更能解释交互设计；需继续读清验证任务、识别准确度及残留控制，硬件可复用与效果强度分别判断。", "期刊索引摘要与亮点；正文访问受限", "Highlights；Abstract"),
"P06": ("可复现装置与探索研究", "复用优先", "提出简单、低成本、可复现的嗅觉显示，并开展三项探索研究。", "摘要明确提到体验可能同时出现正负作用，适合提醒先复用现有装置思路。完整材料清单、成本和实验条件尚需全文，当前不启动自制。", "出版社摘要", "Springer Abstract；Methods 全文待获取"),
"P07": ("技术综述", "背景参考", "把嗅觉显示概括为生成目标浓度的带味空气并递送至嗅觉器官，区分制作气味与递送气味。", "适合解释最基础的工程链路。2008 年综述用于历史和概念，不当作当前产品性能表。", "期刊摘要", "J-STAGE Abstract"),
"P08": ("技术综述", "扩展话题", "对比吸附／热脱附的真实气味浓缩，与传感器检测后另行产生刺激的虚拟浓缩。", "可用来区分检测、计算和输出，避免把电子鼻或气体传感器直接叫作能重放任意气味的显示器。", "期刊摘要", "J-STAGE Abstract"),
"P09": ("基础实验", "必要科学基础", "以钙成像与单细胞 RT-PCR 研究受体和气味分子的组合编码：一个受体可响应多种分子，同一分子也可激活多个受体。", "用一张组合关系图解释基础即可；受体组合证据不直接推出一个固定的通用配香基底，也不要求在通识课展开全套神经回路。", "原始摘要", "Cell Abstract"),
"P10": ("机器学习与感知验证", "数字化边界", "用图神经网络建立 Principal Odor Map，从分子结构预测气味描述，并作前瞻性新分子测试。", "预测气味标签与向鼻子生成刺激是不同任务。适合回答 AI 在哪里有用；不能把分子描述模型直接说成已经实现网上传香。", "原始摘要；全文接口访问受限", "Science／Europe PMC Abstract"),
"P11": ("心理物理实验与外推", "争议备份", "通过混合物辨别实验外推可区分嗅觉刺激的数量，提出超过一万亿的下限估计。", "必须与 P12 配对阅读。汇报可讲嗅觉复杂，具体数量涉及外推假设，不宜直接当成确定事实。", "原始摘要", "Science Abstract；与P12对读"),
"P12": ("方法学批评", "争议备份", "分析如何从有限混合物样本推断气味空间维数，批评一万亿估计的数学外推。", "它质疑的是估计方法，不能反过来宣称人类实际上只能分辨某个很小的固定数。科学争议适合展示为何要查原文。", "原始摘要；全文已取得待核读", "Abstract；完整推导待核读"),
"P13": ("VR场景用户研究", "核心反例", "在 VR 自助餐情境释放薯条气味，研究气味察觉和在场感的关系；摘要报告仅部分参与者察觉气味。", "察觉到味道与更高在场感的关联，不能自动当作随机加香的平均因果效果。注意未察觉者、注意力和个体差异。", "原始摘要；全文接口访问受限", "Frontiers／Europe PMC Abstract"),
"P14": ("场景一致性与延迟回忆实验", "核心反例", "用玫瑰、橙子与无味条件配合虚拟场景，研究一致性、愉悦度和约两周后的场景回忆。", "当前正文未发现记忆描述数量的气味增益；愉悦度表现也依气味和比较条件变化。应分别讲主观体验和记忆。出版页链接一则更正，本轮未取得更正正文，需在正式引用前补核。", "当前期刊正文与原文局部", "Participants；Memory-Recall Session；Bayesian Statistics；更正DOI 10.1177/20416695211028757"),
"P15": ("随机对照研究", "待读候选", "检验放松 VR 中增加触觉和嗅觉刺激的作用。", "本轮核到研究目的和题录，尚未核实各组结果；后续优先读能否分离嗅觉本身的附加作用，当前不写具体效果。", "题录及出版社索引摘要", "Abstract研究目的；结果全文待核"),
"P16": ("观点／综述性文章", "健康背景", "讨论气味用于个性化放松 VR 的可能性、临床场景与递送障碍。", "用于整理机制假说和设计问题，不能独自证明具体设备有效治疗焦虑或其他疾病。", "原始摘要", "Abstract；clinical applications与limitations部分待深入"),
"P17": ("系统开发与用户研究", "场景候选", "以建筑环境为对象，提出多感官 VR 的气味模拟流程与认知、生理、心理等反应测量。", "可复用其开发流程和测量思路；具体对照、样本与效应尚未核实，暂不把技术流程完成当成健康收益。", "期刊索引摘要与亮点", "Building and Environment Abstract／Highlights"),
"P18": ("多感官建筑体验研究", "场景候选", "使用视觉、听觉、嗅觉组合与混合方法，研究建筑 VR 的在场感、参与和体验。", "作为多模态案例候选；需确认每种感官的独立贡献及是否与P17共享样本，不能把同一项目的两篇文章算成重复验证。", "期刊原始摘要", "Virtual Reality & Intelligent Hardware Abstract"),
"P19": ("嗅觉丰富化干预", "健康边界反例", "用夜间气味扩散器研究健康老年人的记忆与脑影像变化，研究本身没有 VR。", "原始摘要报告43名入组者；宣传中的226%对应特定记忆测验及比较口径。不能转写为虚拟嗅觉普遍提升记忆或治疗认知疾病。", "原始摘要；全文已取得待核读", "Abstract；具体数字用于主讲前复核完整分析样本"),
"P20": ("前瞻性对照研究", "临床基础", "对嗅觉障碍患者进行反复气味暴露训练，并与未训练组比较。", "它支持讨论嗅觉训练这一思路，设计并非凭题目就可认定为随机盲法；也没有证明 VR 增量效果。", "原始摘要", "Methods：训练组40、未训练组16；12周"),
"P21": ("随机对照研究", "临床边界", "比较感染后嗅觉障碍患者的不同训练方案，其中一组在闻气味时看对应图片。", "视觉联合训练与嗅觉改善值得关注，但对应图片不是沉浸式 VR。摘要也报告部分情绪／生活质量指标未见改善，应分结局解释。", "原始摘要", "Methods；Results；四组设计；六个月结局"),
"P22": ("系统综述", "临床地图", "整理触觉与嗅觉反馈用于治疗性 VR 的研究，涉及创伤、焦虑、压力和放松等方向。", "39项纳入研究混合了触觉与嗅觉；不能把总数量说成39项嗅觉疗效试验。优先用来追原始研究及证据空白。", "作者机构原始摘要", "Sunway Abstract；综述全文待读"),
"P23": ("HCI设计研究", "待读候选", "以气味体验和技术设计机会为主题的 CHI 论文。", "本轮仅核到题录，具体研究方法和发现暂不归纳；保留为人机交互与设计语言的后续线索。", "仅题录", "Crossref题录；摘要与原文待取得"),
"P24": ("探索性游戏用户研究", "新近反例", "在带事件触发气味的切水果 VR 中比较有味与无味条件，摘要给出12名参与者。", "摘要报告部分沉浸条目改善，而在场感、其他体验及游戏表现未见显著差异；小样本和次序效应限制推广。", "出版社登记摘要", "Abstract；Results统计细节待全文核查"),
"P25": ("会议论文线索", "标识待核", "检索到2024年可穿戴嗅觉显示扩展论文及 Eurographics 原始 PDF 入口。", "初始 DOI 查询失败、PDF入口访问受限；保留题名和检索线索，暂不列为已核实文献或引用其性能。", "仅检索线索", "Eurographics原始入口；DOI未确认"),
"P26": ("多感官自然环境实验", "健康场景候选", "在城市、森林、公园等虚拟自然刺激中，考察多感官环境和生理压力反应。", "原文用皮电等短期实验指标。气味愉悦度与压力反应关系不能直接解释为单独加香治疗疾病或长期获益。", "摘要与原文局部", "Methods；Perceived pleasantness；Relationship between perceived pleasantness and skin conductance"),
"P27": ("经典多感官研究", "待读候选", "经典研究把多感官输入、记忆与在场感放在同一实验问题下。", "本轮仅核到题录和被后续论文引用的关系。具体实验组、样本与效果尚未读，适合背景查源，不写确定结论。", "仅题录", "IEEE题录；正文待取得"),
"P28": ("arXiv公开版本", "新近边界", "30人被试内比较海边 VR 的有香与无香条件，同时测自评与心率变异性。", "摘要报告自评放松差异不显著、部分HRV结果有差异；不能只挑显著指标概括全部有效。同行评审和完整统计尚待核。", "arXiv原始摘要", "Abstract；2025-07-10提交"),
"P29": ("CHI海报／arXiv公开版本", "训练候选", "18人山火撤离 VR 探索研究，对比烟味与对照条件的自评体验和准备感。", "较高沉浸评分不是实际撤离技能迁移的直接证据；规模小，主讲若选它应以探索性训练案例呈现。", "arXiv原始摘要与会议标记", "Abstract；Comments：CHI2026 poster；related DOI 10.1145/3772363.3798806"),
"P30": ("arXiv公开版本", "导航候选", "研究气味提示和通风对 VR 地点辨认、重复导航及用户体验的影响。", "摘要显示通风有助减少残留干扰，但更长通风未清楚提高重复导航准确率。适合把退味讲成工程需求而非装饰。", "arXiv原始摘要", "Abstract；2026-09-26提交；同行评审状态未核实"),
"P31": ("arXiv公开版本", "导航权衡", "两项空间任务分别研究气味定位和回到起点，报告定位偏差、终点误差和任务时间等结局。", "更小终点误差同时伴随更长行走距离与时间。真实价值取决于任务目标，不能只挑一个改善指标。", "arXiv原始摘要", "Abstract；Study1 N=24、Study2 N=19；同行评审状态未核实"),
"P32": ("arXiv公开版本", "社交扩展", "比较虚拟人物的气味、表情和性别线索对人物印象的影响。", "愉快气味未必压过视觉线索，不愉快气味可能主导负面判断。适合作为多感官失配或个体偏好的扩展，而非情绪控制证明。", "arXiv原始摘要", "Abstract；2025-09-14提交；同行评审状态未核实"),
"P33": ("arXiv公开版本", "导航扩展", "在受限视觉门户场景中比较视觉、听觉与气味线索组合，测目标辨认和反应时。", "组合条件改善不等于嗅觉单独贡献已经被分离；需要逐条件对照后再决定是否放入主讲。", "arXiv原始摘要", "Abstract；2025-09-14提交；同行评审状态未核实"),
"P34": ("基础分子研究", "必要科学基础", "通过克隆与表征候选受体基因家族，为嗅觉分子识别建立基础。", "适合作为科学背景，与P09互补。通识汇报只保留与实现有关的解释，不用基础发现代替现代设备或临床证据。", "原始摘要", "Cell Abstract"),
}

ARXIV = {
"P28": ("The Potential of Olfactory Stimuli in Stress Reduction through Virtual Reality", "Yasmin Elsaddik Valdivieso et al.", [2025,7,10]),
"P29": ("Smells Like Fire: Exploring the Impact of Olfactory Cues in VR Wildfire Evacuation Training", "Alison Crosby et al.", [2026,4,9]),
"P30": ("Exploring the Effects of Olfactory Cues and Ventilation on Teleportation-based Navigation in VR", "Dongyun Han et al.", [2026,9,26]),
"P31": ("Smelling the Way: Olfactory Modulation of Spatial Estimation and Path Integration in Virtual Reality", "Siyeon Bak et al.", [2026,9,26]),
"P32": ("What if Virtual Agents Had Scents? Users' Judgments of Virtual Agent Personality and Appeals in Encounters", "Dongyun Han et al.", [2025,9,14]),
"P33": ("Beyond the Portal: Enhancing Recognition in Virtual Reality Through Multisensory Cues", "Siyeon Bak et al.", [2025,9,14]),
}


def author_line(item):
    if item.get("authors_display"):
        return item["authors_display"]
    return "; ".join(" ".join(filter(None, [a.get("given"), a.get("family")])) for a in item.get("authors", [])) or "作者字段待核，见原始入口"


def main():
    records = json.loads((PRIVATE / "metadata.json").read_text(encoding="utf-8"))
    papers, candidates = [], []
    for item in records:
        identifier = item["id"]
        if identifier == "P02":
            record = json.loads((PRIVATE / "P02-europepmc.json").read_text(encoding="utf-8"))
            item.update(title=record["title"].rstrip("."), authors_display=record["authorString"],
                        venue="Nature Communications", published=[[2023,5,9]], status="original_registry_verified")
        if identifier == "P06":
            item.update(title="A reproducible olfactory display for exploring olfaction in immersive media experiences", authors_display="Michael J. Howell; Nicolas S. Herrera; Alec G. Moore; Ryan P. McMahan", venue="Multimedia Tools and Applications", published=[[2016]], status="publisher_abstract_verified", publisher_url="https://link.springer.com/article/10.1007/s11042-015-2971-0", date_note="Online 2015-10-20; print volume 2016")
        if identifier == "P07":
            item["title"] = "Recent Trend in Development of Olfactory Displays"
        if identifier == "P25":
            item.update(title="Extension of Wearable Olfactory Display for Multisensory VR Experience", venue="Eurographics Symposium on Virtual Environments", published=[[2024]], status="identifier_unverified_candidate", seed_doi_unverified=item.pop("doi"), source_url="https://diglib.eg.org/bitstream/handle/10.2312/egve20241374/egve20241374.pdf")
            item.pop("doi_url", None)
        if identifier in ARXIV:
            title, authors, date = ARXIV[identifier]
            number = item["doi"].split("arXiv.",1)[1]
            item.update(title=title, authors_display=authors, venue="arXiv公开版本", published=[date], status="original_arxiv_abstract_verified", url="https://arxiv.org/abs/"+number)
        dates = item.get("published") or []
        if not (dates and dates[0] and type(dates[0][0]) is int):
            raw_path = PRIVATE / (identifier + "-crossref.json")
            raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else {}
            for field in ("published-online", "published-print", "issued"):
                parts = raw.get(field, {}).get("date-parts", [])
                if parts and parts[0] and type(parts[0][0]) is int:
                    item["published"] = parts
                    item["date_source"] = field
                    break
            dates = item.get("published") or []
            if not (dates and dates[0] and type(dates[0][0]) is int):
                known_years = {"P01":2024,"P02":2023,"P03":2024,"P04":2024,"P05":2023,"P06":2016,"P07":2008,"P08":2018,"P09":1999,"P10":2023,"P11":2014,"P12":2015,"P13":2020,"P14":2021,"P15":2016,"P16":2021,"P17":2025,"P18":2025,"P19":2023,"P20":2009,"P21":2026,"P22":2025,"P23":2014,"P24":2026,"P25":2024,"P26":2019,"P27":1999,"P28":2025,"P29":2026,"P30":2026,"P31":2026,"P32":2025,"P33":2025,"P34":1991}
                assert identifier in known_years, ("Date requires review",identifier)
                item["published"] = [[known_years[identifier]]]
                item["date_source"] = "本轮已读原始题录的年份"
        kind, priority, summary, analysis, reading, location = NOTES[identifier]
        item.update(publication_kind=kind, priority=priority, summary_zh=summary, analysis_zh=analysis, reading_scope=reading, original_location=location, authors_display=author_line(item))
        item["authors_bib"] = " and ".join((a.get("family", "") + ", " + a.get("given", "")).strip(", ") for a in item.get("authors", [])) or item["authors_display"].replace("; ", " and ").replace(" et al.", " and others")
        if identifier == "P02":
            item["authors_bib"] = "Liu, Yiming and Yiu, Chun Ki and Zhao, Zhao and Park, Wooyoung and others"
        access = PRIVATE / (identifier + "-passages.json")
        if access.exists():
            full = json.loads(access.read_text(encoding="utf-8"))
            item.update(fulltext_url=full["url"], fulltext_license=full["license"], fulltext_access="已下载全文XML；实际阅读范围以上述reading_scope为准")
        # Preserve evidence privately; public candidate contains our notes, not copied abstracts.
        for key in ("abstract_text", "authors", "links", "license", "errors"):
            item.pop(key, None)
        if identifier == "P25":
            candidates.append(item)
        else:
            papers.append(item)
    updates_path = ROOT / 'deep-review/catalog-updates.json'
    if updates_path.exists():
        updates = json.loads(updates_path.read_text(encoding='utf-8'))
        for item in papers:
            item.update(updates.get('updates', {}).get(item['id'], {}))
        papers.extend(updates.get('additional_papers', []))
    for item in papers:
        assert item.get("title") and item.get("doi") and item.get("summary_zh")
        assert "\ufffd" not in item["title"]
        parts = item.get("published", [[2026]])[0]
        assert parts[0] <= 2026, item
    (ROOT / "papers.json").write_text(json.dumps({"date":"2026-11-01","scope":"定向广泛调研，非穷尽性系统综述","papers":papers,"unverified_candidates":candidates},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines = ["# 论文综览与逐篇中文分析", "", "日期：2026-11-01。以下按已核实题录收录33篇，另保留1条标识待核线索。阅读层级逐篇列出：局部读原文、读原始摘要、仅核题录分别处理。摘要级分析可帮助选题，正式主讲的数字与因果结论仍须回到全文。", "", "原文入口优先 DOI、出版社、作者机构或 arXiv。原始API记录及6篇开放全文XML在本地 private/ 阅读缓存，受忽略规则保护；本轮未上传任何文件。", "", "## 主题导航", "", "| 编号 | 年份 | 论文 | 类型／当前用途 | 阅读范围 |", "| --- | --- | --- | --- | --- |"]
    lines[2] = lines[2].replace('33篇', str(len(papers))+'篇')
    lines[4] = '原文入口优先DOI、出版社、作者机构或arXiv。广泛目录与主讲深读分别记录，后续深读更新见deep-review；原始API、全文与个人预览在private缓存，不纳入公开文件。'
    for item in papers:
        lines.append(f'| [{item["id"]}](#{item["id"].lower()}) | {item["published"][0][0]} | {item["title"]} | {item["publication_kind"]}／{item["priority"]} | {item["reading_scope"]} |')
    for item in papers:
        link = item.get("url", item["doi_url"])
        lines.extend(["", f'<a id="{item["id"].lower()}"></a>', f'## {item["id"]}｜{item["title"]}', "", f'- 作者：{item["authors_display"]}', f'- 年份／期刊：{item["published"][0]}；{item["venue"]}', f'- 原始入口：[DOI]({item["doi_url"]})；[阅读入口]({link})', f'- 文献类型／使用建议：{item["publication_kind"]}；{item["priority"]}', f'- 本轮阅读：{item["reading_scope"]}', f'- 原文定位：{item["original_location"]}', "", "**简介**："+item["summary_zh"], "", "**分析与适用边界**："+item["analysis_zh"]])
        if item.get("fulltext_url"):
            lines.append(f'\n全文：[原文入口]({item["fulltext_url"]})；已获取全文只说明可访问，阅读范围仍以上述记录为准。')
    lines.extend(["", "## 标识待核线索", "", "P25：Extension of Wearable Olfactory Display for Multisensory VR Experience（2024）。[Eurographics 原始PDF入口](https://diglib.eg.org/bitstream/handle/10.2312/egve20241374/egve20241374.pdf)。本轮访问受限且初始DOI查询未通过，保留线索，暂不引用性能或结论。", "", "## 继续阅读的优先顺序", "", "P02/P03/P05：讲清装置与同步；P13/P14/P24：区分在场感、愉悦度与任务表现；P26/P28：放松指标及对照；P20/P21：区分真实嗅觉训练与VR增量；P01/P22：沿综述追溯原始论文。P23/P27仅题录核验，P25标识待核，放在后续查源队列。"])
    (ROOT / "论文综览.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    bib = []
    for item in papers:
        title = item["title"].replace("{", "").replace("}", "")
        bib.append(f'@article{{{item["id"]},\n  title = {{{title}}},\n  author = {{{item["authors_bib"]}}},\n  journal = {{{item["venue"]}}},\n  year = {{{item["published"][0][0]}}},\n  doi = {{{item["doi"]}}},\n  note = {{{item["publication_kind"]}; reading scope recorded in papers.json}}\n}}')
    (ROOT / "references.bib").write_text("\n\n".join(bib)+"\n",encoding="utf-8")
    print(json.dumps({"papers":len(papers),"unverified_candidates":len(candidates),"fulltext_entries_with_url":sum(bool(p.get("fulltext_url")) for p in papers)},ensure_ascii=False))


if __name__ == "__main__":
    main()
