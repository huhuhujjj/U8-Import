# U8采购订单导入平台源码

纯源码交付：frontend前端、backend后端与迁移测试、scripts启动脚本、deploy日志配置、docs维护指南、test-data模拟样例。保留frontend/LICENSE及依赖版权信息。

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
