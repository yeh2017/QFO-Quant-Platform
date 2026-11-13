# QFO 量化回测平台 v1.0.5

发布日期：2026-11-13。本版累计继承 v1.0.3、v1.0.4；功能更新与 CHANGELOG.md 的 v1.0.5 条目一致。

### 启动与安装更新

- **首次启动与快速启动分开**：`run_first_time.bat` 检查环境、安装依赖并创建配置；`run_quick_start.bat` 只启动服务，环境缺失时提示先运行首次启动，不自动安装依赖。
- **恢复可见服务窗口**：分别显示 QFO Backend 和 QFO Frontend 窗口，便于查看真实日志；使用期间保持这两个窗口打开。
- **显示启动进度与结果**：后端最多检查 30 次、前端最多检查 20 次，显示 `[WAIT]`、`[OK]` 或 `[FAIL]`；超时不再显示整体启动成功。次数是检查上限，不是固定等待秒数。
- **统一访问地址**：后端 `http://localhost:8000`，前端 `http://localhost:3000`；服务仍仅绑定本机回环地址。
- **固定 AkShare 版本**：后端依赖固定为 `akshare==1.18.91`，避免新安装时自动选择其他版本。
- **继承 v1.0.4 安装改进**：后端依赖依次尝试阿里云、腾讯云、官方 PyPI；全部失败时提示检查网络和 DNS。保留 Python 3.12+、Node.js 22.12+ 和 UTF-8 安装流程。
- **保持轻量下载**：不附带 Python、Node.js、虚拟环境、前端依赖或行情数据库；首次安装仍需联网。

### 继承 v1.0.3：回测引擎修复

- **退市时点判断**：`FullMarketUniverse` 使用 `delist_date` 历史时点判断，退市前的股票仍可纳入对应回测标的池。
- **退市清仓机制**：通过 `delist_mask` 和主动清仓处理退市股票，区分停牌保留权重与退市清仓。
- **残留价格清理**：清理退市股票最后交易日后的前向填充价格，避免产生虚假收益。

### 继承 v1.0.3：财务数据同步修复

- **更新时间写入**：raw SQL upsert 显式写入 `CURRENT_TIMESTAMP`，修复 `updated_at` 为空导致的增量判断问题。
- **增量窗口**：`FINANCIAL_SKIP_DAYS` 从 90 天调整为 14 天。
- **财报季覆盖**：增加 5、9、11 月的财务同步窗口，支持长尾披露与补录。
- **PIT 公告日查询**：增加 `ann_date`，使用 `ann_date <= end_date` 筛选历史时点可用财务数据。

### 继承 v1.0.3：因子与展示修复

- **复权口径统一**：动量、波动因子使用前复权价格，避免除权日导致异常收益。
- **表达式校验**：`delay`、`delta` 运行时和 AST 校验禁止 `d < 1`。
- **因子评分过滤**：排除 ETF、港股、期货等非股票标的，避免空基本面影响评分。
- **新闻覆盖率统计**：LLM 覆盖率分母排除规则赋分事件。
- **成交额单位统一**：K 线 tooltip 与 ETF 选股器修正成交额单位。

### 继承 v1.0.3：其他改进

- 增加指数成分权重回填函数 `backfill_index_weight()`，按月回填 HS300、ZZ500、ZZ1000 历史成分。
- 保留回测正确性测试，使用合成数据与手算结果验证。
- 同步专用股票池恢复 `is_active=True` 过滤，排除退市股。
- 资金流向 upsert 返回实际写入行数，修正统计数字。
- 保留 WebSocket 广播回调注入和因子缓存下沉，消除相关跨层反向导入。

## 安装与升级

完整解压后运行 `run_first_time.bat`，安装完成后的日常启动运行 `run_quick_start.bat`。首次安装仍需联网，并自行安装 Python 3.12+、Node.js 22.12+。

已有数据请先关闭旧版和新版、保留备份，再按[数据迁移说明](https://github.com/yeh2017/QFO-Quant-Platform/blob/main/docs/upgrade-data-migration.md)迁移数据库。不要跨电脑复制 `.venv` 或 `node_modules`。

[下载 v1.0.5](https://github.com/yeh2017/QFO-Quant-Platform/releases/download/v1.0.5/QFO-Quant-Platform.zip) · [完整更新日志](https://github.com/yeh2017/QFO-Quant-Platform/blob/main/CHANGELOG.md) · [教学网站](https://www.qfo-quant-platform.com/)
