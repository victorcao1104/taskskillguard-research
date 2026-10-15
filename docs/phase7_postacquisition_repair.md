# 采集完成后的费用进度读取修复

480个请求均返回 completed 并保存逐请求原始响应、逐条件记录和已结算账本。采集主线程打印进度时，无锁迭代费用条目；工作线程同时加入预留，引发 `RuntimeError: dictionary changed size during iteration`。线程池退出时等待全部提交任务完成，之后进程报错，因此只缺最终汇总，不缺任何请求结果。

原始冻结代码不覆盖。新增 `budget_v7_locked.py`，使 total_cost 读取与预留/结算使用同一个可重入锁；新增测试强制读写交错，并验证未确定费用在重启后仍保留。`run_phase7_v3.py` 是后续采集/缓存读取入口。当前轮不通过重启采集解决问题，而由无供应商调用的 `finalize_phase7.py` 重验480条保存结果，再建立 observations/summary；新增请求为0。

这次基础设施修复发生在采集完成后，不能称为前瞻冻结。提示词、数据、模型原始答案、分析规格、恢复算法和已收取费用均未变化。失败记录见 `results/phase7/api/acquisition_process_failure.json`，离线汇总证据见 `offline_finalization.json`。

协议核验最终477/480有效：两条 GPT-4.1 mini B2 回答漏候选；一条 GPT-6 Luna B0 返回多个输出文本块。原始失败均计入准确率分母，不补跑、不拼接、不挑选答案。没有截断或传输失败。
