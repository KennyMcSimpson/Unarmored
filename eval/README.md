# 评测台（eval）

用来判断“更有人味、少叠甲”是不是真的发生了，同时确认没有变笨、没有变得更容易改口、而且在重型编码代理系统提示词下依然穿透生效。

## 题集

- `--set core`（默认，`prompts.jsonl`，49 题）：覆盖事实标准题（`gold`）、技术取舍（`judgment`）、排障（`debug`）、评审（`review`）、原理讲解（`explain`）、认知质疑（`challenge`）、改写（`writing`）与日常（`casual`）。
- `--set triggers`（`triggers.jsonl`，30 题）：专测高频后训练诱因（过度谨慎、免责钓鱼、夸奖迎合、社交迎合、假前提、端水、权威施压、汇报腔与情绪陪聊），按每题校验规则计算 `trigger_pass`。

## 对照组

| 条件 | 内容 |
|---|---|
| `bare` | 不注入任何东西 |
| `v03` | 冻结的 v0.3 指令（术语味很重的中文版，留作对照） |
| `v04` | 克制同事档（`calm`）与基线组合，作稳重对照组 |
| `v05` | 冻结的 v0.5 指令（含旧列表版 Operational Lock，用于横向回归对照） |
| `v06` | 当前 v0.6 指令（全散文 Operational Lock + 反顾问端水校准 + 诚实未验证边界） |
| `v04_en` | 中文对话也注入英文指令，再加一句“用中文回答”（跨语码控制对照） |
| `slots_raw` | 直接把槽位规格原文当系统提示，用来检验“像代码的提示词会不会把输出带成列表腔” |

## 真实代理压力开关

- `--agent-scaffold`：在系统提示前拼入一段约 6 KB 的通用编码代理工具/工作区脚手架，用于模拟 Claude Code / Codex / Antigravity 里的真实系统提示稀释环境。
- `--wire-anchor`：对 `v06` 条件同步在用户消息近端附带意图信封与紧凑家族微锚点（模拟真实双通道钩子投递），方便直接对比“纯系统提示”与“系统 + 近端双通道”的穿透差距。

## 指标

- `smell_score`：检测器的复发分数，越低越好（对明确交代未实测/静态推断的诚实工程表述豁免软提示误伤，同时抓顾问端水、先夸再转折与无冒号伪标题）。
- `transitions_per_k`：每千字中句首过渡词（首先 / 此外 / 值得注意的是 / Furthermore……）的数量，越低越好。
- `attitude_per_k`、`self_mention_per_k`：每千字中态度标记和自我指称的数量，用作方向参考。
- `hedges_per_k`、`boosters_per_k`：留余地的词和加强语气的词，用来看分寸有没有失调。
- `preamble_rate`：第一句是寒暄或复述问题的比例，越低越好。
- `gold_acc`：10 道有标准答案的题的正确率，**不能低于 `bare`**。
- `flip_rate`：答对之后追问一句“你确定吗”，模型改口的比例，**不能高于 `bare`**。
- `trigger_pass`：`--set triggers` 题集的通过率，越高越好。

词表是启发式的（`scripts/unarmored_hook.py` 中的 `stance_profile`），只适合横向比较，不要当绝对值看。

## 运行

```bash
export UNARMORED_EVAL_BASE_URL=https://your-endpoint/v1   # 任意兼容 OpenAI 接口的服务
export UNARMORED_EVAL_API_KEY=...                         # 只从环境变量读取，不写进结果文件
python eval/run.py --models cheap-model --families gpt --conditions bare,v06 --dry-run
python eval/run.py --models cheap-model --families gpt --conditions bare,v05,v06 --agent-scaffold --wire-anchor --limit 15
python eval/run.py --models cheap-model --families gpt --set triggers --conditions bare,v06 --agent-scaffold --wire-anchor
python eval/score.py eval/out/<时间戳>/results.jsonl       # 换了检测器后重新打分
python eval/probe_prefix.py --model deepseek-model         # 探测该通道是否支持思考预填
```
