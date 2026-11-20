# 内网运维部署与保底机制

## 当前金额规则（用户调整）

不再比较源表金额与数量×单价，也不做含税/未税金额换算核对；未映射的金额列为空或不一致不会阻止导入。保留中英文金额列误映射为单价的拦截、数量/单价格式及范围校验、明确单价表头与所选税口径的一致性检查。源表金额仅作为原始数据留存，不替换单价、不作为订单金额直接提交；含税/不含税模式仍决定提交U8的单价字段。历史失败任务需重新校验，不能直接确认导入。

## 部署约定

默认8000端口仅限本机使用，使用前配置自己的数据库、凭据和账套。

## 启动

先启动 PostgreSQL，然后在项目根目录执行 `powershell -File scripts/start-backend.ps1`（MOCK）或 `powershell -File scripts/start-u8.ps1`（U8）。两个入口现均调用 `start-managed.ps1`，启动 Web、独立 Worker、监控三个进程。不要同时运行旧版 Web 后台执行器。默认仅监听本机 8000，不自动开放防火墙。

守护程序需持续运行；子进程退出后退避重启，累计五次异常退出后停止整组，避免重启风暴。关闭守护程序会停止它拥有的子进程。主机重启后手动执行启动脚本。

运维页面：`http://127.0.0.1:8000/operations`。可查看数据库、Worker、队列状态、磁盘、备份告警以及跨进程日志。日志 API 为 `/api/operations/logs`，支持 `job_id`、`level` 过滤；上限500条，只读取受控日志目录。

## 任务与恢复

- Alembic `0004` 增加 `queue_tasks` 与 `worker_heartbeats`；启动脚本先迁移，失败则禁止启动。
- Web 不执行真实任务；校验/确认/重试与入队在同一事务提交。满队列返回503并回滚。
- 默认每目标账套一个活动消费者，由 PostgreSQL 会话锁协调多个 Worker；不以时间戳过期为理由抢占仍持锁的进程。
- 任务状态 PENDING/RUNNING/DONE/DEAD。进程崩溃释放锁，RUNNING 可以恢复；最多3次恢复，超过后隔离。
- U8 提交标记在网络调用前持久化；恢复先回查，禁止因网络超时重复提交。业务拒绝不自动无限重试。
- 每5秒心跳，30秒未见心跳告警。默认单任务30分钟期限，超时退出整个 Worker，由守护程序重启；未完成任务仍持久化。不是强杀某个线程后让它继续操作 ERP。
- 连续基础设施故障退避；连续3次故障将待处理队列延迟60秒，降低对上游持续施压。
- 磁盘不足1GB拒绝入队；队列默认最多100个活动任务，可设置 `QUEUE_CAPACITY`。
- 隔离任务不自动删除；在原任务核对结果后调用既有重试接口。不能清除 `remote_state` 来强迫重建。

## 日志与告警

JSON 字段含时间、级别、进程、请求 ID、任务 ID、事件和耗时。响应带 `X-Request-ID`。每进程独立文件（API/Worker/Monitor），单文件5MB，保留5份轮转。Monitor 删除超过14天的本系统日志；总量超过512MB时清理超过1小时未更新的旧日志，不删除活跃文件。

日志不记录原始请求体、SQL参数或完整异常文本，凭据与 token 脱敏。`audit_logs`、`import_errors`、`erp_results` 是业务证据，不随日志清理删除。运维接口没有独立认证，当前部署必须保持本机访问；共享到内网前应加访问控制。

本地告警：数据库不可用、Worker离线、失败隔离、排队超过5分钟、磁盘不足、36小时无成功备份。Monitor 将告警变化写入 ERROR 日志，恢复写 INFO；不向邮箱、群聊或第三方发送通知。

日志中的 `environment` 默认来自 U8_MODE（u8/mock）。pytest 在测试收集前强制设置独立临时 LOG_DIR 和 test 环境，子进程继承；禁止手工将测试日志复制到运行采集目录。Grafana错误告警仅统计 environment=u8/mock，测试日志及无环境标记的历史日志不计入该规则。旧服务需要重启才会生成带环境标记的新日志；历史日志保留用于追溯。

旧任务恢复按目标账套和剩余队列容量分批入队，Worker每次消费前继续恢复；队列已满先消费，不要求全部旧任务一次性迁入。现有隔离任务不会自动重新入队。

可选跨主机收集配置在 `deploy/observability`：

```powershell
docker compose -f deploy/observability/compose.yaml up -d
```

Alloy → Loki → Grafana，端口仅绑定127.0.0.1。Grafana 地址 `http://127.0.0.1:3000`，首次登录需更改默认管理员密码；预配 Loki 数据源和最近5分钟错误日志告警。配置校验不代表容器服务已运行，须验证 Loki `/ready`、Grafana `/api/health` 和日志入库。本机集中日志页面不依赖 Docker。

## 备份

守护启动器在找到 PostgreSQL 工具后启用 `AUTO_BACKUP=1`；可传 `-PgBin` 指定 PostgreSQL bin 目录。Monitor 每24小时备份，失败最多每小时重试，备份超过36小时会告警。手动执行：

```powershell
powershell -File scripts/backup-database.ps1 -PgBin "C:\path\pgsql\bin"
```

备份位于 `backups/u8-*.dump`，保留30天；先写临时文件，经 `pg_restore --list` 验证后原子改名并更新 `last-success.json`。密码通过子进程环境传递，不进入命令行。备份与主库同机保存。


## 开发验证

`backend/tests/test_operations.py` 覆盖原子入队、队列满回滚、崩溃回查、并发消费者、失败隔离、日志脱敏/轮转/保留和告警；`test_worker_process.py` 使用真实 TCP、独立 Web/Worker 进程与隔离 schema 验证跨重启恢复。全量测试命令为 `..\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider`（backend 目录）。

这些测试不证明 U8 真实账套容量，独立 Worker 默认串行写入。此前短时 TestClient 40任务结果不能称作40个生产用户的稳定容量承诺。
