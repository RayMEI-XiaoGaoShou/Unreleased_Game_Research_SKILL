# Section 1: Public Intel and Product Framing

## Purpose

Build a structured public-information dossier for an unreleased game by fully utilizing the Agent's global web search capabilities.
Focus on product identity, development context, test timeline, and observable design direction.
This section is the factual backbone of the full report and must be heavily researched.

## Workflow

**Step 1: Global Intelligence Gathering**
The Agent must execute comprehensive web searches across global sources (gaming news, interviews, official announcements, financial reports, etc.) to gather facts about the studio, test timelines, and game features.

**Step 2: Structured Analysis Output**
Based on the gathered intelligence, the Agent must output the final findings strictly following the analysis framework below. **Crucial Rule:** To prevent LLM hallucinations, every claim in the findings must have a concrete, real-world source. If public information does not cover a specific bullet point in the template, explicitly state "无公开信息" (No public info available) or skip it rather than making things up.

## Required Outputs

This section must produce:

- `projects/<game_slug>/section_1_data.json` (Agent writes this; Python script validates and generates the following)
- `section_1_public_intel/findings.md`
- `section_1_public_intel/evidence_table.csv`
- `section_1_public_intel/timeline.csv`
- `section_1_public_intel/team_profile.csv`

## Fact Gate Contract

`scripts/run_section_1.py` enforces a hard validation gate before writing any output. The Agent **must** produce a `section_1_data.json` that satisfies all of the following, or the script will abort:

1. **`facts` array is required and non-empty.**
2. **Three hard-fact keys are mandatory:** `official_name`, `developer`, `publisher`. Each must have a non-empty `fact_value`, a `source_id`, and a `verification_status` of exactly one of: `official_confirmed`, `cross_checked`, `verified`.
3. **Unverifiable hard facts must be omitted or escalated.** Do NOT include hard-fact rows with unverified statuses — the validator will reject the entire file. Instead, note the gap in `source_notes.md` and leave the fact out of the JSON.
4. **Other (non-required) supplementary facts** may have `confidence_level: low` and will pass validation without verified status.

## Core Questions

Answer all of the following when evidence exists:

1. Who is making the game? (Company, specific studio/group)
2. What are the historical works of this studio?
3. Who is the producer/director? Are there public details about them?
4. Up to the latest test, how many closed beta tests have occurred?
5. What is the timeline from the first reveal to the different test phases?
6. What content was updated, optimized, or reworked in each test phase?
7. What are the game's characteristics based on public info?

## Research Modules & Analysis Framework

### Module A: 基础信息 (Basic Profile & Timeline)

Collect and verify:
- 游戏名称 (Official game name)
- 研发公司与具体工作室 (Developer & specific studio/group)
- 发行商 (Publisher)
- 工作室历史作品 (Historical titles by this studio)
- 核心制作人/主创信息 (Producer/Director details)
- 测试时间线 (Timeline from first reveal to all CBT phases)
- 各轮测试的迭代重点 (What changed/updated in each test phase)

### Module B: 游戏具体分析框架 (Game Characteristic Analysis)

This is the core analysis based on the provided framework. Do not hallucinate.

#### 1. 多维度评估产品
- **玩法 (Gameplay):** 
  - 创新性 (Innovations/breakthroughs)
  - 耐玩性 (Durability for tens of hours)
  - 契合度 (Match between gameplay and theme/IP)
- **视觉美术 (Visual Art):** 
  - 辨识度 (First impression, stylistic distinction)
  - 美术质量 (Pure production quality/fidelity)
  - 接受程度 (Audience acceptability vs. weirdness)
- **题材 (Theme/Setting):** 
  - 新颖度 (Novelty)
  - 流行度 (Popularity and TAM vs. competition)
- **交互设计 (Interaction Design):** 
  - 操作方式 (Control mode)
  - 信息呈现 (Information UI/UX)

#### 2. 核心乐趣提炼与品类定位
- **核心乐趣提炼:** 提炼该游戏最吸引人的 3-4 个核心乐趣点。
- **真实品类定位:** 基于核心乐趣点反推该产品的真实所属品类（而非表面的商店分类标签）。
- **混合品类解构:** 识别该产品的“混合品类”构成及各品类元素的权重占比（例如：开放世界探索40% × 二次元角色收集30%...）。

#### 3. 品类基准比较
- **品类通用特性归纳:** 归纳该产品所属品类的通用优势与通用痛点。
- **品类基因四维分析:**
  - **继承 (Inherit):** 保留了品类的哪些核心体验？
  - **强化 (Strengthen):** 在哪些方面做到了品类最佳或显著超越？手段是什么？
  - **创造 (Create):** 引入了哪些前所未有的新元素？
  - **解决 (Solve):** 解决了品类长期存在的哪些痛点？

#### 4. 品类趋势与生态位判断
- **品类演化脉络:** 梳理该品类的演化走向。
- **品类生命周期定位:** 探索期 / 成长期 / 成熟期 / 变革期。
- **产品生态位判断:** 是“正统继承者”还是“变革挑战者”？与其团队资源禀赋是否匹配？

## Required Tables

### `timeline.csv`
Columns: `milestone_id`, `label`, `date`, `source_id`, `content_type`, `summary`, `change_vs_previous`, `confidence_level`

### `team_profile.csv`
Columns: `entity_name`, `entity_type`, `role`, `related_prior_titles`, `genre_relevance`, `evidence_source_id`, `confidence_level`, `notes`

## Findings Structure

`findings.md` must output in this exact Markdown structure (all in Chinese):

- `## 范围与核心结论`
- `## 1. 基础信息与开发脉络`
  - 研发背景与团队
  - 测试节点与历次迭代
- `## 2. 多维度评估产品`
- `## 3. 核心乐趣提炼与品类定位`
- `## 4. 品类基准比较`
- `## 5. 品类趋势与生态位判断`
- `## 置信度与信息局限`

## Bias Control & Anti-Hallucination

- **NO HALLUCINATION:** If you cannot find info for a bullet point, explicitly write `根据目前公开信息，暂无相关报道` (Based on public info, no relevant reports available).
- Do not convert promotional language into neutral fact.
- Do not invent internal team structure.
