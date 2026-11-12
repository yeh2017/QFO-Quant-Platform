# QFO 量化回测平台 v1.0.4

本版只改进 Windows 首次安装。安装包保持轻量，不附带 Python、Node.js 或行情数据库。

- **恢复备用源**：后端依赖按阿里云、腾讯云、官方 PyPI 的顺序安装。
- **改进失败提示**：如果 pip 显示 `Failed to resolve` 或 `getaddrinfo failed`，请检查网络和 DNS，或换网后重跑 `run_first_time.bat`。备用源无法修复所有域名都不可达的网络。
- **保留 v1.0.3 的安装改进**：Python 3.12+、Node.js 22.12+ 和 UTF-8 安装流程不变。回测、选股和数据同步逻辑不变。

首次安装仍需联网。下载并完整解压安装包后，运行 `run_first_time.bat`；已有数据可按[数据迁移说明](https://github.com/yeh2017/QFO-Quant-Platform/blob/main/docs/upgrade-data-migration.md)备份和迁移。

[完整更新日志](https://github.com/yeh2017/QFO-Quant-Platform/blob/main/CHANGELOG.md) · [教学网站](https://www.qfo-quant-platform.com/)
