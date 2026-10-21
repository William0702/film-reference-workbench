---
name: film-reference-workbench
description: 本地成片逐镜拉片、人物对白对照、五维导演分析、镜头组素材池与脚本优化交接。用于复刻参考整理；不代替新故事创作或视频生成。
metadata:
  version: "0.3.0"
---

# 复合拉片工作台

这是 0.3.0 的 Git 源码分发版，三个原技能的必要模块已内置，用户只需调用 film-reference-workbench，无需安装或单独调用原三个技能。以本目录为技能根目录。源码不包含运行时、模型或私人案例；先按 [README.md](README.md) 准备 Windows x64 / Python 3.12 / Node.js 18+、FFmpeg、ffprobe、本地识别依赖和模型。安装、首次使用和更新后先按 [安装与更新](references/installation.md) 执行检查、按需补齐和合成片自检。获得安装/修复授权后用 setup.ps1 自动补齐已声明依赖；网络或权限受阻时报告具体缺口，不调用其他技能。

## 统一入口

首次素材用 `python scripts/prepare_case.py --video <原片> --out <案例目录>` 完成媒体探测、候选切镜、抽帧与本地ASR。只有本地工具缺失时才报告具体缺口，不转去调用其他技能。该命令只生成证据底稿，之后必须继续完成下述画面分析与素材池交付，不能停在自动底稿。已有分析从案例数据续接，避免重复工作。

## 取证与分析

1. 先确认原片和输出范围；读取 [aipi 数据约定](vendor/aipi-film-study/references/study-format.md) 与 [声音／导演核对方法](vendor/aipi-film-study/references/review-method.md)。使用 `scripts/media.py probe/detect/frames/recut/validate` 调用本包的媒体引擎。自动检测只是候选，检查切点邻帧、黑场、闪切、叠化和镜内动作；道具转向、角色动作与光晕不能单独证明切镜。修订后重建帧、镜号映射、语言关联与派生输出。
2. 可见字幕和音轨分开保存。用 `scripts/run_asr.py --video ... --out ...` 调用实际存在的本地ASR；离线资源包会自动发现本包runtime目录，源码包需显式提供模型及已准备的识别环境。保留原始机器结果，不把ASR等同完整听审或说话人识别。
3. 读取 [五维导演分析模块](vendor/storyboard-shot-breakdown/upstream-workflow.md)，查看镜头及上下文后分析构图、焦距感、运镜动机、剪辑理由、叙事功能。区分画面事实、分析推断与复拍建议。未知真实器材和焦距明确未知。
4. 参考 [镜头库字段模块](vendor/video-shot-analysis-feishu/upstream-workflow.md)，形成分镜图与视频提示词草稿。默认本地导出，不执行该模块的飞书上传步骤；云端操作不在本包默认流程内。原版extract_shots.py作为上游源码保留，Windows切镜优先使用本包media.py。
5. 组织镜头组，记录铺垫、转折、反应、回收、成立条件与迁移限制。按 [交接合同](references/handoff.md) 生成同一份结构化数据，用 `scripts/export_pool.py --study ... --out ... --sequences ...` 输出完整页面、素材池JSON与CSV。逐段页面应同时呈现三类内容，不能只把文件存在视为用户已验收。

## 核验与交接

原片身份、切点、镜内动作、语言、说话人、音乐与音效分别记录证据和审核范围。只有相应来源实际核实后才能改状态；用户认可页面或识别结果不自动代表全片听审。默认使用等级为inspiration，脚本不自动授予已核可复刻资格。

交接给script-optimization-service时，把asset-pool.json和镜头组作为案例输入，列出借鉴理由、匹配条件与不适用部分；读取下游技能当前规则，不修改其知识库或跳过故事与镜头确认。没有新剧本时只交资料包，不自行创作新故事。

界面交互能测试时实际检查播放、换镜、定位、搜索、长文本与窄屏；受限时报告未测，不绕过浏览器策略。当前版本仍是试用框架，不声称任意影片的自动分析或生成效果已验证。

## 分发边界

来源及许可见 THIRD_PARTY_NOTICES.md。上游模块按原许可保留；不把整个包都标成MIT。本地版限Windows x64 / Python3.12；Python和Node.js解释器仍为系统工具。FFmpeg二进制副本仅用于用户本机，尚未作为新分发包发布。源码包不包含私人视频、素材池、个人路径、虚拟环境或模型权重。
