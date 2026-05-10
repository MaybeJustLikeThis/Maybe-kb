# KB 评测系统

## 快速开始

```bash
kb eval                          # 运行全部评测
kb eval --subset easy            # 按难度筛选 (easy/medium/hard)
kb eval --category 学习笔记      # 按分类筛选
kb eval --baseline               # 将本次结果设为基线
kb eval --compare baseline       # 与基线对比
```

## 目录结构

- `dataset.json` — 评测查询集（版本控制）
- `results/` — 评测结果（不提交）
- `generate_dataset.py` — 从 vault 笔记自动生成评测数据

## 生成评测数据集

```bash
python eval/generate_dataset.py
```

脚本会遍历 vault 中所有笔记，用 LLM 生成查询对，输出到 `dataset.json`。
生成后请人工审核 `dataset.json`，确认无误后提交到 git。
