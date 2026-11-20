# 维护与开发指南

本文描述当前版本；启动和日常运维以[OPERATIONS.md](OPERATIONS.md)为准，业务边界以[README](../README.md)为准。

## 架构与代码地图

浏览器解析文件 → 创建持久化任务 → Web事务入队 → Worker校验 → 用户确认 → Worker提交U8/回查 → 保存结果。默认每个目标账套一个活动消费者；结果分批落库不代表拆成多张U8订单。

| 文件 | 职责 |
| --- | --- |
| frontend/src/App.tsx | 工作台、任务确认、状态轮询、历史记录；显示后端分配编号 |
| frontend/src/u8/parser.ts | 文件解析、表头识别、映射与数字校验 |
| backend/app/main.py | API、事务入队入口、静态前端和运维页面 |
| backend/app/api/schemas.py | 请求契约、字段及行数限制 |
| backend/app/business/purchase_order.py | Decimal标准化、业务键、payload哈希 |
| backend/app/business/amount_validation.py | 金额列误映射、明确单价税口径检查；不比较源表金额 |
| backend/app/services/import_service.py | 后端编号、业务校验、执行预留与审计 |
| backend/app/tasks/queue.py | 事务入队、容量及磁盘门禁 |
| backend/app/tasks/worker.py | 独立消费者、按容量恢复、心跳、有限重试与隔离 |
| backend/app/tasks/import_tasks.py | 整单执行、结果不明回查、分批持久化 |
| backend/app/integrations/u8/live.py | 当前账套主数据匹配、U8字段转换和回查 |
| backend/app/observability.py | JSON日志、脱敏、请求关联、按大小轮转 |
| backend/app/operations.py | 健康快照、本地告警、日志查询与保留、定期备份入口 |
| backend/app/backup.py | 本机归档备份及目录检查 |
| backend/app/models/entities.py | ORM实体 |
| backend/migrations/versions | 只追加的数据库迁移 |
| scripts/start-managed.ps1 | Web/Worker/Monitor进程守护 |
| deploy/observability | Alloy/Loki/Grafana本机集中日志配置 |

## 数据库与迁移

当前版本0004：0003增加模板source_headers，0004增加queue_tasks和worker_heartbeats。启动器自动升级；手工检查从项目根目录执行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic current
..\.venv\Scripts\python.exe -m alembic upgrade head
```

新表/字段必须新增迁移，不能重写已应用版本。不要删除订单幂等键、持久化提交标记或审计记录来强制重建。业务表包括import_jobs、import_rows、import_errors、order_executions、erp_results、audit_logs和field_mappings。

## 日志与排错

运行日志位于项目logs目录，API/Worker/Monitor按进程分别写JSONL；每个文件5MB、5个轮转文件，包含environment、请求ID、任务ID等。测试使用独立临时LOG_DIR，不混入运行采集目录。运维查询排除test环境，Grafana本地规则仅统计u8/mock。

业务证据在audit_logs、import_errors、erp_results和order_executions。先用任务ID串联记录，再决定原任务重试；结果不明时先回查，禁止盲目重复POST。运行日志保留策略不删除业务审计表。

/api/health检查数据库及模式；/api/u8/connection只读验证真实连接；/api/operations检查队列、Worker和本地告警。DEAD任务会使总体healthy=false，即使数据库和Worker均正常；当前没有告警确认归档入口。操作者仍固定local-developer。

## 测试

从项目根目录执行，确保PostgreSQL可用：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
Set-Location ..\frontend
npm.cmd test
npm.cmd run lint
npm.cmd run build
```

后端测试使用随机隔离schema，结束清理对应测试schema；pytest在收集前设置临时日志目录和test环境，子进程继承。测试不能复用真实U8写入客户端。前端测试会更新test-data/payload_10.json、payload_100.json、payload_300.json的解析耗时，提交前检查并还原仅由本轮测试产生的变化。

benchmark.py使用TestClient与MOCK且会写数据，应只连接专用测试数据库。短时只读并发、MOCK并发与真实导入用户数不能互换；尚未验证真实最大并发人数或10000行稳定容量。

## 修改与发布检查

- 保留raw_data与normalized_data一致性检查、当前账套档案核验及重复提交保护。
- 前端创建任务不传订单标识，由后端分配；U8实际单号以回查为准。
- 金额列不能充当单价；原始金额不参与数量乘单价比较。
- 后端修改通过相关测试后，先检查活跃队列再重启守护程序，验证模式、连接和Worker。
- 前端修改需重新build，用户刷新后加载新资源；仅修改文档无需重启服务。
- 日志、备份、凭据和构建依赖不提交Git；提交前检查暂存清单与diff。

已知交互问题与限制见README中的已知限制，不要把既有测试通过解释为全部业务场景无缺陷。
