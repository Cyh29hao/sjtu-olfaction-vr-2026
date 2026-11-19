/** Build editable olfaction/VR slides from the common content source. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';

process.on('uncaughtException',error=>{
  console.error(`${error.name}: ${error.message}`);
  console.error((error.stack || '').split('\n').filter(line=>line.trimStart().startsWith('at ')).slice(0,6).join('\n'));
  process.exitCode=1;
});

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const option = (key, fallback) => {
  const i = args.indexOf(key);
  return i < 0 ? fallback : args[i + 1];
};
const modules = process.env.RUNTIME_NODE_MODULES || 'C:/Users/Cyh29hao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {PresentationFile, FileBlob} = await import(pathToFileURL(path.join(modules, '@oai/artifact-tool/dist/artifact_tool.mjs')).href);
const skillDir=process.env.PRESENTATION_SKILL_DIR || 'C:/Users/Cyh29hao/.codex/plugins/cache/openai-primary-runtime/presentations/26.1112.11217/skills/presentations';
const {applyPresentationChartFont}=await import(pathToFileURL(path.join(skillDir,'container_tools/artifact_tool_utils.mjs')).href);
const input = path.resolve(ROOT, option('--input', 'content/deck.json'));
const output = path.resolve(ROOT, option('--output', '.git/production-20261101/build/candidate.pptx'));
const template = option('--template', process.env.OLFACTION_TEMPLATE);
if (!template) throw new Error('Supply --template with the selected local PPTX, or set OLFACTION_TEMPLATE');
const source = JSON.parse(await fs.readFile(input, 'utf8'));
if (!Array.isArray(source.slides) || !source.slides.length) throw new Error('deck.json must contain slides');
const ids = source.slides.map(s => s.id);
if (new Set(ids).size !== ids.length) throw new Error('Slide IDs must be unique');
const last = source.slides.at(-1);
if (source.slides.length > 1 && last.layout !== 'contributions' && !(last.role==='qa' && source.slides.at(-2)?.layout==='contributions')) throw new Error('End with contributions, optionally followed by the Q&A summary');
const p = await PresentationFile.importPptx(await FileBlob.load(path.resolve(template)));
const generalLayout = p.layouts.items.find(x => x.name === '标题和内容（一般样式）');
const blankLayout = p.layouts.items.find(x => x.name === '空白（纯白，无底边）');
if (!generalLayout || !blankLayout) throw new Error('Selected template does not contain the verified layouts');
p.slides.keep([]);
const C = {blue:'#175F8B', green:'#92D050', ink:'#243742', muted:'#586975', line:'#DDE4E7', pale:'#EEF4F6', white:'#FFFFFF'};
const FONT = '微软雅黑';
const nativeTables = [], nativeCharts = [], warnings = [], missingAssets=[];

function text(s, value, x, y, w, h, size=30, color=C.ink, bold=false, name='') {
  const o = s.shapes.add({geometry:'textbox', name, position:{left:x, top:y, width:w, height:h}, fill:'none', line:{fill:'none',width:0}});
  o.text = String(value ?? '');
  o.text.style = {typeface:FONT, fontSize:size, color, bold};
  o.text.insets = 0;
  return o;
}
function rect(s,x,y,w,h,fill=C.pale,stroke='none',name='') {
  return s.shapes.add({geometry:'rect', name, position:{left:x,top:y,width:w,height:h},fill,line:{fill:stroke,width:stroke==='none'?0:1}});
}
function arrow(s,x,y,w=42,color=C.blue) {
  return s.shapes.add({geometry:'rightArrow',position:{left:x,top:y,width:w,height:20},fill:color,line:{fill:'none',width:0}});
}
function line(s,x,y,w,color=C.line,h=2) { return rect(s,x,y,w,h,color); }
function oval(s,x,y,w,h,fill) {
  return s.shapes.add({geometry:'ellipse',position:{left:x,top:y,width:w,height:h},fill,line:{fill:'none',width:0}});
}
function outline(s,x,y,w,h,commands,color=C.blue,width=4) {
  return s.shapes.add({geometry:'custom',position:{left:x,top:y,width:w,height:h},fill:'none',
    line:{style:'solid',fill:color,width},customPaths:[{width:w,height:h,commands}]});
}
async function picture(s, image, x,y,w,h,fit='contain') {
  if (!image) return;
  const item = typeof image === 'string' ? {path:image} : image;
  const absolute = path.resolve(ROOT,item.path || item.src || '');
  try { await fs.access(absolute); }
  catch(error) {
    if(!args.includes('--allow-missing-assets'))throw error;
    missingAssets.push(item.path || item.src);
    text(s,`素材待加入\n${item.path || item.src}`,x+10,y+h/2-45,w-20,100,22,C.muted);
    return;
  }
  const bytes=await fs.readFile(absolute);
  if(!bytes.length)throw new Error('Empty source image: '+absolute);
  const ext=path.extname(absolute).toLowerCase();
  const contentType={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.gif':'image/gif','.svg':'image/svg+xml'}[ext];
  if(!contentType)throw new Error('Unsupported source image extension: '+ext);
  return s.images.add({blob:new Uint8Array(bytes),contentType,alt:item.alt || '',fit:item.fit || fit,position:{left:x,top:y,width:w,height:h},...(item.crop?{crop:item.crop}:{})});
}
function verifyMedia(file) {
  const code=String.raw`import sys,json,io
from zipfile import ZipFile
from PIL import Image
from pathlib import Path
items=[]
with ZipFile(sys.argv[1]) as z:
 for name in z.namelist():
  if not name.startswith('ppt/media/'):continue
  raw=z.read(name)
  if not raw:raise ValueError('Empty media part: '+name)
  if Path(name).suffix.lower() in ['.png','.jpg','.jpeg','.webp','.gif','.bmp','.tif','.tiff']:
   with Image.open(io.BytesIO(raw)) as image:image.verify()
  items.append({'part':name,'bytes':len(raw)})
print(json.dumps({'nonempty':True,'raster_decode':'passed','media':items}))`;
  const result=spawnSync(process.env.RUNTIME_PYTHON || 'C:/Users/Cyh29hao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',['-X','utf8','-c',code,file],{encoding:'utf8'});
  if(result.status!==0)throw new Error('Embedded image validation failed: '+result.stderr);
  return JSON.parse(result.stdout);
}
function notes(d) {
  const refs = (d.source_ids || []).map(id => {
    const r = source.sources?.[id];
    return r ? `[${id}] ${r.authors || ''} ${r.title || ''}\n${r.url || ''}\n${r.location || ''}` : `[${id}]`;
  }).join('\n\n');
  const locations = d.source_locations ? (typeof d.source_locations === 'string' ? d.source_locations : JSON.stringify(d.source_locations,null,2)) : '';
  return `${d.script || ''}\n\n讲述提示：${d.cue || ''}\n来源定位：\n${locations}\n\n${refs}\n\n${d.footer || ''}`.trim();
}
function base(d,n) {
  const s = p.slides.add({layoutId:(d.layout === 'cover' ? blankLayout : generalLayout).id});
  s.background.fill=C.white;
  if (d.role === 'backup') s.hidden=true;
  if (d.layout !== 'cover') {
    // Reuse the template master/layout; custom content does not change the shared master.
    if(source.version === 'v3') {
      const chapter = d.role === 'backup' ? '备课与来源' : d.role === 'contributions' ? '小组协作' : ({'01':'01  嗅觉感知的科学基础','02':'02  虚拟嗅觉的技术实现','03':'03  应用与意义'}[d.group] || (d.id.startsWith('C')?'04  体验途径与效果判断':'气味、VR与虚拟感官'));
      text(s,d.section_heading || chapter,104,16,1092,25,16,C.muted,false,'chapter-location');
      text(s,d.title,104,51,1092,77,43,C.blue,true,'headline');
    } else text(s,d.title,104,38,1092,90,44,C.blue,true,'headline');
    text(s,d.footer ?? (d.source_ids || []).map(x=>`[${x}]`).join('  '),104,660,1060,33,16,C.muted,false,'source-footer');
    text(s,String(n).padStart(2,'0'),1185,673,45,25,15,C.muted,false,'page-number');
  }
  s.speakerNotes.text=notes(d);
  return s;
}
function paragraphs(s, values, x,y,w, size=31,gap=85,color=C.ink) {
  (Array.isArray(values)?values:[values]).filter(Boolean).forEach((v,i)=>text(s,v,x,y+i*gap,w,gap-12,size,color));
}
function nativeTable(s,d,n,frame={left:104,top:185,width:1092,height:400}) {
  const spec=d.table || {};
  const headers=spec.headers || [];
  const values=[headers,...(spec.rows || [])];
  if (!headers.length || values.some(row=>row.length!==headers.length)) throw new Error(`${d.id}: table requires equal-width rows`);
  const headerHeight=values.length>8?38:52;
  const height=Math.min(frame.height,headerHeight+(values.length-1)*78);
  const t=s.tables.add({rows:values.length,columns:headers.length,...frame,height,values});
  t.rows[0].height=headerHeight;
  for(let r=1;r<values.length;r++)t.rows[r].height=(height-headerHeight)/(values.length-1);
  t.columnTracks=(spec.widths || (d.layout==='contributions'&&headers.length===3?[1.15,1.4,3.45]:headers.map(()=>1))).map(value=>({mode:'fr',value}));
  t.borders.assign({fill:C.white,width:1});
  for(let r=0;r<values.length;r++) for(let c=0;c<headers.length;c++) {
    const cell=t.getCell(r,c);
    cell.fill=r===0?C.blue:(r%2?C.pale:C.white);
    cell.text.style={typeface:FONT,fontSize:spec.fontSize || (values.length>8?22:27),color:r===0?C.white:C.ink,bold:r===0};
  }
  nativeTables.push(n);
  return t;
}
async function render(d,n) {
  const s=base(d,n);
  const body=Array.isArray(d.body)?d.body:[d.body].filter(Boolean);
  switch(d.layout) {
    case 'cover': {
      if(d.image) await picture(s,d.image,660,0,620,720,'contain');
      rect(s,0,0,660,720,C.blue);
      text(s,source.course || '气味科学中的健康密码',70,60,510,52,25,C.white);
      text(s,d.title || source.title,70,198,520,230,64,C.white,true,'cover-title');
      text(s,d.subtitle || source.subtitle || '',70,462,500,110,30,C.white);
      text(s,d.byline || '气味、VR与虚拟感官',70,620,520,40,23,C.white);
      if(source.version==='v3')text(s,'研究演示帧：Liu等，2023，Movie3 · CC BY 4.0',687,666,560,36,13,C.white);
      break;
    }
    case 'talk-roadmap': {
      const sections = d.sections || [];
      const gap = 75;
      const width = (1092 - gap * (sections.length - 1)) / sections.length;
      for (const [index, item] of sections.entries()) {
        const x = 104 + index * (width + gap);
        line(s,x,285,width,C.green,5);
        text(s,item.label,x,320,width,76,52,C.blue,true);
        if(item.text)text(s,item.text,x,412,width,50,25,C.muted);
        if (index < sections.length-1) arrow(s,x+width+22,344,31,C.blue);
      }
      break;
    }
    case 'science-bridge': {
      text(s,'科学基础',104,153,435,39,26,C.blue,true);
      text(s,'虚拟嗅觉如何实现',660,153,510,39,26,C.blue,true);
      for (const [index,row] of d.bridge_rows.entries()) {
        const y = 205 + index * 128;
        rect(s,104,y,450,104,'#F2F6F9');
        rect(s,660,y,536,104,'#F0F7E9');
        text(s,row.science,122,y+9,414,36,25,C.blue,true);
        text(s,row.detail,122,y+47,414,50,22,C.ink);
        arrow(s,583,y+43,47,C.blue);
        text(s,row.implementation,681,y+18,494,77,26,C.ink,true);
      }
      text(s,d.caption,104,610,1092,38,24,C.blue,true);
      break;
    }
    case 'device-bridge': {
      text(s,'装置能安排什么',104,153,414,39,26,C.blue,true);
      text(s,'实际应用要测什么',646,153,550,39,26,C.blue,true);
      for(const [index,row] of d.bridge_rows.entries()) {
        const y=205+index*128;
        rect(s,104,y,433,104,'#EFF6E9');
        rect(s,646,y,550,104,index===1?'#E7F2F8':'#F2F6F9');
        text(s,row.device,124,y+22,394,71,26,C.ink,true);
        arrow(s,568,y+43,47,C.blue);
        text(s,row.question,666,y+22,511,71,27,C.blue,true);
      }
      text(s,d.caption,104,611,1092,38,23,C.muted);
      break;
    }
    case 'presence-result': {
      text(s,d.intro,104,146,1092,39,24,C.muted,false,d.backup?.anchor);
      await picture(s,d.image,104,196,708,434,'contain');
      for (const [index,row] of d.result_rows.entries()) {
        const y=212+index*122;
        rect(s,834,y,362,108,index===0?'#EDF5FB':'#F2F5F6');
        text(s,row.label,851,y+8,328,32,24,C.blue,true);
        text(s,row.from+' → '+row.to,851,y+40,328,42,34,C.ink,true);
        text(s,row.text,851,y+82,328,23,17,C.muted);
      }
      text(s,'橙线：始终有香　黄线：始终无香',834,457,362,32,19,C.muted);
      text(s,d.caption,834,500,362,72,21,C.blue,true);
      text(s,d.sample_note,834,578,362,60,19,C.muted);
      break;
    }
    case 'application-verdict': {
      for (const [index,row] of d.verdict_rows.entries()) {
        const y=174+index*145;
        rect(s,104,y,6,102,index<2?C.green:'#A5B8C2');
        text(s,row.label,126,y+7,430,49,29,C.blue,true);
        text(s,row.evidence,570,y+6,620,100,26,C.ink);
        if(index<d.verdict_rows.length-1) line(s,126,y+116,1067,C.line,1);
      }
      text(s,d.caption,126,612,1067,42,23,C.muted);
      break;
    }
    case 'answer-map': {
      if(d.map_rows?.length!==9)throw new Error(`${d.id}: answer-map expects three cards per layer`);
      const columns=[245,569,893];
      const top=[148,268,414];
      const layers=['理论','装置','应用与意义'];
      for(const [r,layer] of layers.entries()) {
        const y=top[r];
        text(s,layer,104,y+10,132,43,24,C.blue,true);
        for(const [i,x] of columns.entries()) {
          const card=d.map_rows[r*3+i];
          const application=r===2;
          const fill=r===0?'#F1F6FA':r===1?'#EFF6E9':i===0?'#E7F2F8':'#F2F6F7';
          rect(s,x,y,303,application?190:85,fill);
          if(application)line(s,x,y,303,i===0?C.blue:i===1?C.green:'#A9BBC5',4);
          text(s,card.label,x+13,y+8,277,35,24,C.blue,true,card.anchor);
          text(s,card.text,x+13,y+46,277,application?127:35,application?20:18,C.ink);
          if(r===0)s.shapes.add({geometry:'downArrow',position:{left:x+139,top:237,width:24,height:25},fill:C.green,line:{fill:'none',width:0}});
        }
      }
      line(s,245,365,951,C.line,1);
      text(s,'在三项独立研究中，看实际体验和任务表现',245,374,951,28,19,C.muted);
      break;
    }
    case 'qa-evidence': {
      text(s,d.answer,104,145,1092,79,31,C.blue,true,'evidence-answer');
      line(s,104,228,1092);
      const details=d.details || [];
      if(d.image || d.images?.length || d.table) {
        if(d.table)nativeTable(s,d,n,{left:104,top:257,width:640,height:325});
        else if(d.images?.length) {
          for(const [i,image] of d.images.entries()) {
            const x=104+i*312;
            await picture(s,image,x,250,292,285,'contain');
            text(s,image.label,x,545,292,38,21,C.blue,true);
          }
        }
        else await picture(s,d.image,104,245,608,344,'contain');
        if(d.caption)text(s,d.caption,104,593,644,63,18,C.muted);
        const rowHeight=Math.floor(398/Math.max(details.length,1));
        for(const [i,item] of details.entries()) {
          const y=248+i*rowHeight;
          text(s,item.label,761,y,435,31,22,C.blue,true);
          text(s,item.text,761,y+36,435,rowHeight-37,20,C.ink);
        }
      } else {
        for(const [i,item] of details.entries()) {
          const x=104+(i%2)*565;
          const y=249+Math.floor(i/2)*174;
          line(s,x,y,526,C.line,1);
          text(s,item.label,x,y+11,526,42,25,C.blue,true);
          text(s,item.text,x,y+55,526,116,23,C.ink);
        }
        if(d.caption)text(s,d.caption,104,612,1092,41,19,C.muted);
      }
      break;
    }
    case 'narrative-map': {
      const detail=d.map_mode==='detail';
      rect(s,92,145,1104,506,'none',C.blue,'narrative-frame');
      const xs=[260,568,876];
      const science=[['真实分子与结构',detail?'香芹酮：空间排列不同\n典型气味可能不同':'分子与结构影响气味'],['到达与感知',detail?'分子到达嗅觉区域\n受体识别、神经元传信号':'刺激怎样进入嗅觉通路'],['组合响应',detail?'多类受体组合响应\n浓度可能改变响应':'不同刺激怎样被区分']];
      const engineering=[['选择材料',detail?'预装香料与石蜡载体\n面罩内九个发生器':'提供真实含香材料'],['安排到达与时机',detail?'近鼻布局，动作触发\n加热释香与温度反馈':'让气味配合虚拟动作'],['管理刺激与切换',detail?'停止、散热与散味\n管理残留和连续切换':'处理残留与下一次呈现']];
      text(s,'科学基础',110,169,142,45,24,C.blue,true);
      text(s,'装置实现',110,314,142,45,24,C.blue,true);
      text(s,'实际应用',110,452,142,45,24,C.blue,true);
      for(let i=0;i<3;i++){
        text(s,science[i][0],xs[i],166,280,35,25,C.blue,true);
        text(s,science[i][1],xs[i],207,280,67,22,C.ink);
        s.shapes.add({geometry:'downArrow',position:{left:xs[i]+120,top:276,width:26,height:25},fill:C.green,line:{fill:'none',width:0}});
        text(s,engineering[i][0],xs[i],310,280,35,25,C.blue,true);
        text(s,engineering[i][1],xs[i],351,280,63,22,C.ink);
        line(s,xs[i]+132,414,2,C.green,14);
      }
      line(s,392,428,616,C.green,2);
      for(const cx of [470,940])s.shapes.add({geometry:'downArrow',position:{left:cx,top:429,width:22,height:15},fill:C.green,line:{fill:'none',width:0}});
      text(s,detail?'酒窖辨香｜手柄系统':'辨香：气味作为题目',260,448,435,34,24,C.blue,true);
      text(s,detail?'12人，比较单味与混合配方\n单味最高、三味等比最低\n第2、3类差异未显著':'闻香、作答与反馈\n用任务表现评价用途',260,486,435,83,21,C.ink);
      text(s,detail?'放松比较｜环境扩香':'放松：气味作为附加刺激',730,448,435,34,24,C.blue,true);
      text(s,detail?'136人，薰衣草环境扩香\n同触觉条件下比较有香与无香\n未检出额外放松优势':'同条件比较有香与无香\n看是否增加放松收益',730,486,435,83,21,C.ink);
      line(s,110,576,1068,C.green,2);
      text(s,'总结意义',110,592,142,38,24,C.blue,true);
      text(s,detail?'科学约束呈现，任务决定指标\n装置能力与应用收益分别检验':'从感知条件到可控呈现\n再用任务与比较证据判断价值',260,584,900,63,25,C.ink,true);
      break;
    }
    case 'agenda': {
      (d.sections || []).forEach((section,i)=>{
        const y=177+i*104;
        text(s,String(i+1).padStart(2,'0'),104,y,95,65,42,C.green,true);
        text(s,section.title,224,y+1,625,55,35,C.blue,true);
        text(s,section.text,835,y+10,360,52,25,C.muted);
        if(i<3)line(s,224,y+74,971,C.line,1.5);
      });
      break;
    }
    case 'science-transport': {
      const stages=[104,487,870];
      (d.steps || []).forEach((step,i)=>{
        const x=stages[i];
        text(s,step.label,x,190,325,59,32,C.blue,true,i===2?d.backup?.anchor:'');
        text(s,step.text,x,486,325,83,25,C.ink);
        if(i<2)arrow(s,x+321,354,32,C.blue);
      });
      rect(s,183,366,6,90,C.green);
      oval(s,151,399,39,17,'#9CCB72');
      oval(s,187,410,39,17,'#9CCB72');
      for(const [dx,dy] of [[-30,-14],[3,-22],[-29,16],[2,21]]) {
        oval(s,172+dx,340+dy,36,37,'#CFE6BA');
      }
      oval(s,174,344,26,26,C.green);
      arrow(s,228,341,35,'#A6BDCA');
      for(const [x,y] of [[271,337],[298,322],[307,350],[331,312],[338,337],[362,328],[372,301]]) {
        oval(s,x,y,13,13,C.blue);
      }
      // Side profile of the nose and the incoming flow, drawn as editable paths.
      outline(s,555,266,187,196,[
        {moveTo:{x:140,y:12}},
        {cubicBezTo:{x1:80,y1:8,x2:46,y2:42,x:45,y:72}},
        {quadBezTo:{x1:39,y1:100,x:11,y:132}},
        {quadBezTo:{x1:7,y1:142,x:24,y:142}},
        {lineTo:{x:52,y:145}},
        {quadBezTo:{x1:54,y1:174,x:79,y:181}},
        {lineTo:{x:141,y:181}},
      ]);
      outline(s,507,302,187,134,[
        {moveTo:{x:5,y:125}},
        {cubicBezTo:{x1:59,y1:128,x2:128,y2:118,x:125,y:77}},
        {quadBezTo:{x1:125,y1:55,x:101,y:31}},
      ],'#71AB3A',5);
      oval(s,594,318,29,29,'#ABD77F');
      text(s,'嗅觉区域',635,305,148,36,20,C.blue,true);
      for(const [x,y] of [[514,411],[541,402],[564,415]])oval(s,x,y,11,11,C.blue);
      for(const [i,[label,dots]] of [
        ['分子很稀',[[28,55],[96,31]]],
        ['浓度足以察觉',[[24,31],[58,26],[98,35],[44,61],[81,65],[108,57]]],
      ].entries()) {
        const x=872+i*162;
        rect(s,x,301,145,105,i?'#EDF6E7':'#F2F6F8',C.line);
        for(const [dx,dy] of dots)oval(s,x+dx,301+dy,14,14,C.blue);
        text(s,label,x,425,150,36,20,C.blue,i===1);
      }
      text(s,d.caption || '',104,609,1092,43,28,C.blue,true);
      break;
    }
    case 'olfaction': {
      // Editable conceptual diagram; positions are not anatomical coordinates.
      const circles=[[148,256,22],[205,298,16],[260,238,19],[301,316,24],[178,361,18]];
      circles.forEach(([x,y,r],i)=>s.shapes.add({geometry:'ellipse',position:{left:x,top:y,width:r*2,height:r*2},fill:i%2?C.green:C.blue,line:{fill:'none',width:0}}));
      text(s,'气味分子',104,173,270,60,35,C.blue,true);
      text(s,'随吸气到达嗅觉区域',104,475,300,85,27,C.ink);
      arrow(s,391,320,45);
      rect(s,488,267,250,16,'#BED4DE');
      [510,583,656].forEach((x,i)=>{
        rect(s,x,235,14,64,i===1?C.green:C.blue);
        s.shapes.add({geometry:'ellipse',position:{left:x-12,top:312,width:40,height:40},fill:C.pale,line:{fill:C.blue,width:2}});
        rect(s,x+6,352,3,70,C.blue);
      });
      text(s,'受体与感受神经元',463,173,335,60,33,C.blue,true);
      text(s,'化学刺激转成神经信号',466,475,330,85,27,C.ink);
      arrow(s,803,320,45);
      s.shapes.add({geometry:'ellipse',position:{left:903,top:249,width:237,height:89},fill:C.pale,line:{fill:C.blue,width:2}});
      text(s,'嗅球',965,273,120,50,33,C.blue,true);
      s.shapes.add({geometry:'downArrow',position:{left:1003,top:353,width:30,height:44},fill:C.blue,line:{fill:'none',width:0}});
      text(s,'后续脑区',921,410,245,60,33,C.blue,true);
      text(s,'处理信号，形成感受',884,492,310,70,27,C.ink);
      text(s,d.caption || '',104,602,1092,43,28,C.ink);
      break;
    }
    case 'device-detail': {
      await picture(s,d.image,104,186,480,376,'contain');
      text(s,'面罩与气味发生器',104,575,500,48,28,C.blue,true,d.backup?.anchor);
      await picture(s,d.detail_image,620,178,250,273,'contain');
      text(s,'单个发生器',620,479,250,50,27,C.blue,true);
      (d.items || []).forEach((item,i)=>{
        const y=190+i*122;
        text(s,item.label,914,y,280,45,30,C.blue,true);
        text(s,item.text,914,y+49,280,70,25,C.ink);
      });
      if(d.caption)text(s,d.caption,104,623,1092,31,22,C.muted);
      break;
    }
    case 'scent-interaction': case 'task-sequence': {
      await picture(s,d.image,104,171,1092,256,'contain');
      const steps=d.steps || [],gap=50,width=(1092-gap*(steps.length-1))/steps.length;
      steps.forEach((step,i)=>{
        const x=104+i*(width+gap);
        text(s,String(i+1).padStart(2,'0'),x,453,55,38,24,C.green,true);
        text(s,step.label,x,497,width,52,29,C.blue,true,i===1?d.backup?.anchor:undefined);
        text(s,step.text || '',x,553,width,66,24,C.ink);
        if(i<steps.length-1)arrow(s,x+width+8,505,32);
      });
      break;
    }
    case 'odor-cycle': {
      const xs=[330,633,936];
      (d.rows || []).forEach((row,r)=>{
        const y=211+r*188;
        text(s,row.label,104,y+15,200,75,31,C.blue,true);
        row.states.forEach((state,i)=>{
          rect(s,xs[i],y,246,101,r?C.pale:'#F1F7E8');
          text(s,state,xs[i]+17,y+29,215,63,29,C.ink,true,r===1 && i===1?d.backup?.anchor:undefined);
          if(i<2)arrow(s,xs[i]+261,y+40,25);
        });
      });
      text(s,'场景停止后，气味仍可能留在鼻子附近',330,344,850,50,29,C.blue);
      text(s,d.caption || '',104,605,1092,45,28,C.ink);
      break;
    }
    case 'study-result': {
      if(!d.chart_labels) {
        text(s,'任务等级与混合设定',104,175,560,48,30,C.blue,true);
        (d.levels || []).forEach((level,i)=>{
          const y=248+i*83;
          text(s,level.label,104,y,375,49,30,C.ink,true);
          text(s,level.text,104,y+43,400,40,24,C.muted);
        });
        await picture(s,d.image,683,166,492,446,'contain');
        text(s,'每级平均得分（满分8）',690,606,505,36,25,C.blue);
        if(d.caption)text(s,d.caption,104,634,1092,27,19,C.muted);
        break;
      }
      await picture(s,d.image,112,151,450,463,'contain');
      text(s,d.backup?.label || '两种三味配方',610,168,578,43,30,C.blue,true,d.backup?.anchor);
      for(const [i,label] of d.chart_labels.entries()) {
        const y=230+i*119;
        const segments=i?[1/3,1/3,1/3]:[.5,.25,.25];
        text(s,`第${i+3}柱 · ${label}`,610,y,565,43,29,C.ink,true);
        let x=611;
        for(const [j,ratio] of segments.entries()) {
          rect(s,x,y+52,294*ratio-3,20,['#8FCB63','#B5D5E6','#5F92AE'][j]);
          x+=294*ratio;
        }
        text(s,i?'等比例':'50% / 25% / 25%',925,y+43,260,40,22,C.muted);
      }
      line(s,610,465,578);
      text(s,d.intro || (d.takeaways || [])[0],610,489,578,112,31,C.blue,true);
      if(d.caption)text(s,d.caption,104,620,1092,32,19,C.muted);
      break;
    }
    case 'resources': {
      (d.resources || []).forEach((resource,i)=>{
        const x=104+i*575;
        text(s,resource.label,x,180,520,62,33,C.blue,true);
      });
      for(let i=0;i<(d.resources || []).length;i++) {
        const resource=d.resources[i],x=104+i*575;
        await picture(s,resource.qr,x,269,218,218,'contain');
        text(s,resource.text,x+243,310,290,140,28,C.ink);
      }
      if(d.caption)text(s,d.caption,104,572,1092,71,29,C.ink);
      break;
    }
    case 'photo': {
      const side=Boolean(d.side_text || body.length>1);
      await picture(s,d.image,104,165,side?735:1092,side?430:420,d.fit || 'contain');
      if(side) paragraphs(s,d.side_text || body,885,230,310,31,115);
      text(s,d.caption || (!side?body[0]:'') || '',104,602,1092,47,30,C.ink);
      break;
    }
    case 'process': case 'mechanism': case 'timeline': {
      const steps=d.steps || [];
      const count=steps.length;
      const gap=90, width=(1092-gap*(count-1))/count;
      for(let i=0;i<count;i++) {
        const x=104+i*(width+gap), step=steps[i];
        text(s,step.number || String(i+1).padStart(2,'0'),x,190,width,65,42,C.green,true);
        if(step.image) await picture(s,step.image,x,275,width,180);
        text(s,step.label,x,step.image?470:300,width,90,30,C.blue,true);
        text(s,step.text || '',x,step.image?565:420,width,130,25,C.ink);
        if(i<count-1) arrow(s,x+width+30,step.image?350:310,30);
      }
      if(d.caption || body[0]) text(s,d.caption || body[0],104,602,1092,47,29,C.ink);
      break;
    }
    case 'receptors': {
      const receptors=d.receptor_labels || ['受体A','受体B','受体C','受体D'];
      const rows=d.odors || [];
      const x0=360, cellW=190, rowH=112;
      receptors.forEach((r,i)=>text(s,r,x0+i*cellW,180,cellW,55,29,C.blue,true));
      rows.forEach((odor,r)=>{
        const y=270+r*rowH;
        text(s,odor.label,104,y-3,235,66,35,C.ink,true);
        receptors.forEach((_,c)=>s.shapes.add({geometry:'ellipse',position:{left:x0+48+c*cellW,top:y,width:46,height:46},fill:odor.active.includes(c)?C.blue:'#E3EAED',line:{fill:'none',width:0}}));
      });
      text(s,d.caption || '组合编码教学示意，圆点不表示实测强度',104,602,1092,47,28,C.muted);
      break;
    }
    case 'formal-references': {
      const title=s.shapes.items.find(shape=>shape.name==='headline');
      title.text.style={typeface:'宋体',fontSize:43,color:C.ink,bold:true};
      const writeLine=(value,x,y,w,h,size,bold=false)=>{
        const item=text(s,value,x,y,w,h,size,C.ink,bold);
        item.text.style={typeface:'Times New Roman',fontSize:size,color:C.ink,bold};
      };
      rect(s,632,147,1,473,'#D5DEE0');
      d.entries.forEach((ref,i)=>{
        const x=i<4?104:661, y=146+(i%4)*123;
        writeLine('['+(i+1)+']',x,y,40,29,22,true);
        writeLine(ref.author,x+45,y,490,28,22,true);
        writeLine(ref.title,x+45,y+30,471,63,18);
        writeLine(ref.journal+'  DOI '+ref.doi,x+45,y+93,490,28,16);
      });
      const note=s.shapes.items.find(shape=>shape.name==='source-footer');
      note.text.style={typeface:'宋体',fontSize:17,color:C.muted};
      break;
    }
    case 'receptor-overlap': {
      text(s,d.backup?.label || '小鼠嗅觉受体的实测响应',104,151,900,42,26,C.blue,true,d.backup?.anchor);
      text(s,'测试分子',104,215,190,48,26,C.muted,true);
      d.receptors.forEach((receptor,i)=>text(s,receptor,322+i*294,215,268,53,29,C.blue,true));
      d.odors.forEach((odor,row)=>{
        const y=284+row*111;
        text(s,odor.label,104,y+20,192,54,34,C.ink,true);
        d.receptors.forEach((_,column)=>{
          const x=322+column*294, active=odor.active.includes(column);
          rect(s,x,y,268,89,active?(column===1?'#E9F5DF':'#EDF4F9'):'#F6F8F9');
          text(s,active?'有响应':'未见响应',x+18,y+20,232,57,32,active?C.blue:C.muted,active);
        });
      });
      text(s,d.caption,104,535,1092,51,32,C.blue,true);
      text(s,'节选原图三种小鼠嗅觉受体，A、B、C 为讲解用简称。',104,600,1092,42,24,C.muted);
      break;
    }
    case 'requirements': {
      const items=d.items || [];
      if(items.length!==3)throw new Error(`${d.id}: requirements needs three concrete items`);
      items.forEach((item,i)=>{
        const x=104+i*380;
        text(s,item.label,x,245,320,70,40,C.blue,true);
        line(s,x,340,300,C.green,5);
        text(s,item.text,x,385,320,150,31,C.ink);
      });
      if(d.caption)text(s,d.caption,104,600,1092,47,28,C.ink);
      break;
    }
    case 'device': {
      await picture(s,d.image,104,180,520,405,'contain');
      (d.items || []).forEach((item,i)=>{
        const y=200+i*126;
        text(s,item.label,690,y,500,48,34,C.blue,true);
        text(s,item.text,690,y+53,500,62,28,C.ink);
      });
      if(d.caption)text(s,d.caption,104,602,1092,43,25,C.muted);
      break;
    }
    case 'response': {
      text(s,'发生器温度随时间变化（原图）',104,173,730,42,26,C.blue);
      await picture(s,d.image,104,240,720,290,'contain');
      (d.items || []).forEach((item,i)=>{
        const y=235+i*175;
        text(s,item.label,875,y,320,52,31,C.blue,true);
        text(s,item.text,875,y+62,320,100,28,C.ink);
      });
      if(d.caption)text(s,d.caption,104,600,1092,48,25,C.ink);
      break;
    }
    case 'compare': {
      const cols=d.columns || [];
      const start=d.intro?211:175;
      if(d.intro && d.backup && d.intro.startsWith('香芹酮')) {
        text(s,'香芹酮',104,145,98,53,25,C.blue,true,d.backup.anchor);
        text(s,d.intro.slice('香芹酮'.length),200,145,996,53,25,C.ink);
      } else if(d.intro)text(s,d.intro,104,145,1092,57,25,C.ink,false,d.backup?.anchor);
      for(let i=0;i<cols.length;i++) {
        const col=cols[i],x=104+i*570;
        text(s,col.label,x,start,520,65,36,C.blue,true);
        if(col.image) await picture(s,col.image,x,d.intro?285:260,520,d.intro?237:270);
        const terms=String(col.text || '').split('\n').filter(Boolean);
        if(!col.image && terms.length===2) {
          text(s,terms[0],x,290,520,70,38,C.ink);
          s.shapes.add({geometry:'downArrow',position:{left:x+64,top:380,width:28,height:44},fill:C.blue,line:{fill:'none',width:0}});
          text(s,terms[1],x,450,520,70,38,C.ink);
        } else text(s,col.text || '',x,col.image?(d.intro?548:565):295,520,col.image?61:250,29,C.ink);
      }
      if(body[0])text(s,body[0],104,615,1092,38,28,C.ink);
      break;
    }
    case 'experiment': {
      text(s,d.caption || body[0] || '',104,185,1092,70,33,C.ink);
      const conditions=d.conditions || [];
      const spec=d.table || {headers:['气味条件','无触觉','有触觉'],rows:[['无香',conditions[0]?.text || '',conditions[2]?.text || ''],['有香',conditions[1]?.text || '',conditions[3]?.text || '']]};
      const matrix=nativeTable(s,{...d,table:{fontSize:32,widths:[1.1,1.3,1.3],...spec}},n,{left:190,top:310,width:920,height:260});
      for(let r=1;r<=2;r++) {
        matrix.getCell(r,0).fill=C.blue;
        matrix.getCell(r,0).text.style={typeface:FONT,fontSize:32,color:C.white,bold:true};
      }
      break;
    }
    case 'results': {
      const c=d.chart;
      if(!c?.categories?.length || !c?.series?.length) throw new Error(`${d.id}: results requires chart data`);
      for(const series of c.series) if(series.values.length!==c.categories.length) throw new Error(`${d.id}: chart values/category mismatch`);
      const wide=!(d.takeaways?.length);
      const chart=s.charts.add(c.type || 'bar',{
        position:{left:104,top:180,width:wide?1092:810,height:430},
        categories:c.categories,series:c.series.map((v,i)=>({name:v.name,values:v.values,fill:v.color || [C.blue,C.green,'#7296AA','#B5C8D0'][i%4]})),
        hasLegend:c.series.length>1,legend:{position:'bottom',textStyle:{typeface:FONT,fontSize:21}},
        barOptions:{direction:c.direction || 'column',grouping:'clustered',gapWidth:95},
        dataLabels:{showValue:true,position:'outEnd',textStyle:{fontSize:23,fill:C.ink}},
        chartFill:C.white,plotAreaFill:C.white,
        xAxis:{textStyle:{typeface:FONT,fontSize:c.category_font_size || 23},majorGridlines:{fill:'none',width:0}},
        yAxis:{min:c.yMin ?? 0,max:c.yMax,numberFormatCode:c.format || '0.0',textStyle:{fontSize:20},majorGridlines:{fill:C.line,width:1}},
      });
      applyPresentationChartFont(chart,{fontFamily:FONT});
      if(c.yTitle)text(s,c.yTitle,104,143,810,36,22,C.muted,false,d.backup?.anchor);
      if(!wide)paragraphs(s,d.takeaways,950,245,245,30,135,C.ink);
      if(d.caption)text(s,d.caption,104,617,1092,35,24,C.muted);
      nativeCharts.push(n);
      break;
    }
    case 'evidence': {
      nativeTable(s,d,n,{left:104,top:185,width:1092,height:d.takeaways?.length?335:420});
      if(d.takeaways?.length)paragraphs(s,d.takeaways,104,553,1092,30,65);
      break;
    }
    case 'judgment': {
      text(s,d.question || body[0] || '',104,185,1092,110,42,C.ink,true);
      const alts=d.alternatives || [];
      alts.forEach((a,i)=>{
        const y=350+i*130;
        text(s,a.label,104,y,320,75,30,C.blue,true);
        text(s,a.text,450,y,746,95,33,C.ink);
      });
      if(body[0])text(s,body[0],104,615,1092,38,27,C.muted);
      break;
    }
    case 'application-summary': {
      text(s,d.question,104,150,1092,48,27,C.ink,true);
      d.alternatives.forEach((a,i)=>{
        const y=226+i*142;
        text(s,a.label,104,y+6,180,45,30,C.blue,true);
        text(s,a.text,320,y,860,96,27,C.ink);
      });
      d.lines.forEach((line,i)=>text(s,line,104,512+i*54,1092,64,34,C.blue,true));
      break;
    }
    case 'closing': {
      if(d.image)await picture(s,d.image,860,210,335,340,'cover');
      paragraphs(s,d.lines || body,104,215,d.image?710:1092,39,d.image?115:135,C.blue);
      if(d.caption || body[0])text(s,d.caption || body[0],104,609,1092,45,27,C.muted);
      break;
    }
    case 'references': {
      (d.entries || []).forEach((entry,i)=>{
        const y=171+i*80;
        text(s,entry.label || '',104,y,130,65,24,C.blue,true);
        text(s,entry.text || '',245,y,950,65,23,C.ink);
      });
      break;
    }
    case 'contributions': {
      nativeTable(s,d,n,{left:104,top:160,width:1092,height:470});
      break;
    }
    default: {
      if(!d.elements?.length) throw new Error(`${d.id}: unknown layout ${d.layout}`);
      break;
    }
  }
  for(const el of d.elements || []) {
    const frame=el.position || {left:el.x,top:el.y,width:el.w,height:el.h};
    if(el.type==='image')await picture(s,el.image || el.path,frame.left,frame.top,frame.width,frame.height,el.fit);
    else if(el.type==='text')text(s,el.text,frame.left,frame.top,frame.width,frame.height,el.size || 30,el.color || C.ink,el.bold || false,el.name || '');
    else if(el.type==='arrow')arrow(s,frame.left,frame.top,frame.width,el.color);
    else if(el.type==='rect')rect(s,frame.left,frame.top,frame.width,frame.height,el.fill,el.stroke,el.name);
    else throw new Error(`${d.id}: unsupported element type ${el.type}`);
  }
  const visibleChars=(d.title || '').length+body.join('').length;
  if(d.role==='main' && visibleChars>100)warnings.push(`${d.id}: review visible copy length`);
  return s;
}

for(let i=0;i<source.slides.length;i++)await render(source.slides[i],i+1);
await fs.mkdir(path.dirname(output),{recursive:true});
await (await PresentationFile.exportPptx(p)).save(output);
const mediaCheck=verifyMedia(output);
await fs.writeFile(output.replace(/\.pptx$/i,'.media-check.json'),JSON.stringify(mediaCheck,null,2)+'\n','utf8');
const manifest={input:path.relative(ROOT,input),output:path.relative(ROOT,output),slides:source.slides.length,main_count:source.slides.filter(x=>x.role==='main').length,main_seconds:source.slides.filter(x=>x.role==='main').reduce((a,b)=>a+(b.seconds || 0),0),native_tables:nativeTables,native_charts:nativeCharts,template_reference:'诗意校园·2022蓝绿青春',template_layouts:['标题和内容（一般样式）','空白（纯白，无底边）'],warnings,missing_assets:[...new Set(missingAssets)],slide_ids:ids};
if(args.includes('--subdecks')) {
  manifest.subdecks=[];
  for(const [group,name] of [['1','group-01-science'],['2','group-02-technology'],['3','group-03-applications']]) {
    const indexes=source.slides.map((s,i)=>Number(s.group)===Number(group)?i:-1).filter(i=>i>=0);
    if(!indexes.length)continue;
    const sub=await PresentationFile.importPptx(await FileBlob.load(output));
    sub.slides.keep(indexes);
    const dest=path.join(path.dirname(output),name+'.pptx');
    await (await PresentationFile.exportPptx(sub)).save(dest);
    verifyMedia(dest);
    const subsetSlides=indexes.map(i=>source.slides[i]);
    const subManifest={...manifest,output:path.relative(ROOT,dest),slides:indexes.length,main_count:subsetSlides.filter(x=>x.role==='main').length,main_seconds:subsetSlides.reduce((sum,x)=>sum+(x.seconds || 0),0),native_tables:nativeTables.filter(n=>indexes.includes(n-1)).map(n=>indexes.indexOf(n-1)+1),native_charts:nativeCharts.filter(n=>indexes.includes(n-1)).map(n=>indexes.indexOf(n-1)+1),slide_ids:subsetSlides.map(x=>x.id)};
    delete subManifest.subdecks;
    await fs.writeFile(path.join(path.dirname(output),name+'.manifest.json'),JSON.stringify(subManifest,null,2)+'\n','utf8');
    manifest.subdecks.push({group,path:path.relative(ROOT,dest),source_indexes:indexes.map(i=>i+1),slides:indexes.length});
  }
}
await fs.writeFile(path.join(path.dirname(output),'build-manifest.json'),JSON.stringify(manifest,null,2)+'\n','utf8');
await fs.writeFile(output.replace(/\.pptx$/i,'.manifest.json'),JSON.stringify(manifest,null,2)+'\n','utf8');
console.log(JSON.stringify(manifest));
