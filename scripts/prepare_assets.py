"""Crop licensed source figures without redrawing scientific evidence."""
from pathlib import Path
from PIL import Image
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'research/2026-11-01/deep-review/assets'
dest = ROOT / 'assets'
dest.mkdir(exist_ok=True)
items = [
    ('P02-Fig5.jpg', 'flower-vr.jpg', (0, 0, 668, 276), 'P02', 'Fig.5a，场景与系统示意'),
    ('P02-Fig5.jpg', 'flower-vr-sequence.jpg', (0, 282, 212, 692), 'P02', 'Fig.5b，三段虚拟动作与真人对应画面'),
    ('P02-Fig1.png', 'wearable-device.jpg', (0, 1624, 2003, 2242), 'P02', 'Fig.1d–e，两个装置的实物照片'),
    ('P02-Fig1.png', 'wearable-close.jpg', (431, 1930, 850, 2240), 'P02', 'Fig.1d右下，上唇装置照片，保留尺度'),
    ('P05-Fig5.png', 'handheld-sniff.jpg', (473, 0, 947, 503), 'P05', 'Fig.5b，真人使用手持装置'),
    ('P05-Fig5.png', 'wine-cellar-task.jpg', (0, 0, 1645, 503), 'P05', 'Fig.5a–c，酒窖、闻香、选择气味成分')
]
credits = []
for original, name, crop, paper, location in items:
    img = Image.open(source / original)
    img.crop(crop).convert('RGB').save(dest / name, quality=95, subsampling=0)
    credits.append({'file':name,'paper':paper,'original':f'research/2026-11-01/deep-review/assets/{original}','location':location,'crop_pixels':crop,'license':'CC BY 4.0','modification':'仅裁剪并转JPEG，科学内容未重绘','source_url':'https://doi.org/10.1038/s41467-023-37678-4' if paper=='P02' else 'https://doi.org/10.1016/j.ijhcs.2022.102928','sha256':hashlib.sha256((dest/name).read_bytes()).hexdigest()})
frames = ROOT / '.git/production-20261101/video-frames'
if (frames / 'frame-01.png').exists():
    frame=Image.open(frames/'frame-05.png')
    # Screenshot dimensions differ from the encoded video's dimensions.
    frame.crop((660,0,frame.width,frame.height)).convert('RGB').save(dest/'flower-vr.jpg',quality=95,subsampling=0)
    triptych = Image.new('RGB',(1920,360),'white')
    for index,time in enumerate([1,5,13]):
        im=Image.open(frames/f'frame-{time:02}.png').convert('RGB')
        im=im.resize((640,360),Image.Resampling.LANCZOS)
        triptych.paste(im,(index*640,0))
    triptych.save(dest/'flower-vr-sequence.jpg',quality=95,subsampling=0)
    for credit in credits[:2]:
        credit.update({'original':'P02 Supplementary Movie3','location':'视频1／5／13秒真实帧；封面为5秒帧裁剪','modification':'原视频逐帧渲染后裁剪或并排，无生成内容','sha256':hashlib.sha256((dest/credit['file']).read_bytes()).hexdigest()})
Image.open(source/'P02-Fig5.jpg').crop((213,595,668,706)).convert('RGB').save(dest/'temperature-response.jpg',quality=95,subsampling=0)
credits.append({'file':'temperature-response.jpg','paper':'P02','original':'research/2026-11-01/deep-review/assets/P02-Fig5.jpg','location':'Fig.5d，发生器温度随演示变化','crop_pixels':[213,595,668,706],'license':'CC BY 4.0','modification':'仅裁剪原图，未估读或重绘数据','source_url':'https://doi.org/10.1038/s41467-023-37678-4','sha256':hashlib.sha256((dest/'temperature-response.jpg').read_bytes()).hexdigest()})
(dest/'credits.json').write_text(json.dumps(credits,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(dest/'README.md').write_text('# 主讲素材\n\n本目录图片来自P02与P05原论文的CC BY图，具体图号、来源、裁剪与哈希见[credits.json](credits.json)。裁剪用于投影可读性，原始图保存在research/2026-11-01/deep-review/assets。\n\n图像中的原研究示意、真人照片和实验结果按原图性质使用；过程图由本组另作可编辑教学示意。\n',encoding='utf-8')
print('Prepared',len(credits),'licensed image crops')
