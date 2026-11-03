"""Verify a selected release against the current editable content source."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import argparse
import hashlib
import json
import math
import posixpath
import re
from PIL import Image
from lxml import etree as E
import fitz

ROOT = Path(__file__).resolve().parents[1]
NS = {'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
      'c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
GROUP_NAMES = {'01':'group-01-science', '02':'group-02-technology', '03':'group-03-applications'}
PEOPLE = ['陈云海','朱轶宸','刘昌镇','潘力熔','蔡天怿','娄嘉恒','王叶','陈柔羽','杨绎麟','邓沐熙','隋沅辰']


def check_chart(archive, number, source):
    rels = E.fromstring(archive.read(f'ppt/slides/_rels/slide{number}.xml.rels'))
    targets = [r.get('Target') for r in rels if r.get('Type','').endswith('/chart')]
    assert len(targets) == 1, (source['id'], 'expected one editable chart', targets)
    target = targets[0]
    chart_path = target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join('ppt/slides', target))
    chart = E.fromstring(archive.read(chart_path))
    actual = chart.xpath('//c:ser', namespaces=NS)
    expected = source['chart']
    assert len(actual) == len(expected['series']), source['id']
    for xml, series in zip(actual, expected['series']):
        values = [float(x) for x in xml.xpath('.//c:val//c:pt/c:v/text()', namespaces=NS)]
        assert len(values) == len(series['values']), (source['id'], values)
        assert all(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9) for a,b in zip(values,series['values'])), (source['id'], values)
        assert xml.xpath('.//c:cat//c:pt/c:v/text()',namespaces=NS) == expected['categories'], source['id']
        assert xml.xpath('./c:tx//c:v/text()',namespaces=NS) == [series['name']], source['id']
    for key, tag in [('yMin','min'),('yMax','max')]:
        if expected.get(key) is not None:
            values = chart.xpath(f'//c:valAx/c:scaling/c:{tag}/@val',namespaces=NS)
            assert values and math.isclose(float(values[0]),expected[key]), (source['id'], key, values)


def check_deck(path, expected, sources, is_full=False):
    charts = 0
    with ZipFile(path) as archive:
        assert archive.testzip() is None, path
        parts = [n for n in archive.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)]
        assert len(parts) == len(expected), (path.name,len(parts),len(expected))
        for name in archive.namelist():
            if not name.startswith('ppt/media/'):
                continue
            data = archive.read(name)
            assert data, (path.name,name,'empty media')
            if name.lower().endswith(('.png','.jpg','.jpeg','.gif','.bmp','.webp','.tif','.tiff')):
                with Image.open(BytesIO(data)) as image:
                    image.verify()
        for number, slide in enumerate(expected,1):
            xml = E.fromstring(archive.read(f'ppt/notesSlides/notesSlide{number}.xml'))
            notes = '\n'.join(xml.xpath('//a:t/text()',namespaces=NS))
            assert slide['script'] in notes, (path.name,slide['id'],'notes drift')
            for sid in slide.get('source_ids',[]):
                assert sid in sources, (slide['id'],'unknown source',sid)
                url = sources[sid].get('url')
                if url:
                    assert url in notes, (path.name,slide['id'],'missing source URL',sid)
            if slide.get('layout') == 'results':
                check_chart(archive,number,slide)
                charts += 1
        if is_full:
            assert expected[-1]['id'] == 'TEAM' and expected[-1]['role'] == 'contributions'
            last = E.fromstring(archive.read(f'ppt/slides/slide{len(expected)}.xml'))
            rows = last.xpath('//a:tbl/a:tr',namespaces=NS)
            assert len(rows) == len(PEOPLE)+1, ('TEAM needs header and eleven person rows',len(rows))
            row_text = [''.join(r.xpath('.//a:t/text()',namespaces=NS)) for r in rows[1:]]
            for person in PEOPLE:
                assert sum(person in row for row in row_text) == 1, ('TEAM',person)
    return charts


def reading_seconds(production):
    path = production / 'timing.json'
    if not path.exists():
        return None
    timing = json.loads(path.read_text(encoding='utf-8'))
    for key in ['synthesized_reading_seconds','reading_seconds','duration_seconds','total_seconds','audio_seconds']:
        value = timing.get(key)
        if isinstance(value,(int,float)) and not isinstance(value,bool) and value > 0:
            return value
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',help='Defaults to content/deck.json version, then v1.')
    parser.add_argument('--production-dir',type=Path,help='Private verification and timing.json directory.')
    args = parser.parse_args()
    deck = json.loads((ROOT/'content/deck.json').read_text(encoding='utf-8'))
    version = args.version or deck.get('version','v1')
    if not re.fullmatch(r'v[\w.-]+',version):
        parser.error('Invalid version')
    if version != deck.get('version','v1'):
        parser.error('Requested release does not match content/deck.json version')
    release = ROOT/'release'/version
    production = ROOT/(args.production_dir or Path('.git/production-20261101' if version=='v1' else f'.git/production-{version}'))
    production.mkdir(parents=True,exist_ok=True)
    main_slides = [s for s in deck['slides'] if s['role']=='main']
    assert deck['slides'][:len(main_slides)] == main_slides, 'Main PDF expects contiguous main slides'
    expected_decks = {f'olfaction-vr-{version}':deck['slides']}
    expected_decks.update({name:[s for s in deck['slides'] if int(s['group'])==int(group)] for group,name in GROUP_NAMES.items()})
    artifacts = []
    charts = 0
    for name,slides in expected_decks.items():
        assert slides, ('missing group slides',name)
        path = release/f'{name}.pptx'
        charts += check_deck(path,slides,deck['sources'],name==f'olfaction-vr-{version}')
        artifacts.append(path)
    pdf_counts = {name:len(slides) for name,slides in expected_decks.items()}
    pdf_counts[f'olfaction-vr-{version}-main'] = len(main_slides)+1
    for name in [*pdf_counts,'全场口播','问答与备课']:
        path = release/f'{name}.pdf'
        with fitz.open(path) as pdf:
            if name in pdf_counts:
                assert pdf.page_count == pdf_counts[name], (name,pdf.page_count,pdf_counts[name])
            assert pdf.page_count > 0 and all(page.get_text().strip() for page in pdf), (name,'empty page')
            if name == f'olfaction-vr-{version}-main':
                for person in PEOPLE:
                    assert person in pdf[-1].get_text(), ('main PDF contribution page',person)
        artifacts.append(path)
    missing = []
    links = 0
    for path in ROOT.rglob('*.md'):
        if any(x in path.parts for x in ['.git','private','node_modules']) or any(x.startswith('.chart-data-') for x in path.parts):
            continue
        text = path.read_text(encoding='utf-8')
        assert '\ufffd' not in text, path
        for a,b in re.findall(r'\]\((?:<([^>]+)>|([^\s)]+))\)',text):
            link = a or b
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',link) or link.startswith('#'):
                continue
            links += 1
            if not (path.parent/link.split('#')[0]).exists():
                missing.append((str(path.relative_to(ROOT)),link))
    assert not missing, missing
    paper_count = None
    papers_path = ROOT/'research/2026-11-01/papers.json'
    if papers_path.exists():
        papers = json.loads(papers_path.read_text(encoding='utf-8'))['papers']
        paper_count = len(papers)
        assert len({p['doi'] for p in papers}) == paper_count, 'Duplicate paper DOI'
    spoken = sum(s['seconds'] for s in main_slides)
    total_budget = deck.get('presentation_seconds',720)
    reserve = deck.get('transition_reserve_seconds',total_budget-spoken)
    assert 0 <= reserve and spoken+reserve <= total_budget
    speakers = deck.get('speaker_count',4)
    assert 1 <= speakers <= 4
    manifest = {'version':version,'main_slides':len(main_slides),
                'backup_slides':sum(s['role']=='backup' for s in deck['slides']),
                'last_slide':'11人分工','speakers':speakers,
                'design_seconds':spoken+reserve,'spoken_seconds_budget':spoken,
                'transition_reserve_seconds':reserve,
                'presentation_seconds':deck.get('presentation_seconds',720),
                'synthesized_reading_seconds':reading_seconds(production),
                'human_rehearsal':False,
                'artifacts':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,
                              'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in artifacts]}
    (release/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report = {'version':version,'status':'passed','relative_links':links,
              'papers':paper_count,'artifacts':len(artifacts),
              'media':'nonempty and decodable','notes':'all decks match source scripts and URLs',
              'chart':f'{charts} native result charts match current source data','human_rehearsal':False}
    (production/'release-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__ == '__main__':
    main()
