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
const skillDir=process.env.PRESENTATION_SKILL_DIR || 'C:/Users/Cyh29hao/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
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
if (source.slides.length > 1 && last.layout !== 'contributions') throw new Error('The last physical slide must be contributions');
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
    text(s,d.title,104,38,1092,90,44,C.blue,true,'headline');
    text(s,d.footer || (d.source_ids || []).map(x=>`[${x}]`).join('  '),104,660,1060,33,16,C.muted,false,'source-footer');
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
    case 'compare': {
      const cols=d.columns || [];
      for(let i=0;i<cols.length;i++) {
        const col=cols[i],x=104+i*570;
        text(s,col.label,x,175,520,65,36,C.blue,true);
        if(col.image) await picture(s,col.image,x,260,520,270);
        const terms=String(col.text || '').split('\n').filter(Boolean);
        if(!col.image && terms.length===2) {
          text(s,terms[0],x,290,520,70,38,C.ink);
          s.shapes.add({geometry:'downArrow',position:{left:x+64,top:380,width:28,height:44},fill:C.blue,line:{fill:'none',width:0}});
          text(s,terms[1],x,450,520,70,38,C.ink);
        } else text(s,col.text || '',x,col.image?565:295,520,col.image?76:250,29,C.ink);
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
        xAxis:{textStyle:{typeface:FONT,fontSize:23},majorGridlines:{fill:'none',width:0}},
        yAxis:{min:c.yMin ?? 0,max:c.yMax,numberFormatCode:c.format || '0.0',textStyle:{fontSize:20},majorGridlines:{fill:C.line,width:1}},
      });
      applyPresentationChartFont(chart,{fontFamily:FONT});
      if(c.yTitle)text(s,c.yTitle,104,143,810,36,22,C.muted);
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
