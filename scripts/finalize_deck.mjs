/** Validate a private candidate and create a separate final PPTX. */
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const argv=process.argv.slice(2);
const opt=(name,fallback)=>{const i=argv.indexOf(name);return i<0?fallback:argv[i+1];};
const candidate=path.resolve(ROOT,opt('--candidate','.git/production-20261101/build/candidate.pptx'));
const finalPath=path.resolve(ROOT,opt('--output','release/v1/olfaction-vr-v1.pptx'));
const manifestPath=path.resolve(ROOT,opt('--manifest',candidate.replace(/\.pptx$/i,'.manifest.json')));
const manifest=JSON.parse(await fs.readFile(manifestPath,'utf8'));
if(manifest.missing_assets?.length)throw new Error('Candidate has missing images: '+manifest.missing_assets.join(', '));
const template=opt('--template',process.env.OLFACTION_TEMPLATE);
if(!template)throw new Error('Provide the selected original --template for font/reference verification');
const referencePath=path.resolve(template);
const referenceSha256=crypto.createHash('sha256').update(await fs.readFile(referencePath)).digest('hex');
const SKILL=process.env.PRESENTATION_SKILL_DIR || 'C:/Users/Cyh29hao/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations';
process.env.RUNTIME_NODE_MODULES=process.env.RUNTIME_NODE_MODULES || 'C:/Users/Cyh29hao/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {finalizePresentation}=await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
await fs.mkdir(path.dirname(finalPath),{recursive:true});
const candidateHash=crypto.createHash('sha256').update(await fs.readFile(candidate)).digest('hex').slice(0,12);
const recordStem=path.basename(path.dirname(finalPath))+'.'+path.basename(finalPath)+'.'+candidateHash;
const receiptDir=path.join(path.dirname(candidate),'receipts');
await fs.mkdir(receiptDir,{recursive:true});
const receipt=path.join(receiptDir,recordStem+'.validation.json');
// Imported templates can retain unused layouts and their pictures. Remove only
// unreferenced resources in a separate candidate before the standard validators.
const cleanCandidate=candidate.replace(/\.pptx$/i,'.trimmed.pptx');
const pythonExecutable=process.env.RUNTIME_PYTHON || 'C:/Users/Cyh29hao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';
const pruneCode=String.raw`
import sys,json,posixpath,re,io
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from PIL import Image
src,dst=map(Path,sys.argv[1:3])
with ZipFile(src) as z: parts={n:z.read(n) for n in z.namelist()}
NSR='http://schemas.openxmlformats.org/package/2006/relationships'
NSP='http://schemas.openxmlformats.org/presentationml/2006/main'
NSO='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def target_part(rels_name,target):
    owner=rels_name.replace('/_rels/','/').removesuffix('.rels')
    return posixpath.normpath(posixpath.join(posixpath.dirname(owner),target)).lstrip('/')
used=set()
for name,data in list(parts.items()):
    if re.match(r'ppt/slides/_rels/[^/]+\.rels$',name):
        for rel in E.fromstring(data):
            if rel.get('Type','').endswith('/slideLayout'):
                used.add(target_part(name,rel.get('Target')))
layouts={name for name in parts if re.match(r'ppt/slideLayouts/[^/]+\.xml$',name)}
unused=layouts-used
removed=set(unused)
for layout in unused:
    relname=posixpath.dirname(layout)+'/_rels/'+posixpath.basename(layout)+'.rels'
    removed.add(relname)
for name,data in list(parts.items()):
    if re.match(r'ppt/slideMasters/_rels/[^/]+\.rels$',name):
        rels=E.fromstring(data); dropped=[]
        for rel in list(rels):
            if rel.get('Type','').endswith('/slideLayout') and target_part(name,rel.get('Target')) in unused:
                dropped.append(rel.get('Id')); rels.remove(rel)
        if dropped:
            owner=name.replace('/_rels/','/').removesuffix('.rels')
            master=E.fromstring(parts[owner])
            for item in master.findall('.//{'+NSP+'}sldLayoutId'):
                if item.get('{'+NSO+'}id') in dropped:item.getparent().remove(item)
            parts[owner]=E.tostring(master,xml_declaration=True,encoding='UTF-8',standalone=True)
            parts[name]=E.tostring(rels,xml_declaration=True,encoding='UTF-8',standalone=True)
for name in removed:parts.pop(name,None)
referenced=set()
for name,data in parts.items():
    if name.endswith('.rels'):
        for rel in E.fromstring(data):
            if rel.get('TargetMode')!='External':referenced.add(target_part(name,rel.get('Target','')))
media={name for name in parts if name.startswith('ppt/media/')}
unreferenced=media-referenced
for name in unreferenced:parts.pop(name,None)
removed.update(unreferenced)
ct=E.fromstring(parts['[Content_Types].xml'])
for node in list(ct):
    if node.get('PartName','').lstrip('/') in removed:ct.remove(node)
parts['[Content_Types].xml']=E.tostring(ct,xml_declaration=True,encoding='UTF-8',standalone=True)
checked_images=[]
for name,data in parts.items():
    if not name.startswith('ppt/media/'):continue
    if not data:raise ValueError('Empty embedded media: '+name)
    if Path(name).suffix.lower() in ['.png','.jpg','.jpeg','.gif','.webp','.bmp','.tif','.tiff']:
        with Image.open(io.BytesIO(data)) as image:image.verify()
    checked_images.append({'part':name,'bytes':len(data)})
with ZipFile(dst,'w',ZIP_DEFLATED) as z:
    for name,data in parts.items():z.writestr(name,data)
print(json.dumps({'unused_layouts_removed':len(unused),'unreferenced_media_removed':len(unreferenced),'before_bytes':src.stat().st_size,'after_bytes':dst.stat().st_size,'nonempty_media':True,'raster_decode':'passed','media':checked_images}))
`;
const pruned=spawnSync(pythonExecutable,['-X','utf8','-c',pruneCode,candidate,cleanCandidate],{encoding:'utf8'});
if(pruned.status!==0)throw new Error('Template resource cleanup failed: '+pruned.stderr);
await fs.writeFile(path.join(receiptDir,recordStem+'.resource-trim.json'),pruned.stdout,'utf8');
const result=await finalizePresentation({
  workspaceDir:ROOT,candidatePath:cleanCandidate,finalPath,
  explicitTotalSlideCount:manifest.slides,
  pythonExecutable,
  integrityValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath:path.join(SKILL,'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit','--validate-bullet-geometry',...(manifest.native_tables || []).flatMap(n=>['--require-native-table-slide',String(n)])],
  fontPolicy:{basis:'reference',families:['微软雅黑','Arial'],referencePath,referenceSha256},
  requiredNativeChartOwnerSlides:manifest.native_charts || [],
  requiredNativeTableOwnerSlides:manifest.native_tables || [],
  materializeLiteralChartWorkbooks:true,
  verifyArtifactToolImport:true,receiptPath:receipt,
});
console.log(JSON.stringify({output:result.finalPath,sha256:result.finalSha256,receipt}));
