# KB 评测体系建设

**Date:** 2026-05-10
**Status:** approved
**Project:** kb

## 背景

当前测试体系：125 条测试，74% 覆盖率，E2E 测试被跳过。三个核心缺口：
1. RAG 搜索/答案质量无法量化评估
2. 多个模块覆盖率不足（watcher 0%, llm 46%, rag 53%）
3. 缺乏回归对比机制

## 目标架构

```
kb eval ──→ dataset.json ──→ search + rag ──→ scoring ──→ report
                                                           │
                                                    eval/results/
```

三层体系：
- **评测数据层**：LLM 自动生成 + 人工审核的查询集
- **执行引擎层**：`kb eval` 子命令跑搜索/RAG 评测
- **代码测试层**：pytest 补齐覆盖率到 80%+

---

## 一、评测数据集

### 目录结构

```
eval/
├── dataset.json
├── results/
│   ├── .gitkeep
│   └── 2026-05-10T143000.json
└── README.md
```

- `dataset.json` 版本控制，作为唯一真源
- `results/` gitignore，评测结果不提交
- `results/baseline.json` 特殊名称，作为对比基准

### 数据格式

```json
{
  "version": "1",
  "queries": [
    {
      "id": "q001",
      "query": "Agent Skills到底是什么？",
      "expected_source": "notes/学习笔记/吴恩达的skill课程（一）.md",
      "expected_keywords": ["工具调用", "prompt", "agent"],
      "type": "single_hop",
      "difficulty": "easy"
    }
  ]
}
```

字段说明：
- `id`：唯一标识，格式 `q001`
- `query`：自然语言查询
- `expected_source`：期望命中的笔记 file_id（single_hop 为字符串，multi_hop 为数组）
- `expected_keywords`：期望答案应包含的关键词
- `type`：`single_hop`（单笔记可回答）或 `multi_hop`（需跨笔记综合）
- `difficulty`：`easy` / `medium` / `hard`

### 生成流程

1. Python 脚本遍历 vault 中所有笔记
2. 逐篇喂给 LLM，生成 2-3 个 single_hop 问答对
3. 随机组合 2-3 篇相关笔记，生成 multi_hop 问题
4. 输出到 `dataset.json`
5. 用户审核后提交到 git

---

## 二、kb eval 子命令

### 命令

```bash
kb eval                        # 运行全部评测
kb eval --subset easy          # 按难度筛选
kb eval --category 学习笔记    # 按分类筛选
kb eval --baseline             # 将本次结果设为基线
kb eval --compare baseline     # 与基线对比
```

### 评测流程

```
dataset.json
    │
    ▼
┌─────────────────────────────────────────────┐
│  for each query:                            │
│    1. 执行搜索 (search/semantic/hybrid)     │
│    2. 检索命中评分 (hit/rank)               │
│    3. 执行 RAG query (可选)                  │
│    4. LLM 答案质量评分                       │
│    5. 汇总每道题的分数                       │
└─────────────────────────────────────────────┘
    │
    ▼
eval/results/<timestamp>.json
    │
    ▼
终端摘要 + 可选的详细 JSON 报告
```

### 评分指标

| 阶段 | 指标 | 说明 | 计算方式 |
|------|------|------|----------|
| 检索 | `hit` | 期望来源是否出现在结果中 | 0/1 |
| 检索 | `rank` | 期望来源在结果中的排名 | 整数，未命中记 -1 |
| 检索 | `mrr` | Mean Reciprocal Rank | 1/rank 的平均值 |
| 答案 | `keyword_score` | 回答覆盖期望关键词的比例 | 命中数 / 总关键词数 |
| 答案 | `llm_judge` | LLM 裁判综合打分 | 1-5 分 |

### 结果格式

```json
{
  "timestamp": "2026-05-10T14:30:00",
  "config": {"search_mode": "hybrid", "top_k": 5},
  "summary": {
    "total": 20,
    "hit_rate": 0.85,
    "avg_rank": 1.8,
    "mrr": 0.72,
    "keyword_score": 0.78,
    "llm_judge_avg": 4.1,
    "overall": 0.815
  },
  "details": [
    {
      "id": "q001",
      "hit": true,
      "rank": 1,
      "keyword_score": 0.75,
      "llm_judge": 4,
      "llm_judge_reason": "回答了Agent Skills的核心定义，但缺少工具调用的具体示例"
    }
  ]
}
```

### 对比报告

`--compare baseline` 模式：
- 逐查询对比，标记退化的查询
- 汇总维度变化（hit_rate ±X, avg_rank ±X）
- 输出退化查询的详细信息

---

## 三、代码测试补齐

### 目标：覆盖率 74% → 80%+

| 优先级 | 模块 | 当前 | 目标 | 补齐内容 |
|--------|------|------|------|----------|
| P0 | `watcher.py` | 0% | 80% | 文件变更检测、防抖延迟、回调触发、停止/重启 |
| P0 | `llm.py` | 46% | 70% | OpenAI/Anthropic HTTP mock、异常路径、超时 |
| P1 | `rag.py` | 53% | 80% | 空上下文、超长截断、流式 chunk 增量验证 |
| P1 | `cli.py` | 60% | 75% | serve 参数、ask 参数校验、migrate 边界 |
| P2 | `routes.py` | 74% | 85% | 路径遍历边界、404 返回体、related 去重逻辑 |
| P2 | `indexer.py` | 65% | 80% | 外部源同步、解析失败跳过、删除检测 |
| P3 | `mcp_server.py` | 73% | 80% | kb_semantic_search 空 store、kb_rag_query 异常 |
| P3 | `server.py` | 56% | 70% | lifespan 行为、静态文件路径遍历 |

### eval 命令自身也需要测试

- `tests/test_eval.py`：评测命令生成的数据集解析、评分逻辑、结果序列化
- `tests/test_eval_cli.py`：CLI 参数解析、baseline 对比、子集过滤

### 测试不改动的部分

- `services.py` — 已 100%
- `config.py` — 已 100%
- `database.py` — 已 99%
- `storage.py` — 已 95%
- `vector.py` — 已 96%

---

## 四、实现阶段

### Phase 1: 评测数据生成
- 实现数据集生成脚本
- 生成初始 dataset.json
- 用户审核

### Phase 2: kb eval 子命令
- 创建 `src/kb/core/eval.py`（评测引擎）
- 创建 `src/kb/cli.py` 新增 `eval` 命令
- 实现检索评分 + LLM Judge
- 实现 --baseline / --compare
- 测试：`test_eval.py` + `test_eval_cli.py`

### Phase 3: 代码测试补齐
- 按 P0 → P3 优先级补测试
- 每次补齐一个模块后验证覆盖率
- 目标覆盖率 80%+

### Phase 4: 集成到 CI
- `kb eval --compare baseline` 作为 PR 质量门禁
- pytest 覆盖率检查

---

## 五、不改动的部分

- 现有 125 条测试逻辑不变
- 现有 API 接口不变
- Web 前端不变
- MCP server 工具接口不变
