# 第二轮独立审阅与交付核验

审阅覆盖真实样本模型输入、P/Q闭环、生成合同的实际使用、OS缓存/计分、unknown分母、静态图归属、完整网格与报告图形。没有将源Skill指令作为代理指令执行。

| 发现 | 处理与证据 |
|---|---|
| 旧E3合同解析丢失unknowns，可能把不确定合同当已决定安全 | 从不可变raw恢复29槽位/27响应，对应116条执行移出decided分母；原运行不改写，分析保存raw SHA |
| 缺Q计划可变成空动作但继续计安全 | analyzer拒绝非valid q_plan_status，未来runner显式unresolved；现有264计划全valid，结果不变 |
| 仅按case ID连接可能误用修改后的任务 | 固定四个最终manifest文件，核验phase和数据SHA；当前全部匹配，历史不同SHA记录仍保留 |
| no_guard也绕过taint/lease检查 | 报告解释为移除共享执行检查点，未改冻结实验；no_taint/no_lease是独立条件 |
| graph_v2与旧模型图不能混为一个轨道 | 报告明确新图仅离线结构对照，模型请求仍使用冻结legacy图 |
| OS旧embedded oracle接受过宽输出 | 使用实际输出和required effects的外层v2任务判定，保留旧布尔值与失败；见Oracle修正记录 |
| OS图同时汇总low/high与all_contexts导致重复 | 只绘制all_contexts并新增回归，oracle有效分母24而非48 |
| mini未知记录不应画成0% | 图表明确NA与88个unknown，统计不计作安全或成功 |

集成后本机全套 **158 passed / 4 skipped**。四项Docker测试需显式环境开关，默认离线检查跳过；真实容器实验另外保存240正式运行与65来源/Replay运行。新复现CLI的四次CSV自检独立归档，不计入正式分母。其4/4任务成功、两个无守卫执行越权，验证正反路径。

`verify_phase2_release.py` 核对每个计划键而非仅看行数，拒绝重复/缺项，验证内容寻址raw、P输入边界、240条聚合与逐次记录一致、真实样本声明、三类Replay和Judge、盲审包、180包/3414文件零变化及USD20累计上限。`verify_release.py` 另核验旧2724条模型回链、发布字节哈希和凭证格式。无误结果保存在发布验证资料中；检查不能代替真人语义真值。

图形经实际PNG渲染查看；报告、表格与图均从保存记录离线生成。最终证据清单对Git暂存字节与工作文件进行一致性检查。没有为了好看的结论删除原始失败或把unsupported归安全。
