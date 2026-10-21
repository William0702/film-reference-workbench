# 0.3.1 冷安装与更新验证（2026-10-21）

## 测试环境与隔离范围

在同一台 Windows x64 主机建立两个独立 Agent skills 目录，使用新建 CPython 3.12 虚拟环境；从子进程 PATH 隐藏现有 Node.js、FFmpeg/ffprobe，关闭用户 site-packages 及 pip 下载缓存，清除原技能运行时覆盖变量。测试使用已获仓库权限的 Git 登录态。

没有复用原技能目录内的模型、Python 识别依赖或媒体工具。基础 Windows、Git/认证和 Python 3.12 解释器仍由宿主提供；不是全新 Windows 虚拟机，未执行缺 Python 时的 winget 用户安装分支。

## 真实网络测试结果

1. 从私有 GitHub 仓库 clone 0.3.0 到空 Agent skills 目录成功，首次 install 自动发现缺件，Node.js 下载并安装成功。
2. FFmpeg 主站发生 TLS EOF，0.3.0 首次安装失败。保留失败记录，不把脚本存在当作通过。
3. 修复为有限重试 + 官方 GitHub 同版本镜像，仍校验同一锁定 SHA256。隔离 Agent 执行 update.ps1，真实快进拉取该修复，完成 FFmpeg、26 个识别依赖及四个模型文件下载。
4. 上述环境完成模型哈希、依赖版本和 native import 检查；合成片 probe/候选切镜/抽帧/ASR/HTML/素材池导出自检通过。
5. 使用第二个空 Agent skills 目录重新执行 install.ps1，全部工具、识别依赖和模型再次联网下载；首次安装及合成片自检通过，用时约 72 秒。
6. 第二个隔离 Agent 执行 update.ps1，真实快进拉取最终提交并再次自检通过，约 10 秒；工具/模型的大小和修改时间未变，日志没有重复下载或安装。随后同安装账号的 CheckOnly 再次通过。

固定来源：Node.js 22.16.0（ZIP 35,466,975 bytes）、Gyan FFmpeg 8.1.2 essentials（ZIP 109,728,040 bytes）、PyPI 锁定版本、Systran/faster-whisper-small 固定 revision（model.bin 483,546,902 bytes）。未将上述大文件提交 Git。

## 故障修复测试

离线单元测试 5 项通过，新增网络失败重试后切换镜像、校验正确才替换目标文件的测试。0.3.0 的隔离本地 Git 更新保护测试仍作为历史证据，见对应验证文档；真实 GitHub 快进更新由本轮单独验证。

## 使用限制

只证明上述隔离环境中的安装/更新与合成片执行。缺 Python 的用户安装、Git 缺失、未授权私有仓库账户、另一台新 Windows 电脑、Linux/macOS、浏览器交互、完整页面截图及真实影片导演分析质量不在本次通过范围内。

观察到账号边界：安装账号检查通过，另一个 Windows 沙箱账号复检失败，且直接列出 python-packages 目录被拒绝访问。未修改目录权限；不能把同账号的成功推广为跨账号可用。

主站或镜像均不可达时，安装仍应失败并列出错误。不会关闭 TLS 校验、修改系统执行策略、调用付费接口或上传测试视频。
