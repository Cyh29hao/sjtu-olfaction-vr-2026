# 本机构建与导出

组员修改文稿与资料即可，无需安装或运行本目录工具。第0组合稿时，用同一内容源生成总PPT、分组PPT、备注，再检查真实页面。

`build_deck.mjs`读取`content/deck.json`，使用选中的蓝绿青春模板。模板原件保持在本机；仓库不附整套空白模板。运行库沿用本机已有的捆绑Node、artifact-tool和Office，不安装替代依赖。可以通过`RUNTIME_NODE_MODULES`、`PRESENTATION_SKILL_DIR`、`RUNTIME_PYTHON`覆盖本机路径。

## 数据约定

顶层包含`title`、`subtitle`、`sources`、`slides`。`sources`以文献ID为键，值包含`title`、`authors`、`url`、`location`。每页包括稳定`id`、`group`（0/1/2/3）、`role`（main/backup/contributions）、`title`、`layout`、`seconds`、自然`script`、`source_ids`、具体`source_locations`和短`footer`。正文与来源定位进入PPT备注。

| layout | 主要字段 |
| --- | --- |
| cover | image、subtitle、byline；左侧标题、右侧图片 |
| photo | image、caption；可用side_text在右侧放短解释 |
| process / mechanism / timeline | steps数组，每项label、text，可选image；caption可选 |
| receptors | receptor_labels；odors数组，每项label、active（从0开始的受体位置）；caption标明教学示意 |
| compare | columns数组，每项label、image、text |
| experiment | table给出行／列条件构成的2×2实验矩阵，caption放实验设置短句；原生表格保留可编辑 |
| results | chart含type、categories、series（name、values、color）、yMin/yMax、yTitle、format；takeaways和caption可选 |
| evidence | table含headers、rows、widths（列宽比例）、fontSize；takeaways可选 |
| judgment | question、alternatives数组（label、text） |
| closing | lines、caption |
| references | entries数组（label、text、url） |
| contributions | table，作为全套最后一页 |

图片路径均相对仓库根目录，image可以是字符串或`{path,alt,fit,crop}`。图表数据、表格、过程与受体组合示意保留为可编辑对象。`elements`可补充text/image/arrow/rect对象，但优先使用对应内容布局。

图片会实际读取为字节后嵌入，而非只登记本地路径。构建与最终整理均检查媒体非空并解码栅格图片；这仍需配合正式PowerPoint渲染，确认图片确实显示。

备份页在PPT中标为隐藏。后台PDF导出会纳入全部页面，便于查阅。`--main-count`另导出连续主讲页PDF，配合`--append-last`在主讲PDF末尾再附全套最后的分工表。实际贡献由组内填写和核实。

## 运行顺序

1. 首次真正创建操作前，按已安装presentation skill运行一次`mark_artifact_operation_started.mjs`。本轮样页制作已执行，后续修订沿用同一次创建操作，不重复标记。
2. 用捆绑Node运行`build_deck.mjs --input content/deck.json --template <本机模板路径> --output .git/production-20261101/build/candidate.pptx --subdecks`。
3. 运行`finalize_deck.mjs --candidate <候选路径> --manifest <build-manifest.json路径> --template <原模板路径> --output <新的正式PPTX路径>`。校验器保留候选、另写正式文件；存在的正式输出不会覆盖。修订使用新候选及新输出名，验收后再更新稳定入口。
4. 运行`python -X utf8 -B scripts/export_native.py <正式PPTX路径> --out-dir <PDF目录> --png-dir <私有检查图目录> --main-count <实际主讲页数>`。
5. 逐页看PNG，并核查科学内容、口播、备注、PDF和分组材料一致，再发布。构建或校验成功不能替代视觉与内容检查。

`--subdecks`会在候选旁输出第一、二、三组PPTX，按group字段筛选，保留原全场页码便于定位。分组文件也要按各自实际页数与原生对象重新校验、导出，不能直接套用总稿manifest。

工具只在后台打开本次PPT，不移动鼠标或发送全局按键。原生导出后检查源文件哈希保持一致。自动检查记录写入私有构建目录；README面向组员的入口只展示可用成品与协作说明。
