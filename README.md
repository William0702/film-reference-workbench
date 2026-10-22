# film-reference-workbench 0.3.3

本地逐镜拉片、人物对白对照、五维导演分析和素材池交接的复合 Codex 技能。三个模块位于 vendor/，不需要另装原技能。

## 自动安装、环境检查与更新

复制给 Agent：

> 请从 https://github.com/William0702/film-reference-workbench 安装这个复合拉片技能。先读取 references/installation.md，在我的 Codex skills 路径中安装，自动检查并补齐缺失组件，跑完默认自检。已有 Git 安装则用 scripts/update.ps1 更新后再自检。只使用普通 Windows 用户权限，不修改系统安全策略、不以管理员身份运行；如网络或权限阻断，报告实际失败，不能把离线模拟记为在线通过。

Agent 也可以在 PowerShell 中执行下面整段命令（需要 Git；公开仓库无需 GitHub 登录；脚本仍须遵守本机执行策略）：

```powershell
$skillsBase = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
$skillPath = Join-Path $skillsBase 'film-reference-workbench'
if (Test-Path -LiteralPath $skillPath) {
    & (Join-Path $skillPath 'scripts/update.ps1')
} else {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required' }
    git clone --branch main https://github.com/William0702/film-reference-workbench.git $skillPath
    if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
    & (Join-Path $skillPath 'scripts/setup.ps1')
}
```

只更新已有安装时：`& (Join-Path $skillPath 'scripts/update.ps1')`。旧的非 Git 安装不会被覆盖。

Agent 请先读取 [安装与更新说明](references/installation.md)。scripts/install.ps1 安装，scripts/setup.ps1 自动检查/补齐并运行合成片自检，scripts/update.ps1 拉取 main 最新代码后重复自检。仅支持 Windows x64；公开仓库可匿名拉取，无需 GitHub 登录。

## 运行资源

将整个目录安装到自己的 Codex skills 路径。运行环境为 Windows x64、CPython 3.12、Node.js 18+。源码包不附带运行时，首次安装并非开箱即用。

- 首次安装：执行 scripts/install.ps1，默认自动检查、补齐缺件，再运行合成片自检。
- 环境修复：执行 scripts/setup.ps1；FFmpeg/ffprobe、Node.js、Python 识别依赖、small 模型按安装说明准备，正确资源复用。
- 后续更新：执行 scripts/update.ps1，快进拉取 main 后重新检查和自检。
- 仅检查：执行 scripts/setup.ps1 -CheckOnly，不联网、不安装组件。
- 已有本地一体化版可继续使用原 runtime/，这些文件不会进入 Git。

```powershell
python scripts/doctor.py
python scripts/prepare_case.py --video "my-video.mp4" --out "my-case"
```

prepare_case 生成候选切镜、截图与机器对白证据。Agent 还需实际核对画面和声音，填写导演分析、镜头组，再由 export_pool.py 输出报告及素材池。机器转写不代表听审通过，默认素材使用等级为 inspiration。

## 分发与验证范围

保留 THIRD_PARTY_NOTICES.md、THIRD_PARTY.json 以及 vendor/ 下许可。上游含 MIT 与 AGPL-3.0 模块；尚未为新增整合代码选定统一开源许可证，不宣称全包 MIT。仓库公开不代表将所有模块改为 MIT；安装和再分发请保留各模块原许可。

0.3.3 在既有 0.2.1 分析流程上增加安装、依赖修复和更新入口。运行时大文件不进入 Git；examples 中包含用户已明确授权公开的案例原片及分析数据。已在本机通过合成片端到端自检、离线修复测试和本地 Git 更新保护测试；全新机器联网安装尚未验证。详见 [本轮验证范围](references/validation-0.3.3.md)。

## 完整案例

[情侣星座反转拉片示例](examples/couple-zodiac/README.md)：含原片、完整 HTML 工作台、逐镜画面及素材池。页面截图待补。
