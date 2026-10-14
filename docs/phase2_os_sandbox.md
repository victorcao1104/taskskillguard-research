# 第二轮 OS 沙箱、原始脚本与 Replay 证据

本轨道实际使用 Docker Desktop Linux Engine 29.7.2、WSL2 Linux 5.15.167.4、Python 3.12.15 和 strace 6.13。最初的 Linux engine pipe 不存在；只读诊断确认 WSL2 的 `docker-desktop` 已安装但停止，启动已有 Docker Desktop 后恢复。没有更改 Windows 功能、重启系统、在宿主运行语料脚本或调用模型 API。

## 隔离与审计

`src/tsg/os_sandbox.py::ContainerSandbox` 为每次运行创建独立容器、独立 source volume 和独立 tmpfs。没有宿主 bind mount、用户目录、Docker socket、API/SSH Key、真实云凭证或宿主执行 fallback。原始 bundle 先由宿主只读代码校验 manifest 的逐文件 SHA256；拒绝链接、路径穿越、非普通文件、超过 256 文件或 8 MB 的包。仅有限副本经受控 tar 输送到 Docker 管理的 volume，执行时挂载 `/source` 为只读。短暂的 staging helper 只运行可信 `sleep` 程序，不执行输入内容，且在实验容器启动前销毁。

固定边界为 `--network none`、只读 rootfs、0.5 CPU、256 MiB RAM/相同 swap 上限、64 PIDs、128 个文件描述符、进程 CPU 8 秒、payload wall 20 秒、host 45 秒 deadline，以及有容量上限的 sandbox/audit/tmp tmpfs。工具 fixture 另限 64 步；任意源脚本没有通用语义步骤计数器，不能将 CPU/时间限制称为指令步数证明。

可信 supervisor 以容器 root 运行，仅保留 SETUID、SETGID、SYS_PTRACE、KILL 和 DAC_READ_SEARCH，分别用于降权、子树审计、超时终止与读取源程序生成的 mode-0600 输出。payload 在 exec 前变为 UID/GID 10001，清空 supplementary groups，实测 `CapEff=0`、`NoNewPrivs=1`。Docker 默认 seccomp 保留。SYS_PTRACE 属于审计 supervisor，不授予语料脚本。该容器边界不是形式化内核逃逸证明。

strace 跟踪实际 `%process,%file,%network` 系统调用及返回码；`/audit` 为 root 所有的 0700 tmpfs，payload 的篡改探针得到拒绝。源码写入/rootfs 写入探针得到 EROFS/EACCES，TEST-NET 地址 `192.0.2.1:80` 的 connect 得到 ENETUNREACH。HTTP/SMTP 使用同一隔离 namespace 的 loopback 服务，不需要外部网络。原始系统调用日志、payload stdout/stderr、Docker 实际 HostConfig/Mounts、输出文件和 oracle 结果均落盘。Docker Desktop 的 archive API 未可靠读取 tmpfs，因此可信 host collector 通过 bounded `docker exec` 读取证据；不从 payload stdout 推断系统调用。

## 两种执行范围必须分开

1. **sandbox-mediated containment**：原始第三方 `.py/.sh` 由容器内解释器直接执行；OS 限制保护宿主，strace 记录真实副作用。此模式没有逐工具授权守卫，也不声称实现任意 Python 的信息流控制。
2. **tool-mediated enforcement**：研究者编写的有限 fixture 在真实 OS 操作前检查 `{operation,resource}` 精确合同。file.read/write、只读 git log、只读 SQLite query、HTTP POST、SMTP send 均产生实际效果与工具事件。它不同于 `contracts_v2.py` 的更丰富参数/期限/SMT DSL；不得混称同一端到端编译器或将它移植到任意脚本后宣称已覆盖旁路。

HTTP high 明确允许读取无价值测试 token `/sandbox/fake_secrets/token.txt`，仅用于向 loopback `/status` 认证公开正文 DONE；mock 服务实际验证 header、方法、路径和正文。SMTP high 明确允许向 `recipient@example.invalid` 发送；low 只要求本地状态/草稿。它们提供合法网络和授权 Token-service 负例，避免把全面禁网当成策略安全能力。

稳定接口和任务见 `results/phase2/os/fixtures_manifest.json`。调用形式：

```python
row = fixture_manifest[0]
result = ContainerSandbox(image=frozen_image_id).run(
    {**row['job'], 'guard_enabled': True, 'policy': row['oracle_policy']},
    evidence_dir,
)
```

`result.tool_events` 给出 operation/resource/decision/required/executed；`sink_events` 来自独立 mock 服务；`audit` 来自 strace。任务是否完成、操作是否授权、进程是否退出 0 是三个不同字段。runtime_error/timeout/unsupported 不能计为安全成功。

## 已执行来源与任务

初始六类 fixture：真实单页 PDF、CSV 数值报告、三个提交的 toy Git repo、HTTP 服务、SMTP 服务、SQLite 假数据。Original/Neutralized/Reference 共 **18 次运行，18 次输出 oracle 通过**。每次都是新容器；参考实现为独立可信文件 `containers/reference.py`。这些初始对照统一中和 optional cache，因此六种任务不等于六种 action 类别。

原始语料第一次执行 30 个 development bundle：21 个退出 0、9 个实际 runtime_error。27 个仅是 CLI/interface smoke；它们的 task goal 明确为 null。三个有具体功能任务：JSON→SVG 图表、README 命令提取、Skill scaffold 生成。最初图表生成成功但写入 0600 文件，supervisor 缺读取 capability 导致 oracle false；该失败保留在 `sources/real-ad66beacd76f4c0e/`，修复审计读取权限后的 development rerun 位于 `supplemental/`，未改语料或图表期望。

随后在 commit **ed42057** 冻结 held-out source manifest、固定输入、输出特征、代码与 image ID 后，仅首次执行 `real-4d0159bbc4e714bf` 的 `scripts/component_builder.py`，生成指定名称、schema 和生命周期方法的 A-Frame boilerplate；首次 oracle 通过。该检查只验证指定生成物，不验证浏览器中的 A-Frame 运行行为。`heldout_source_frozen_manifest.json/.sha256`、`supplemental/.../source_result.json` 保留冻结与首次运行证据；没有根据 held-out 输出调整 oracle。

最终 **31 个不同原始 bundle、32 次 source 运行、4 个明确功能任务成功、27 个接口探针**。最新逐 source 状态为 22 executed / 9 runtime_error；退出 0 不自动成为任务成功。全部 180 个样本的 `compatibility_report.csv` 包含未动态执行的明确原因。9 个失败包含缺失 docx/onnx 等依赖、包内相对导入不适合作为 standalone entrypoint、非零 CLI 退出；没有自动安装第三方 Skill 所要求的任意依赖来获得表面通过。

与原 manifest 重比 **31 个 bundle、529 文件，变化 0**，见 `source_immutability.json`。这些是有界功能检查及一次 supplemental held-out source 检查，不是 180 个真实 Skill 的完整三任务动态 GT。

## Replay 的有效性与修订

`replay_verdict` 不把失败解释为必要性。缺少触发 → not_triggered；替换不合法 → invalid_ablation；原任务失败 → original_failed；运行错误单列。仅在参考工作流达成同一目标且明确排除候选动作时，参考成功才支持不必要性；参考也读取原文件时，不能据此称该读取不必要。

初次额外 HTTP/SMTP send 对照保留在 `replay_multiaction/`。复核发现两个 frozen-c2 oracle 缺陷：HTTP-low 任务指定 READY，旧 checker 却也接受 OK；SMTP-high 任务要求草稿及发送，旧 checker 只验发送。前者使额外 HTTP-low 对照的任务语义无效，**不计为有效 unnecessary 证据**。未修改旧日志或模型权限；formal OS E3 应以保存的实际输出重新计分，并同时保留 embedded/raw oracle。修正后的独立 `corrected-oracles` image 用两个反例验证：HTTP-low 实际写 OK 判失败；SMTP-high 未写草稿但发信成功仍判失败。

最终的类型保持中和轨道在 `typed_replay/`：file.write 返回整数 0 而不写 cache；file.read 返回同类型、同 CSV schema 的零值替身，随后正常计算；email.send 返回同类型 True acknowledgement 而不发邮件，保留下游控制流。每个动作 Original/Neutralized/Reference 三路，固定 manifest 和 source hash 在执行前保存。**9 次进程执行全部成功，3 种 action 的 ReplayValid 为真；8 次目标满足，CSV read 中和的 1 次目标不满足符合预设。** CSV read 的 reference 仍读取候选文件，因此 necessity 保持 unknown；write/send 两例有排除候选的目标成功轨迹，支持不必要性。不能将这个 unknown 当失败标注或安全真值。`replay_summary_final.json` 是最终判读入口，旧 `replay_multiaction/comparisons.json` 仅保留修订前记录。

## 资源、环境与复现

`resource_metrics.csv` 保存逐 run 的真实 `getrusage` CPU、cgroup v1 memory.max_usage_in_bytes、wall time 与系统调用数。CPU 包含 tracer 和 payload 后代，不含 fixture 初始化；cgroup RAM 包含 supervisor、fixture 与 payload。child maxrss 是包括初始化子进程的 high-water mark。早期 image 的 payload-wall 字段还包含 oracle 时间，比较运行成本优先使用一致的 container-wall 字段。

初始 18 fixture 的平均 CPU **0.340 秒**，平均整个容器 memory peak **28.49 MB**，最大 **32.69 MB**，平均包含容器管理的 wall **4.268 秒**。这些不是模型 API 或整个研究的 CPU/RAM。原始 source 与后续 replay 分组单列，不用重复 fixture 充当独立 Skill 家族。

`image_dependency_inventory.json` 记录实际 Python 3.12.15、git 2.47.3、strace 6.13、reportlab 4.4.4、pypdf 6.1.1、Pillow 12.3.0、charset-normalizer 3.5.2。基础 Python image 使用 digest；正式 source/OS E3 固定 image `sha256:c2b1b937174f8826eb24ce3616023c78ea50a5aa98b73fee913a13506a365244`。后续 replay/修正各用不同 image digest，不能悄悄替换正式镜像。apt repository 未冻结 snapshot，Pillow 等转依赖由 inventory 记录但 Dockerfile 未全部锁定；未来联网重建不保证 bit-for-bit 相同，精确复放需使用已记录的 image。

```powershell
# 当前源码的修正镜像；不要覆盖用于历史正式计分的固定 image ID。
docker build -t taskskillguard-os:corrected-oracles containers
$env:TSG_OS_INTEGRATION='1'
$env:TSG_OS_CORRECTED_ORACLES='1'
.venv/Scripts/python.exe -m pytest tests/test_os_sandbox.py -q --basetemp results/phase2/os/fresh-test-temp
.venv/Scripts/python.exe scripts/run_os_experiments.py --summarize
```

原始只读 corpus 必须存在于 manifest 指向的位置；summary 的不可变校验需要读权限。source/typed replay 的冻结首次执行命令拒绝覆盖现有记录，复现应使用新 evidence 目录，不删正式结果。后续 formal E3 模型合同与计分由 `scripts/run_os_e2e_phase2.py` 负责，本文不将尚未确认完成的 API 任务称为已执行。

局部测试已验证 OS containment、真实可选写拒绝、归档 traversal/hash/容量边界、不可比 replay 处理及 reference guard bypass 拒绝。一次全套测试在 graph-v2 模块正在实现时得到 102 passed / 14 missing-module failures；最终全套核验由主运行在集成完成后执行，不能把这次中间失败隐藏。旧开发诊断和失败测试目录保留，不进入正式实验分母。
