# 字段与业务定义

输入编码 UTF-8，允许 BOM。首行必须匹配样例列顺序。记录键和业务组保留原始字符串。`kind` 允许 column, dependency, approval, audit。说明列 `note` 可以跨行，限制 200 字。

业务字段按 `field`、`parent`、`grade`、`day`、`until_day` 排列。最终值单位见阶段结果。数字接受非负整数、全角数字和完整千分位。空串、短横线、N/A、NULL 与未知为缺值。无关字段用 0 占位。

等级 0–3，取自身和上游的最高值。区间左闭右开。已准许的降级结果继续传播，但不得低于字段自身登记级别。重叠审批单在重叠日不生效并将该日标记为 `APPROVAL_OVERLAP`；首尾相接（前单 `until_day` 等于后单 `day`）不是重叠，交界日由后单覆盖。

每个业务组额外生成一个 7 日签发日历：`schedule.days` 逐日给出 `day`、`grade`/`label`、`expected`、`status`、`signable`、`held` 和 `overlap`，并汇总 `signable_days`、`held_days`、`overlap_days`。对账结果的 `balance.daily` 展平所有业务组的逐日结论，不能只核对审计日/周末。

`incoming.csv` 包含四个业务组，第二组提供不同边界，第三组触发业务拒收，第四组需要核对。另含重复表头、冲突记录、重复回放与错误列数。`ready.csv` 含可以签发的两个组。
