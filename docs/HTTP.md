# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean` 或 `file=<CSV>` 三选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批和当前复核状态。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、业务证据和复核信息的 JSON。

业务报告的每个可计算分组还包含 `schedule`（7 日签发日历）、`days`/`daily_labels`（逐日记录）以及 `signable_days`、`held_days`。`balance.daily` 是跨分组的逐日对账记录，`balance.daily_reconciliation.days` 按日期汇总；逐日标签不满足下游等级或审批重叠时，该日为暂缓而不是可签。
