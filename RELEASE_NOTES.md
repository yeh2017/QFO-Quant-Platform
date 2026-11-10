# QFO量化回测平台 v1.0.3

本次更新修复 Windows 首次安装问题，并改进回测、财务同步和因子计算。

## 主要更新

- 启动时选择 Python 3.12+，使用当前虚拟环境和 UTF-8 安装依赖，避免 GBK 解码错误和跨目录安装。
- 修正前端依赖误判，首次安装使用锁文件；后端和前端响应后才提示启动完成。
- 更新 Vite、React 插件及相关依赖，修复本轮 npm 审计发现的漏洞。
- 修复退市股票回测、财务数据增量同步与公告日查询，统一因子复权口径并限制前视表达式。
- 修正新闻 LLM 覆盖率、成交额单位和数据同步统计，调整广播与缓存的模块依赖。

## 安装与升级

- Windows 10/11，Python **3.12+**，Node.js **22.12+**。本轮在 Python 3.14 和 Node.js 24 环境验证。
- 完整解压后运行 `run_first_time.bat`；日常启动使用 `run_quick_start.bat`。只准备环境而不启动服务时，可运行 `run_first_time.bat --prepare-only`。
- 跨电脑复制时不要复用原电脑的 `backend/.venv` 和 `frontend/node_modules`。
- 升级前保留数据库备份，按[数据迁移说明](docs/upgrade-data-migration.md)复制原有数据；数据库与密钥不随安装包发布。
- 启动失败时检查窗口实际错误及 `backend/logs/` 日志。

完整变更见 [CHANGELOG.md](CHANGELOG.md)，使用方法见 [README.md](README.md)。

本轮验证：74 项后端单元测试、69 项前端测试及生产构建通过；独立目录首次安装和前后端连接通过；npm 安装审计报告 0 项已知漏洞。联网数据源仍需使用者配置自己的 Token。

[下载最新稳定版](https://github.com/yeh2017/QFO-Quant-Platform/releases/latest/download/QFO-Quant-Platform.zip) · [教学网站](https://www.qfo-quant-platform.com/) · [完整视频教程](https://www.bilibili.com/video/BV18Cby6XEfR/)
