# U8采购订单导入平台源码

纯源码交付：frontend前端、backend后端与迁移测试、scripts启动脚本、deploy日志配置、docs维护指南、test-data模拟样例。保留frontend/LICENSE及依赖版权信息。

## 项目介绍

### 用友 U8 是什么

用友 U8 是很多企业日常使用的 ERP（企业资源计划）管理软件，采购、销售、库存、财务等业务都在里面记账流转。其中「采购订单」是采购环节的核心单据，供应商、物料、数量、单价、金额等信息都要录入 U8，才能继续后续的入库、结算等流程。

### 需求（痛点）是什么

企业批量采购时，一次往往有几十到几百条采购明细。如果靠人工在 U8 里一条条手动录入，存在几个明显问题：

- 录入慢、效率低；
- 手工填错的风险高（漏字段、单位/数量/金额填错）；
- 出错后难追溯、难批量核对；
- 一旦误提交，ERP 数据就被污染，纠正成本高。

### 这个自动流工具解决了什么问题

本平台把「表格 → 校验 → 确认 → 写入 U8」全流程自动化，针对上面的痛点逐一解决：

- **批量导入**：CSV / TSV / XLS / XLSX 表格直接导入，一次处理数十到数百条订单，替代逐条手录。
- **入库前校验**：自动识别表头、映射字段、校验数量/单价与金额口径，误映射会被拦截，把错误挡在提交之前。
- **人工确认再写入**：校验通过后需人工确认，才真正写入 U8，避免误导、错导。
- **可靠不重不漏**：任务持久化 + 事务入队 + 提交前标记 + 崩溃回查，网络超时不会重复下单。
- **全程可追溯**：审计、错误、执行记录完整留存，每笔订单可定位、可复盘。

## 安装

需要Python 3.12、Node.js和已初始化的PostgreSQL。根目录创建.venv，使用.venv/Scripts/python.exe -m pip install -r backend/requirements.lock.txt安装后端依赖；在frontend执行npm ci及npm run build生成网页。

配置DATABASE_URL（postgresql+psycopg连接串）。脚本默认工具目录C:/U8Runtime/pgsql/bin、数据目录C:/U8Runtime/pgdata，按实际安装修改；不会自动初始化数据库。

模拟启动：powershell -File scripts/start-backend.ps1。
真实启动：powershell -File scripts/start-u8.ps1 -CredentialsHtml "C:/U8Config/credentials.html"。
真实启动前核对脚本账套参数，999/megsky不是通用配置；亦可设置U8_APP_KEY/U8_APP_SECRET环境变量。凭据需自行提供。

启动器负责迁移和API、Worker、Monitor；不要只启动uvicorn。访问http://127.0.0.1:8000/。集中日志可通过deploy/observability/compose.yaml启动。

## 测试与限制

前端目录运行npm test、npm run lint、npm run build；后端目录使用虚拟环境Python运行-m pytest tests -q -p no:cacheprovider。后端测试需要PostgreSQL。

本包不含依赖目录、编译产物、数据库数据、日志、凭据或版本历史。未在其他电脑执行安装验收。

当前仅限本机受控使用，缺少登录权限；校验后修改部分表头仍可能提交旧数据，应核对持久化任务后确认；无表头信息的旧模板需人工复核。详见docs维护与运维指南。
