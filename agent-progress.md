# Agent Progress Log

> This file is the cross-session memory for the long-running agent.
> Each session MUST read this file at startup and append a summary at the end.
> DO NOT delete or rewrite previous entries — only APPEND.

---

## Session 0 — Initial Setup (2026-02-25)

**What was done:**
- Project scaffolding created: src/, scripts/, configs/, data/, openspec/
- openspec/ contains requirements.md, design.md, tasks.md
- pyproject.toml and requirements.txt configured
- configs/lora_config.yaml and eval_config.yaml created
- src/inspection_lora/ core modules: data_utils.py, metrics_parser.py, prompt_builder.py
- data/templates/ partial: cpu_templates.py, memory_templates.py, __init__.py
- scripts/ created: generate_data.py, filter_data.py, split_data.py, create_dummy_data.py
- Long-running agent harness files created: feature_list.json, agent-progress.md, init.sh, AGENT_GUIDE.md

**Known issues:**
- cpu_templates.py line 176: `rnchoice` should be `rng.choice` (typo)
- memory_templates.py line 148: `rng.unifor   avail = ...` (truncated line, syntax error)
- disk_templates.py, network_templates.py, composite_templates.py: NOT YET CREATED (but imported in __init__.py)
- gen_templates.py: abandoned/incomplete, can be deleted
- Memory template analysis text is in English, should be Chinese to match CPU templates

**Current state:**
- Phase 1: Partially done (structure exists, configs exist, dummy data script exists, but not validated end-to-end)
- Phase 2: In progress (core modules done, CPU+memory templates done with bugs, disk/network/composite templates missing)
- Phase 3: Not started
- Phase 4: Not started

**Next session should:**
1. Fix syntax errors in cpu_templates.py and memory_templates.py
2. Create disk_templates.py, network_templates.py, composite_templates.py
3. Run `python scripts/generate_data.py --count 10 --seed 42` to validate the pipeline
4. Update feature_list.json as features pass

---

## Session 1 — W3/W4/W5 Complete: Templates + Data Pipeline (2026-02-26)

**What was done:**
- Created disk_templates.py (5 generators: normal, space_low, io_saturation, inode_exhaustion, write_latency)
- Created network_templates.py (4 generators: normal, traffic_spike, asymmetric, bandwidth_saturation)
- Created composite_templates.py (6 generators: cpu_io_correlation, memory_swap_cascade, cpu_memory_load, disk_network_backup, full_stack_degradation, load_cpu_divergence)
- Fixed syntax errors in disk/composite templates (truncated variable names, missing parens)
- Verified all 26 generators produce valid ScenarioConfig
- Ran full data pipeline: generate 2200 → filter 2200/2200 → split 1760/220/220
- Updated feature_list.json: 16 features marked PASS

**Features completed:**
- F-1.1: 项目目录结构完整
- F-1.2: pyproject.toml 和 requirements.txt 配置正确
- F-1.5: LoRA 训练配置文件格式正确
- F-2.1: metrics_parser.py 功能完整
- F-2.2: prompt_builder.py 功能完整
- F-2.3.1 ~ F-2.3.5: 全部 5 个模板引擎完整
- F-2.4: generate_data.py 正常运行
- F-2.5: filter_data.py 正常运行
- F-2.6: split_data.py 正常运行
- F-2.7: 端到端 2200 条数据产出
- F-2.8: data_utils.py 功能完整
- F-2.9: 模板注册表正确

**Known issues:**
- F-1.3 (venv), F-1.4 (model download), F-1.6 (dummy training) 未验证（需要实际运行训练）
- gen_templates.py 仍存在，可删除
- Session 0 提到的 memory_templates 英文分析文本问题未确认是否已修复

**Next session should:**
1. Verify F-1.3, F-1.4, F-1.6 (venv/model/dummy training)
2. Start Phase 3: F-3.1 MLX LoRA training with real data
3. Delete abandoned gen_templates.py
