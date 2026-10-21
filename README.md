# film-reference-workbench 0.2.1

本地逐镜拉片、人物对白对照、五维导演分析和素材池交接的复合 Codex 技能。三个模块位于 vendor/，不需要另装原技能。

## 安装与资源

将整个目录安装到自己的 Codex skills 路径。运行环境为 Windows x64、CPython 3.12、Node.js 18+。源码包不附带运行时，首次安装并非开箱即用。

- FFmpeg 与 ffprobe：自行准备到 runtime/tools/，或加入系统 PATH。
- Python 依赖：按 requirements-win-py312.lock.txt 准备到 runtime/python-packages/。run_asr.py 当前要求此目录，单纯安装到系统环境不能替代。
- small 模型：准备到 runtime/model-small/，必须含 model.bin 和配套文件。下载辅助脚本为 scripts/download_model.py；先查看 --help，下载须显式执行。
- 已有本地一体化版可继续使用原 runtime/，这些文件不会进入 Git。

```powershell
python scripts/doctor.py
python scripts/prepare_case.py --video "my-video.mp4" --out "my-case"
```

prepare_case 生成候选切镜、截图与机器对白证据。Agent 还需实际核对画面和声音，填写导演分析、镜头组，再由 export_pool.py 输出报告及素材池。机器转写不代表听审通过，默认素材使用等级为 inspiration。

## 分发与验证范围

保留 THIRD_PARTY_NOTICES.md、THIRD_PARTY.json 以及 vendor/ 下许可。上游含 MIT 与 AGPL-3.0 模块；尚未为新增整合代码选定统一开源许可证，不宣称全包 MIT。建议先使用私有仓库，公开发布前处理许可证选择。

本目录取自本机安装版 0.2.1，排除了模型、依赖、二进制、私人视频和案例。本次执行源码结构、Python 语法和技能格式检查；既往本机运行记录不等于本次在全新机器上复测。浏览器交互及第二部影片尚未验证。

## 完整案例

[情侣星座反转拉片示例](examples/couple-zodiac/README.md)：含原片、完整 HTML 工作台、逐镜画面及素材池。页面截图待补。
