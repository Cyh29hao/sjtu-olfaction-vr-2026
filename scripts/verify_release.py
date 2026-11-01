"""Verify the actual shareable files and their links before publication."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import hashlib,json,re,subprocess,posixpath
from PIL import Image
from lxml import etree as E
import fitz

ROOT=Path(__file__).resolve().parents[1]
NS={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
deck=json.loads((ROOT/'content/deck.json').read_text(encoding='utf-8'))
names={'olfaction-vr-v1':22,'group-01-science':3,'group-02-technology':5,'group-03-applications':4}
artifacts=[]
for name,count in names.items():
    p=ROOT/'release/v1'/f'{name}.pptx'
    with ZipFile(p) as z:
        assert z.testzip() is None
        assert len([n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)])==count
        for n in z.namelist():
            if n.startswith('ppt/media/'):
                b=z.read(n);assert b,(p,n)
                if n.lower().endswith(('.png','.jpg','.jpeg','.gif')):Image.open(BytesIO(b)).verify()
        expected=deck['slides'] if name=='olfaction-vr-v1' else [s for s in deck['slides'] if s['group']=={'group-01-science':'01','group-02-technology':'02','group-03-applications':'03'}[name]]
        for i,s in enumerate(expected,1):
            xml=E.fromstring(z.read(f'ppt/notesSlides/notesSlide{i}.xml'))
            text='\n'.join(xml.xpath('//a:t/text()',namespaces=NS))
            assert s['script'] in text,(name,s['id'],'notes drift')
        if name=='olfaction-vr-v1':
            rels=E.fromstring(z.read('ppt/slides/_rels/slide13.xml.rels'))
            target=next(r.get('Target') for r in rels if r.get('Type','').endswith('/chart'))
            chart_path=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('ppt/slides',target))
            chart=E.fromstring(z.read(chart_path))
            vals=[[float(x) for x in ser.xpath('.//c:val//c:pt/c:v/text()',namespaces=NS)] for ser in chart.xpath('//c:ser',namespaces=NS)]
            assert vals==[[6.06,6.17,6.76,6.70],[7.78,8.14,8.33,7.88]],vals
            last=E.fromstring(z.read('ppt/slides/slide22.xml'));text=''.join(last.xpath('//a:t/text()',namespaces=NS))
            for person in ['陈云海','朱轶宸','刘昌镇','潘力熔','蔡天怿','娄嘉恒','王叶','陈柔羽','杨绎麟','邓沐熙','隋沅辰']:assert person in text,person
    artifacts.append(p)
for name,count in {**names,'olfaction-vr-v1-main':17,'全场口播':3,'问答与备课':3}.items():
    p=ROOT/'release/v1'/f'{name}.pdf'
    with fitz.open(p) as pdf:
        assert pdf.page_count==count,(name,pdf.page_count)
        assert all(page.get_text().strip() for page in pdf)
    artifacts.append(p)
missing=[];links=0
for p in ROOT.rglob('*.md'):
    if any(x in p.parts for x in ['.git','private','node_modules']) or any(x.startswith('.chart-data-') for x in p.parts):continue
    text=p.read_text(encoding='utf-8');assert '\ufffd' not in text,p
    for a,b in re.findall(r'\]\((?:<([^>]+)>|([^\s)]+))\)',text):
        link=a or b
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',link) or link.startswith('#'):continue
        links+=1
        if not (p.parent/link.split('#')[0]).exists():missing.append((str(p.relative_to(ROOT)),link))
assert not missing,missing
papers=json.loads((ROOT/'research/2026-11-01/papers.json').read_text(encoding='utf-8'))
assert len(papers['papers'])==34 and len({p['doi'] for p in papers['papers']})==34
assert sum(s['seconds'] for s in deck['slides'] if s['role']=='main')==660
manifest={'version':'v1','main_slides':16,'backup_slides':5,'last_slide':'11人分工','speakers':4,'design_seconds':720,'synthesized_reading_seconds':636.54,'human_rehearsal':False,'artifacts':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in artifacts]}
(ROOT/'release/v1/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
report={'status':'passed','relative_links':links,'papers':34,'artifacts':len(artifacts),'media':'nonempty and decodable','notes':'all four decks match content source','chart':'exact native values match P15 Table1','human_rehearsal':False}
(ROOT/'.git/production-20261101/release-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
