# 第五轮复现与验证

正式入口：主采集 `results/phase5/acquisition_v2/`；提取首次测试 `results/phase5/extraction_primary/`；实际执行 `results/phase5/recovery_primary/`；主分析 `results/phase5/analysis/`；语义澄清补测 `results/phase5_q017/`。无 `_primary` 的 recovery 目录只有先前规划快照。

环境：Python 3.12、旧 `configs/requirements-lock.txt`，新增分词依赖固定在 `configs/phase5-requirements.txt`。旧锁文件和工作流保持原字节。安装这两份依赖后，在仓库根目录先创建 `work`，再运行：

```text
python -m pytest -q --basetemp work/phase5-tests
python scripts/verify_phase5_release.py
```

验证器离线核对所有继承文件、冻结请求、原始响应重新解析、预算账本前缀和 180 次执行证据。不会调用 API、Docker 或原始 Skill。旧工作流未安装可选分词库时只跳过新增的分词控制测试；第五轮工作流安装固定库并运行全部测试。首次载入官方分词表可能需要联网下载到 `work/tiktoken`，之后本地缓存可用。

可重复运行 `prepare_phase5.py` 重算冻结提取结果（输出不同会拒绝覆盖）。人工包修订用 `extend_review_phase5.py`，已经填写的标注应保存在独立工作副本。`analyze_phase5.py --out <新目录>` 从保存证据重算主分析；输出目录必须不存在。它保留 18 家族主结果及排除 q017 的 17 家族敏感性，不把补测混回主结果。

需要重新执行时，必须明确区分“验证保存结果”与“采集新重复”。主 API 脚本不带 `--execute` 只检查/冻结。已保存的失败不会自动重试；已持久记录发送意图但没有回答时，恢复为 `interrupted_unknown`。主采集与 q017 补测共用一个账本，只能顺序单进程写入。不能复制空账本或并行启动两个采集程序。供应商密钥不在仓库内，也不是复核现有结果的条件。

Docker 实验固定镜像摘要见 recovery frozen_grid。`run_recovery_phase5.py --execute --resume --workers 3 --out results/phase5/recovery_primary` 重用所有保存条件，包括失败。主机不执行语料代码；容器无外网、无宿主挂载、非 root、只读根目录。保存结果是有限工具网关实验，不能被复现说明扩写为任意程序安全证明。

历史结果及本轮首次快照均不可就地修正。任何新增参数、修复或重新采集应使用新目录并附来源摘要、原因和比较口径。

遗漏文件清单因重复完整来源元数据达到 206,582,997 字节。仓库以 `data/phase5/human_review/omitted_files.jsonl.gz` 无损发布；解压后与本地首次 JSONL 的摘要完全一致。验证器直接检查 gzip 和原文字节摘要，不要求手动解压。`extend_review_phase5.py` 可重建本地原文；`package_phase5_omissions.py` 检查压缩往返。原文只在本地 Git exclude 中排除，旧 `.gitignore` 未改，压缩包完整上传。
