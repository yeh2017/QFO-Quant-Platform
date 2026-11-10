# QFO量化回测平台 v1.0.3

本次包含回测、财务同步、因子、数据展示和 Windows 安装修复。Issue #8 的部分改动已合入，未完成事项见下方。

## 功能修复与更新

- **回测时序**：移除使用下一交易日收益的重复涨跌停过滤调用；将信号决策延后至下一交易日执行。
- **退市回测**：按历史上市、退市日期建立标的池，增加退市清仓并清理退市后的价格残留；实际效果仍取决于历史日线覆盖。
- **财务同步**：修正更新时间和增量同步判断，扩展财报期覆盖，保存公告日并增加按公告日筛选的查询。
- **因子计算**：统一动量、波动率与回测的复权口径；限制 `delay/delta` 的天数必须大于等于 1，并过滤非股票标的。
- **新闻与数据展示**：修正 LLM 覆盖率、成交额单位、资金流向写入数量及停牌统计。
- **指数与模块调整**：新增历史指数成分权重回填函数；调整 WebSocket 广播与因子缓存的模块依赖。回填函数尚未接入常规同步任务。
- **Windows 安装与启动**：修复多 Python 版本选择、UTF-8/GBK 编码、跨目录安装和前端重复重装；首次与日常启动共用检查逻辑，服务响应后才提示成功，日志保存至 `backend/logs/`。
- **依赖更新**：升级 Vite、React 插件及相关工具依赖；发布时 npm 审计报告 0 项已知漏洞。Python 要求保持 **3.12+**，Node.js 调整为 **22.12+**。

## Issue #8 的修复边界

[Issue #8：未来函数优化](https://github.com/yeh2017/QFO-Quant-Platform/issues/8) **仍保持开放，v1.0.3 是部分修复，不表示已消除全部前视或存活偏差**：

- 财报公告日为空时，因子加载器仍回退到报告期过滤，不能保证严格 PIT；其他财务查询入口也需要继续核查。
- 退市股票的历史日线可能不完整；增加退市处理代码不等于已为用户补齐数据。
- 指数成分历史需另行回填并核验时间覆盖，不能以新增回填函数认定已解决历史成分偏差。
- 涨跌停执行约束、次日执行时序等仍需补充端到端回归验证。

## 安装与升级

- Windows 10/11，Python **3.12+**，Node.js **22.12+**；本轮在 Python 3.14 和 Node.js 24 环境验证。
- 完整解压后运行 `run_first_time.bat`，日常启动使用 `run_quick_start.bat`；只准备环境时可运行 `run_first_time.bat --prepare-only`。
- 跨电脑迁移时，由目标电脑重建 `backend/.venv` 和 `frontend/node_modules`，不要直接复用原电脑的运行环境。
- 升级前备份数据库，按[数据迁移说明](https://github.com/yeh2017/QFO-Quant-Platform/blob/main/docs/upgrade-data-migration.md)复制原有数据；数据库与密钥不随安装包发布。

## 验证范围

74 项后端单元测试、69 项前端测试及生产构建通过；独立目录首次安装、前后端连接和发布包校验通过。上述验证不替代 Issue #8 所需的完整时序与历史数据覆盖验证。

[完整更新日志](https://github.com/yeh2017/QFO-Quant-Platform/blob/main/CHANGELOG.md) · [使用说明](https://github.com/yeh2017/QFO-Quant-Platform/blob/main/README.md) · [下载最新稳定版](https://github.com/yeh2017/QFO-Quant-Platform/releases/latest/download/QFO-Quant-Platform.zip) · [教学网站](https://www.qfo-quant-platform.com/) · [完整视频教程](https://www.bilibili.com/video/BV18Cby6XEfR/)
