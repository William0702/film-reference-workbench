# Agent 安装、检查与更新

当前支持 Windows 10/11 x64，不是 Linux/macOS 安装器。用户授权安装本技能时，先说明下列依赖及下载范围，再执行安装流程。宿主审批拒绝网络或安装时，报告缺件，不绕过审批；安装技能不代表授权付费服务或上传用户影片。

## 第一次安装

正式仓库现为公开仓库，安装和更新可以匿名拉取，无需 GitHub 登录或 token。Git 是拉取工具的前置依赖。目标目录应为空，旧版非 Git 安装不自动覆盖。

```powershell
$skillsBase = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
$skillPath = Join-Path $skillsBase 'film-reference-workbench'
git clone --branch main https://github.com/William0702/film-reference-workbench.git $skillPath
if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
& (Join-Path $skillPath 'scripts/install.ps1') -Destination $skillPath
```

install.ps1 也可从已下载的源码目录执行，自动 clone 到默认 skills 目录后调用 setup。默认完整执行：检查 → 缺件修复 → 重检 → 合成片 probe/切镜/抽帧/ASR/HTML/素材池自检。自检不等于真实影片导演分析验收。执行策略禁止脚本时遵守所在环境的规则，不修改执行策略。

## 检查和更新

```powershell
& "$skillPath/scripts/setup.ps1" -CheckOnly
& "$skillPath/scripts/setup.ps1"
& "$skillPath/scripts/update.ps1"
```

- CheckOnly 不联网、不安装依赖，只写本地诊断。
- setup 可重复运行，复用兼容工具及正确依赖/模型，补齐缺失与损坏项；可用 -Python 指定 Python3.12 的绝对路径。
- update 只接受原仓库、main 分支、干净工作树，执行 git pull --ff-only 后再次 setup 和自检；runtime、缓存不进 Git，不强制重置修改。
- 不定时联网。需要更新时由用户或 Agent 执行。代码更新但自检失败时，报告未完成，修复网络或权限后重跑 setup。
- 首次使用、更新后或组件报错时，Agent 先跑 setup 检查；已有安装/修复授权且缺件时跑完整 setup。没有自检成功结果，不宣称环境可用。

诊断见 runtime/setup-report.json。中断留下 .bootstrap.lock 时先确认无安装进程运行，再手动清理该单个锁文件。

## 下载范围和固定来源

| 组件 | 处理方式 |
| --- | --- |
| Python 3.12 x64 | 复用兼容解释器；缺少时通过 winget 社区源 Python.Python.3.12 / 3.12.10 用户安装；缺 winget 则明确报告，需先准备 Python |
| Node.js 18+ | 复用可执行工具；否则从 nodejs.org 下载固定 22.16.0 Windows x64 ZIP，核对同版本官方 SHASUMS256，便携保存到 runtime |
| FFmpeg + ffprobe | 复用可执行工具；否则下载 Gyan 8.1.2 essentials ZIP，网络失败有限重试后回退官方 GitHub 同版本镜像，始终核对同一锁定 SHA256，保留许可/文档 |
| ASR Python 依赖 | PyPI 官方源、requirements-win-py312.lock.txt 固定版本，只接受二进制 wheel，装到 runtime/python-packages |
| small 模型 | Hugging Face Systran/faster-whisper-small 固定 revision；四文件按锁定 SHA256 校验，缺失/损坏文件单独重下 |

模型约 484 MB，另有工具和依赖下载，首次准备需数 GB 磁盘及可达上述源的网络。setup 可能增加用户级 Python，其余资源留在 runtime。无管理员自动提权、无全局 PATH/执行策略修改、无素材上传或付费接口。pip 缺失时用所选解释器的 ensurepip 引导。

FILM_REFERENCE_RUNTIME 可显式指定独立运行时目录，用于已有资源或隔离验证，默认无需设置。该目录须由当前用户控制，报告及自检输出均写入该目录。

0.3.2 及后续版本修复生成依赖目录丢失父目录权限继承的问题：安装后的依赖树启用 runtime 父目录已有 ACL 的继承，并保存完成记录；后续账号无需反复请求修改 DACL。不会新增 Everyone/Users 授权，也不会修改系统目录或全局安全策略。跨账号使用的前提是父目录本来就允许该账号读取、执行，以及更新所需的写入。

旧版存在受保护依赖目录时，请先由原安装账号执行一次新版 setup.ps1 或 update.ps1 修复。普通读取账号没有修改 DACL 的权限时，明确报告需安装账号处理，不自动提权。CheckOnly 不做 ACL 修复。

权限操作限于技能生成的 python-packages 或 packages-stage-* 直接子目录，拒绝重解析点，并使用 Windows 长路径语法。自检目录也继承 runtime 的已有权限。更新命令仅为本技能当前目录指定进程内 safe.directory，不写全局 Git 信任配置；本地改动/分叉保护仍保留。

实际验证范围见 [0.3.3 普通账号在线安装记录](validation-0.3.3.md) 与 [跨账号复测记录](validation-0.3.2.md)。脚本不要求 Windows 管理员权限；Agent 所在的离线沙箱仍需具备联网权限，同主机隔离测试不等于新 Windows 系统安装验证。
