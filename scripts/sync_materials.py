"""Keep the talk, group packets and source handout aligned with editable content."""
from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {'00': '00-integration', '01': '01-science', '02': '02-technology', '03': '03-applications'}
LABELS = {'00': '开场、收束与整合', '01': '科学原理', '02': '技术与设备', '03': '多感官与应用'}
LEGACY_JOINS = {'00':'用闻花动作引出问题；最后回到装置与实际用途，帮助听众带走判断方法。', '01':'接住“鼻子怎样闻到花香”；讲到软件可以描述气味之后，把“怎样送到鼻子”交给技术组。', '02':'接住“鼻子还需要实际刺激”；讲清释放、同步与退味，再用手持装置把“能用来做什么”交给应用组。', '03':'接住手持装置；先看辨香游戏，再用放松研究展示怎样比较额外收益，交给第0组练习判断宣传。'}

def as_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return '\n\n'.join(as_text(item) for item in value)
    if isinstance(value, dict):
        labels = {'incoming':'接住', 'receive':'接住', 'outgoing':'交给下一段', 'deliver':'交给下一段', 'core':'本段重点'}
        return '\n\n'.join(f'{labels.get(key, key)}：{as_text(item)}' for key, item in value.items())
    return str(value) if value is not None else ''

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    assert path.read_text(encoding='utf-8') == text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', action='store_true', help='Initialize group JSON from the assembled content; never use over unmerged group work.')
    parser.add_argument('--version', help='Release version; defaults to deck.version, then v1.')
    parser.add_argument('--production-dir', type=Path, help='Private checkpoint directory.')
    args = parser.parse_args()
    master = ROOT / 'content/deck.json'
    deck = json.loads(master.read_text(encoding='utf-8'))
    version = args.version or deck.get('version', 'v1')
    if not re.fullmatch(r'v[\w.-]+', version):
        raise ValueError('Invalid version: ' + version)
    if deck.get('version', 'v1') != version:
        raise ValueError('Requested version does not match content/deck.json; sync the intended source first.')
    release = ROOT / 'release' / version
    production = args.production_dir or Path('.git/production-20261101' if version == 'v1' else f'.git/production-{version}')
    production = ROOT / production
    if args.split:
        for group, folder in GROUPS.items():
            part = {k: v for k, v in deck.items() if k != 'slides'}
            part['slides'] = [s for s in deck['slides'] if s['group'] == group]
            write(ROOT / 'groups' / folder / 'content.json', json.dumps(part, ensure_ascii=False, indent=2) + '\n')
    else:
        changes = {}
        for folder in GROUPS.values():
            p = ROOT / 'groups' / folder / 'content.json'
            if p.exists():
                part = json.loads(p.read_text(encoding='utf-8'))
                if part.get('version', 'v1') != version:
                    raise ValueError(f'{p}: group content version differs; preserve/merge its work before initializing the new version.')
                for slide in part['slides']:
                    if slide['id'] in changes:
                        raise ValueError('Duplicate module ID: ' + slide['id'])
                    changes[slide['id']] = slide
        known = {s['id'] for s in deck['slides']}
        if set(changes) - known:
            raise ValueError('New IDs require integration order review: ' + str(set(changes) - known))
        deck['slides'] = [changes.get(s['id'], s) for s in deck['slides']]
        write(master, json.dumps(deck, ensure_ascii=False, indent=2) + '\n')
    ids = [s['id'] for s in deck['slides']]
    assert len(set(ids)) == len(ids)
    assert deck['slides'][-1]['role'] == 'contributions'
    sources = deck['sources']
    main_slides = [s for s in deck['slides'] if s['role'] == 'main']
    spoken_seconds = sum(s['seconds'] for s in main_slides)
    total_budget = deck.get('presentation_seconds', 720)
    reserve = deck.get('transition_reserve_seconds', total_budget - spoken_seconds)
    assert 0 <= reserve and spoken_seconds + reserve <= total_budget, (spoken_seconds, reserve, total_budget)
    full = ['# 全场口播', '', f"对应{version}的{len(main_slides)}页主讲，{deck.get('speaker_count', 4)}人讲述。内容设计预算{spoken_seconds}秒，另留{reserve}秒换人和停顿；问答另计2–3分钟。真人计时后再调整。", '', '第0组负责开场与收束；其余三位依次讲科学原理、技术设备、多感官与应用。具体发言人由组内决定。页脚来源无需朗读。', '']
    for group, folder in GROUPS.items():
        selected = [s for s in main_slides if s['group'] == group]
        seconds = sum(s['seconds'] for s in selected)
        lines = [f'# 本组文稿：{LABELS[group]}', '', f'设计内容预算：{seconds}秒。页面与全场口播来自同一份内容；可直接改文字、标注意见，或交回本组PPT副本。', '', '## 这段接住什么、交给下一段什么', '']
        handoffs = deck.get('group_handoffs', {})
        handoff = handoffs.get(group, handoffs.get(str(int(group))))
        fallback = LEGACY_JOINS[group] if version == 'v1' else '本组交接说明待统筹补充。'
        lines.extend([as_text(handoff) if handoff is not None else fallback, '', '## 可直接讲的口播', ''])
        for slide in selected:
            n = ids.index(slide['id']) + 1
            block = [f"### {n:02} {slide['title']}（{slide['id']}，预算{slide['seconds']}秒）", '', slide['script'], '']
            lines.extend(block)
            lines.extend(['看图提示：' + visual_hint(slide), '', '来源定位：' + '；'.join(slide.get('source_locations', [])), ''])
        used = list(dict.fromkeys(i for s in selected for i in s['source_ids']))
        lines.extend(['## 本组先打开这些来源', ''])
        lines.extend([f"- [{sid} {sources[sid]['title']}]({sources[sid]['url']})：{sources[sid]['location']}" for sid in used])
        lines.extend(['', 'AI已按记录范围查阅。小组核改时，请成员亲自打开关键原始来源；把实际复核人和日期写在建议或PR里。', ''])
        write(ROOT / 'groups' / folder / '本组文稿.md', '\n'.join(lines))
    # Restore real presentation order: group 0's closing belongs at the end.
    for slide in main_slides:
        n = ids.index(slide['id']) + 1
        full.extend([f"## {n:02} {slide['title']}（{slide['id']}，预算{slide['seconds']}秒）", '', slide['script'], ''])
    compression = deck.get('compression_notes', '优先保留闻花动作、完整释香流程、放松试验的对照与结尾。赶时间时先缩短S03的模型例子和T05的两种形态比较。视频或动画仅辅助解释，静态画面即可完成讲述。' if version == 'v1' else '先按全场预算试讲，由统筹确定需要压缩的位置。')
    full.extend(['## 试讲时怎么压缩', '', as_text(compression), ''])
    write(release / '全场口播.md', '\n'.join(full))
    refs = ['# 来源手册', '', f'版本：{version}。记录AI实际查阅及原文位置，供成员打开原文复核。AI检查不计作人工复核。文献综览的广度与主讲证据的深度分别保留。', '', '## 逐页追溯', '', '| 页面 | 来源 | 原文定位 |', '| --- | --- | --- |']
    for n, slide in enumerate(deck['slides'], 1):
        citations = '、'.join(f"[{i}]({sources[i]['url']})" for i in slide['source_ids']) or '已确认分组名单'
        locations = '；'.join(slide.get('source_locations', [])) or '2026-10-29用户提供名单；具体贡献待填写'
        refs.append(f"| {n:02} {slide['id']} | {citations} | {locations} |")
    refs.extend(['', '## 完整题录与本轮读取范围', ''])
    for sid, source in sources.items():
        refs.extend([f"### {sid} {source['title']}", '', f"{source.get('authors', '')}，{source.get('year', '')}。原始入口：{source['url']}", '', f"定位：{source.get('location', '')}。", '', f"材料使用：{source.get('license', '按原始来源核对使用条件')}。", ''])
        if source.get('fulltext'):
            refs.extend([f"作者／原文入口：{source['fulltext']}", ''])
        if source.get('correction'):
            refs.extend([f"更正：{source['correction']}。{source.get('correction_summary', '')}", ''])
    if version == 'v1':
        refs.extend(['## 放松图的准确口径', '', 'P15作者稿Table1；VAS 0–10。组别人数依次34、36、33、33。图绘制均值，未将SD画成置信区间。', '', '| 组别 | 体验前均值±SD | 体验后均值±SD |', '| --- | --- | --- |', '| VR | 6.06±2.28 | 7.78±1.75 |', '| VR＋香味 | 6.17±2.23 | 8.14±1.79 |', '| VR＋触觉 | 6.76±1.98 | 8.33±1.68 |', '| 两者都加 | 6.70±2.22 | 7.88±1.98 |', '', '整体前后F(1,132)=90.31，p<.001。作者报告未检出加香对情绪／在场感的额外改善；原文未给该项精确F/p，保留原报告层级。研究为健康参与者、投影式VR、薰衣草扩香，不能直接当成现代头戴式精准释香装置的临床试验。', '', '作者稿§2.6有Smell/Touch说明对调的文字笔误；按Fig.3与§2.7核正。详见deep-review/application的核验记录。', '', '## 图片与开放资料', '', '主讲使用P02与P05的CC BY原图裁剪，图号、原始入口及裁剪方式见assets/credits.json。未公开原模板文件或其他课程私人预览。其余机制与过程为可编辑教学示意，图中位置、长度与颜色不充当实测值。', ''])
    else:
        for slide in deck['slides']:
            if slide.get('layout') != 'results':
                continue
            chart = slide['chart']
            refs.extend([f"## {slide['id']} 图表数据", '', chart.get('yTitle', ''), '', '| 条件 | ' + ' | '.join(s['name'] for s in chart['series']) + ' |', '| --- | ' + ' | '.join('---' for _ in chart['series']) + ' |'])
            for index, category in enumerate(chart['categories']):
                refs.append('| ' + category + ' | ' + ' | '.join(str(s['values'][index]) for s in chart['series']) + ' |')
            refs.extend(['', '原文定位：' + '；'.join(slide.get('source_locations', [])), ''])
        if deck.get('evidence_notes'):
            refs.extend(['## 数据解释与适用范围', '', as_text(deck['evidence_notes']), ''])
        refs.extend(['## 图片与开放资料', '', '图片原始入口、图号和裁剪方式见assets/credits.json；机制教学示意与实测结果分别标明。', ''])
    write(release / '来源手册.md', '\n'.join(refs))
    verification = {'version':version,'slide_ids':ids,'main_ids':[s['id'] for s in main_slides],'spoken_seconds_budget':spoken_seconds,'transition_reserve_seconds':reserve,'presentation_seconds':total_budget,'main_script_characters':sum(len(s['script']) for s in main_slides),'group_slide_ids':{g:[s['id'] for s in main_slides if s['group']==g] for g in GROUPS},'last_slide':deck['slides'][-1]['id'],'human_rehearsal':False}
    write(production / 'content-check.json', json.dumps(verification,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(verification,ensure_ascii=False))

def visual_hint(slide):
    return {'photo':'先指动作或装置，再解释，避免逐字念说明。','results':'先说横纵轴和两种颜色，再比较前后与组间。','experiment':'先交代四组共用同一放松程序，再指出香味与触觉的差别。','receptors':'只解释组合关系；颜色是教学示意。','timeline':'指顺序，提醒长度未按真实秒数绘制。','compare':'先说比较对象，再说各自承担的动作。','mechanism':'沿图讲清每一步的对象和动作。','process':'沿流程说明指令和材料怎样配合。'}.get(slide['layout'],'围绕本页主要问题讲，长解释留在口播里。')

if __name__ == '__main__':
    main()
