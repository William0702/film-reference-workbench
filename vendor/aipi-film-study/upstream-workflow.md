---
name: aipi-film-study
description: 以AIπ工作台逐镜分析成片，按真实帧时间保留每次切换，核对完整语言记录，编写导演解读和复拍方案，导出播放联动的报告、镜头表与字幕。适用于短剧拉片、视听学习和制作参考。
license: MIT
metadata:
  description_en: Frame-based film study with complete dialogue review, director notes, reshoot guidance, and an interactive AIpi review workspace.
  version: "1.0.1"
  author: AIπ
  display_name: AI圆周派 · 逐镜拉片
  brand: AI圆周派
  runtime: Node.js 18 or newer
  dependencies: FFmpeg and ffprobe; a browser for report review
---

# AIπ｜AI圆周派 · 逐镜拉片

把成片整理成可追溯的镜头记录，让使用者同时看见原片、完整台词和拍摄思路。用当前技能目录作为 `{skill}`，用用户选定的项目文件夹保存结果。执行说明与命令时使用宿主实际提供的本地工具。

## 交付要求

镜头按原片切换划分，一镜一条记录；同一镜中的人物动作不自动算作新镜。检测结果是候选，需要结合切点前后画面复核。黑场、单帧闪切、叠化和长镜头都保留其真实节奏。

画面记录写可见事实；导演分析写有依据的解读；复拍建议写可执行的机位、走位、视线或剪辑安排。不要把估计的焦段、拍摄器材或人物心理写成已知事实。

“完整”“可交付”“生产使用”意味着全片画面和声音均在核对范围内。扫描字幕和每镜抽两帧不能替代声音审核。没有可用的听辨或识别工具时，明确标记未完成项，继续完成能证实的工作。

## 工作顺序

1. 执行 `node "{skill}/scripts/engine.mjs" probe "输入视频"`，确认画幅、音轨、实际帧时间和素材身份。读取 [数据约定](references/study-format.md)。
2. 执行 `detect "输入视频" --out study.json` 生成候选底稿。按片子节奏调整检测阈值，保留检测记录；不要填充假的已审状态。
3. 用 `frames study.json --video "输入视频" --out frames` 生成参考帧。读取命令返回的新数据文件位置；核对正确后将它用于后续编辑。镜头只有一帧时，首尾参考可以相同。
4. 结合联系视图、切点邻帧及镜内运动核对每次切换。需要改切点时使用 `recut`，并重算镜号、语言引用和参考帧；机器不确定的地方记录复核依据。
5. 阅读 [语言核对与导演记录](references/review-method.md)，建立独立的逐句语言时间表。核对跨镜续句、画外音、唱腔和片尾字幕，再为各镜填写画面、人物、运镜和导演字段。
6. 执行 `validate study.json` 检查结构，执行 `validate study.json --production` 检查完整交付条件。只有实际审核完成时才能写入已完成状态。失败时保留具体原因，不能通过改标签来代替补核。
7. 用 `table study.json --out shots.csv`、`subtitles study.json --out dialogue.srt` 导出文字；用 `node "{skill}/scripts/report.mjs" study.json --out report.html` 生成AIπ工作台。命令具体可选参数以 `--help` 为准。

## 报告验收

打开真正生成的HTML，用实际原片播放检查：长对白镜能读到最后一句，导演与复拍字段完整；播放改变当前镜并带动列表；手动读表可以暂停跟随；点击镜头落在本镜首帧；单帧和片尾行为正确。检查至少一个常见笔记本视口及窄屏，视频不能被长文本挤出可视区域。

保留视频、关键帧与HTML的相对路径，整体保存结果文件夹。报告可以离线打开，视频文件仍须在本地。语言未核完时明确显示参考状态。

网页播放首版只接受零起点素材；非零PTS可以用引擎测量与抽帧，但生成报告前须将独立素材副本规范到零起点，再重新探测和关联。对可变帧率，网页使用实际frameTimes定位，不假定每帧等长。

需要同步视频时使用 `aipi-sync-video`，传入同一份最终 `study.json`。修改台词或切点后重新生成所有受影响文件。需要XLSX时使用当前宿主可用的表格工具从相同数据转换；本技能不内置特定宿主的办公运行时。

首次在新宿主运行时先读 [安装与宿主检查](references/host-setup.md)，适用于 Codex、Claude Code、WorkBuddy 及其他支持本地技能的代理。最终汇报真实输出、检查范围及尚未解决的声音问题，不能把命令成功等同于内容无遗漏。
