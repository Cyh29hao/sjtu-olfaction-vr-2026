"""Create readable Chinese rehearsal PDFs from the same Markdown sources."""
from pathlib import Path
import argparse
import json
import re
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
import fitz

ROOT=Path(__file__).resolve().parents[1]
FONT='OlfactionYaHei'
pdfmetrics.registerFont(TTFont(FONT,'C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
BLUE=HexColor('#175F8B')
STYLES={
    'title':ParagraphStyle('title',fontName=FONT,fontSize=25,leading=35,textColor=BLUE,spaceAfter=20),
    'h2':ParagraphStyle('h2',fontName=FONT,fontSize=14,leading=22,textColor=BLUE,spaceBefore=15,spaceAfter=7,keepWithNext=True),
    'body':ParagraphStyle('body',fontName=FONT,fontSize=10.8,leading=19,wordWrap='CJK',spaceAfter=9),
}

def inline(text):
    text=escape(text)
    text=re.sub(r'\*\*(.*?)\*\*',r'\1',text)
    text=re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)',
                lambda m:f'<link href="{m.group(2)}" color="#175F8B">{m.group(1)}</link>',text)
    text=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',text)
    return text.replace('\n','<br/>')

def markdown_table(block):
    rows=[]
    for line in block.splitlines():
        cells=[x.strip() for x in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-+:?',x) for x in cells):continue
        rows.append(cells)
    if not rows or any(len(r)!=len(rows[0]) for r in rows):
        raise ValueError('Malformed Markdown table')
    count=len(rows[0])
    weights=([1.15,1.0,3.25] if count==3 else [1.7,0.65,2,2] if count==4 else [1]*count)
    widths=[499.28*w/sum(weights) for w in weights]
    base=ParagraphStyle('cell',parent=STYLES['body'],fontSize=8.8,leading=14,spaceAfter=0)
    head=ParagraphStyle('cellhead',parent=base,textColor=HexColor('#FFFFFF'))
    values=[[Paragraph(inline(value),head if r==0 else base) for value in row] for r,row in enumerate(rows)]
    table=Table(values,colWidths=widths,repeatRows=1,hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),BLUE),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[HexColor('#EEF4F6'),HexColor('#FFFFFF')]),
        ('GRID',(0,0),(-1,-1),0.4,HexColor('#DDE4E7')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    return table

def footer(canvas,doc,version='v1'):
    canvas.saveState()
    canvas.setStrokeColor(HexColor('#92D050'));canvas.setLineWidth(2)
    canvas.line(48,44,547,44)
    canvas.setFont(FONT,8);canvas.setFillColor(HexColor('#687780'))
    canvas.drawString(48,28,f'气味、VR与虚拟感官 · {version} 排练材料')
    canvas.drawRightString(547,28,str(doc.page))
    canvas.restoreState()

def build(name,version='v1',review_dir=None):
    source=ROOT/'release'/version/f'{name}.md'
    target=source.with_suffix('.pdf')
    story=[]
    for block in re.split(r'\n\s*\n',source.read_text(encoding='utf-8').strip()):
        if not block.strip():continue
        if block.lstrip().startswith('|'):
            story.extend([markdown_table(block),Spacer(1,10)])
            continue
        if block.startswith('# '):key='title';text=block[2:]
        elif block.startswith('## '):key='h2';text=block[3:]
        else:key='body';text=block
        story.append(Paragraph(inline(text),STYLES[key]))
    doc=SimpleDocTemplate(str(target),pagesize=(595.28,841.89),leftMargin=48,rightMargin=48,topMargin=45,bottomMargin=61,title=name,author='气味科学小组')
    page_footer=lambda canvas,doc:footer(canvas,doc,version)
    doc.build(story,onFirstPage=page_footer,onLaterPages=page_footer)
    with fitz.open(target) as pdf:
        base=Path(review_dir) if review_dir else Path('.git/production-20261101/print-review' if version=='v1' else f'.git/production-{version}/print-review')
        out=ROOT/base/name
        out.mkdir(parents=True,exist_ok=True)
        for i,page in enumerate(pdf):page.get_pixmap(matrix=fitz.Matrix(1.1,1.1)).save(out/f'{i+1:02}.png')
        assert all(p.get_text().strip() for p in pdf)
        return {'file':target.name,'pages':pdf.page_count}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',help='Defaults to content/deck.json version, then v1.')
    parser.add_argument('--review-dir',type=Path,help='Private directory for rendered page PNGs.')
    args=parser.parse_args()
    content=ROOT/'content/deck.json'
    default_version=json.loads(content.read_text(encoding='utf-8')).get('version','v1') if content.exists() else 'v1'
    version=args.version or default_version
    if not re.fullmatch(r'v[\w.-]+',version):
        parser.error('Invalid version')
    print([build(name,version,args.review_dir) for name in ['全场口播','问答与备课']])
