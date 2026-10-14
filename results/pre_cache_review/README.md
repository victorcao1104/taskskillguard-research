# 响应缓存和边界校验复核前结果

保留 development、validation、real 的早期派生结果。复核发现相同 fingerprint 的并发请求可能产生多笔计费而覆盖同一个原始响应文件。修复后使用最终保存的原始响应重新解析所有正式派生结果，不重新挑选模型输出。无法恢复的早期响应内容不伪造；对应 settled / reserved 金额继续计入总费用上界。

graph 资源定位与 contract schema 的校验同时收紧。这里的旧结果不纳入最终统计。正式结果中的每个 request_hash 必须能在 `results/api/raw/` 重新解析。
