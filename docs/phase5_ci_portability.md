# 第五轮发布修正：ZIP 输入的跨平台字节一致性

初始发布提交 `9ecff1dc5cd78220fdb02c96869d65d7860fdbd4` 在 Windows 的完整测试为 738 passed、4 skipped、150 subtests passed。上传后的 Ubuntu CI 暴露了一个确定性错误：archive_manifest 的 ZIP 输入设置了固定时间，却没有设置 `ZipInfo.create_system`。Windows 默认值为 0，Linux 为 3，两个中央目录条目因而有不同字节。任务内容和答案没有变化，但严格冻结输入检查正确地拒绝这种差异。

已保存的 [首次 CI 失败](https://github.com/victorcao1104/taskskillguard-research/actions/runs/38804973296) 及其他旧工作流都指向同一个失败测试。新增参数化回归在 Windows 上模拟 0/3 两种默认值：修复前 0 通过、3 失败；修复后都通过。实现只显式设置 `create_system = 0`，使所有宿主重建最初在 Windows 上冻结并实际执行的输入。没有改变任务内容、真值、worker 代码、策略、效果、任何原始结果或费用。

修改前的四个文件逐字节保存在 `results/phase5/provenance/ci_portability_original/`，其摘要必须与原 `release_hashes.json` 匹配。`ci_portability_amendment.json` 记录旧/新摘要；`release_hashes_v2.json` 封存当前版本。验证器要求：原清单中未声明修改的所有文件仍完全相同，声明文件必须同时验证原始快照和当前版本；随后逐一核对新的发布清单及所有实验记录。原 `release_hashes.json` 和 `release_verification.json` 不覆盖。

新版本仍对 180 条保存的输入、worker 摘要、效果证据和重新评分执行完整核对。它不调用 Docker 或 API。现有报告里的所有结果数字和累计费用不受影响。

修复后完整本地测试为 740 passed、4 skipped、150 subtests passed（44.36 秒）。比初版增加的两项检查分别模拟 Windows/Linux 的 ZIP 默认创建系统值。首次失败日志原文保存在 `results/phase5/provenance/ci_portability_first_failure.log`。

复核命令仍为 `python scripts/verify_phase5_release.py`，会自动验证修订链。完整结果保存在 `release_verification_v2.json`。若需要重新实际运行容器，请使用新的输出目录冻结当前宿主生成源码摘要；旧目录的执行冻结摘要包含修复前模块，原 runner 会拒绝就地更换冻结清单。检查旧证据只需离线验证器，不能把 source-hash 拒绝绕过成覆盖实验。
