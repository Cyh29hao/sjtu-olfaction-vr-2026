"""Create readable Chinese rehearsal PDFs from the same Markdown sources."""
from pathlib import Path
import re
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
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

def footer(canvas,doc):
    canvas.saveState()
    canvas.setStrokeColor(HexColor('#92D050'));canvas.setLineWidth(2)
    canvas.line(48,44,547,44)
    canvas.setFont(FONT,8);canvas.setFillColor(HexColor('#687780'))
    canvas.drawString(48,28,'气味、VR与虚拟感官 · v1 排练材料')
    canvas.drawRightString(547,28,str(doc.page))
    canvas.restoreState()

def build(name):
    source=ROOT/'release/v1'/f'{name}.md'
    target=source.with_suffix('.pdf')
    story=[]
    for block in re.split(r'\n\s*\n',source.read_text(encoding='utf-8').strip()):
        if not block.strip():continue
        if block.startswith('# '):key='title';text=block[2:]
        elif block.startswith('## '):key='h2';text=block[3:]
        else:key='body';text=block
        text=escape(text).replace('\n','<br/>')
        text=re.sub(r'\*\*(.*?)\*\*',r'\1',text)
        story.append(Paragraph(text,STYLES[key]))
    doc=SimpleDocTemplate(str(target),pagesize=(595.28,841.89),leftMargin=48,rightMargin=48,topMargin=45,bottomMargin=61,title=name,author='气味科学小组')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    with fitz.open(target) as pdf:
        out=ROOT/'.git/production-20261101/print-review'/name
        out.mkdir(parents=True,exist_ok=True)
        for i,page in enumerate(pdf):page.get_pixmap(matrix=fitz.Matrix(1.1,1.1)).save(out/f'{i+1:02}.png')
        assert all(p.get_text().strip() for p in pdf)
        return {'file':target.name,'pages':pdf.page_count}

if __name__=='__main__':
    print([build(name) for name in ['全场口播','问答与备课']])
