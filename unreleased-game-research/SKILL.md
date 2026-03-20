---
name: unreleased-game-research
description: Research unreleased games through public information, official video comment analysis, homepage player review analysis, and creator review video interpretation. Use when a coding agent needs to investigate pre-launch games, map development milestones, compare player sentiment across test phases, assess creator feedback reliability, and assemble a structured evidence-based report with markdown artifacts and optional PDF export.
---

# Unreleased Game Research

Build an evidence-based research package for an unreleased game.
Treat this skill as an orchestration layer, not as a single giant prompt.
Prefer stable artifacts over inline reasoning.

## Core Mission

Produce a structured dossier that helps a strategy analyst answer:

- what this game actually is
- who is making it and what that implies
- how it changed over milestones
- how official audience reaction evolved
- what likely test players are saying
- what credible creators think about the latest playable build
- what remains uncertain

## Operating Principles

- Separate facts, opinions, and inference.
- Preserve evidence provenance.
- Prefer partial but auditable output over polished but weakly grounded claims.
- Keep markdown artifacts as the primary deliverable.
- Treat PDF as a packaging layer, not the source of truth.

## Default Workflow

1. Initialize a project folder and artifact contract.
2. Build the source registry and milestone map.
3. Run Section 1 first to establish product framing.
4. Run Sections 2-4 when inputs are ready.
5. Normalize text, sentiment, topic labels, and evidence references.
6. Synthesize across sections without flattening disagreement.
7. Export a final markdown report and optional PDF.

Read `references/research_workflow.md` before running a full end-to-end study.

## Project Initialization

Create a project under `projects/<game_slug>/`.

Minimum required files and folders:

- `project.yaml`
- `sources/source_registry.csv`
- `sources/source_notes.md`
- `section_1_public_intel/`
- `section_2_official_video_comments/`
- `section_3_homepage_reviews/`
- `section_4_creator_reviews/`
- `synthesis/`
- `exports/`

If a required section cannot run, create the folder anyway and record the reason in `findings.md`.

Use `scripts/init_project.py` to create this structure.

## Required References

Read these references before running the corresponding section:

- `references/report_schema.md`
- `references/source_reliability.md`
- `references/bias_control.md`
- `references/section_1_public_intel.md`
- `references/section_2_official_video_comments.md`
- `references/section_3_homepage_reviews.md`
- `references/section_4_creator_reviews.md`
- `references/credentials_guide.md`

Use `references/visualization_guidelines.md` when generating charts or report visuals.

## Operating Modes

### `safe_mode`

Use when compliance risk, scraping fragility, or environment limits are high.

Behavior:

- prioritize public and official sources
- prefer YouTube API if available
- allow manual URL input or manual source dumps
- stop at markdown if PDF or capture automation is unstable

### `deep_mode`

Use when the environment supports richer automation and the operator accepts higher fragility.

Behavior:

- enable best-effort page capture for supported platforms
- allow transcription and richer visual outputs
- still preserve the same artifact contract
- never hide capture failures or partial coverage

## Section Order

### Section 1

Run first unless the user explicitly wants only one later section.
This section defines the game's frame and milestone map.

**Agent Action Required:**
The AI Agent must execute **Global Intelligence Gathering** by heavily utilizing web search, explore/librarian agents, and public databases to gather exhaustive facts about the game, the developer, and its test history.

Section 1 now has a **fact-gate**. The AI Agent must not write freeform company facts directly into final findings without source verification. Before calling `scripts/run_section_1.py`, prepare a structured `facts` array inside `section_1_data.json`.

Required hard-fact keys:

- `official_name`
- `developer`
- `publisher`

For hard facts, each row must contain:

- `fact_key`
- `fact_value`
- `source_id`
- `source_type`
- `verification_status`
- `confidence_level`

Accepted `verification_status` values for hard facts:

- `official_confirmed`
- `cross_checked`
- `verified`

**Important:** If a hard fact cannot be verified, do NOT pass it with an unverified status — `run_section_1.py` will reject it. Instead, either (a) omit it and note it in `source_notes.md` as "publicly unconfirmed", or (b) use a weaker `source_type` and mark `confidence_level: low` only for non-required supplementary facts.

**Crucial Analysis Framework:**
The Agent must structure the `findings` inside `section_1_data.json` exactly according to the `references/section_1_public_intel.md` framework:
1. **多维度评估产品** (玩法、视觉美术、题材、交互设计)
2. **核心乐趣提炼与品类定位**
3. **品类基准比较** (继承、强化、创造、解决)
4. **品类趋势与生态位判断**

**Zero Hallucination Rule:** If the web search does not provide enough info for a specific dimension (e.g., interaction design), explicitly write "根据目前公开信息，暂无相关报道" instead of making up features.

### Section 2

Run after official video links are known.
Best when at least two milestones can be compared.

Before any Section 2 collection starts, perform a credential preflight. If YouTube API key and/or Bilibili cookie are missing, read `references/credentials_guide.md`, give a short plain-language Chinese summary, and ask the user to paste credentials in one fixed template instead of explaining CLI flags. Prefer this reply format:

```text
请直接复制下面模板并填写后发我：

YouTube API Key: <粘贴这里，没有就写 None>
Bilibili SESSDATA: <粘贴这里，没有就写 None>
Bilibili bili_jct: <粘贴这里，没有就写 None>
Bilibili DedeUserID: <粘贴这里，没有就写 None>
Bilibili buvid3: <粘贴这里，没有就写 None>
Bilibili buvid4: <可选，没有就写 None>
```

Do not block Section 2 unless all requested platforms are missing credentials. If the user provides only one platform's credential, proceed with that platform and explicitly mark partial coverage. Only show the full step-by-step credential guide if the user says they do not know how to get the values.

### Section 3

Run when public review pages or reservation comments exist.
Use especially when test-player long reviews are visible.

Before any Section 3 collection starts, tell the user in plain Chinese what input is needed and why:

- `page-url`: the public TapTap or Bilibili game / reservation page URL used for direct capture
- `input-file`: a CSV / JSON export if the user already manually exported reviews
- `biligame-request-bundle-file`: only needed for direct Bilibili page capture, because Bilibili requires a copied DevTools request bundle

If the user is non-technical, do not say "just pass CLI flags". Instead say what each input is for, then ask for one of these three paths:

1. give a TapTap page URL
2. give a Bilibili page URL plus copied request bundle file
3. give an exported review file

If none is available, mark Section 3 as blocked and continue the rest of the workflow.

After the Python capture finishes, do **not** treat the script-generated topic label as the final analysis. For Section 3, the script outputs are only the evidence base.

The Agent must then do a second-pass deep analysis on top of:

- `section_3_homepage_reviews/review_sample.csv`
- `section_3_homepage_reviews/review_registry.csv`
- `section_3_homepage_reviews/evidence_table.csv`

Agent requirements for Section 3 deep analysis:

1. Read the full long-review text, not just the summary row.
2. Split a single long review into multiple meaning units if it covers multiple topics.
3. Re-organize findings into generic game-analysis dimensions such as:
   - `题材与定位`
   - `美术与视听`
   - `交互体验与战斗`
   - `核心玩法与内容循环`
   - `商业化与成长压力`
   - `技术表现与优化`
   - `市场讨论与竞品比较`
4. For each dimension, summarize:
   - positive points
   - negative points / concerns
   - representative quotes from the raw long reviews
5. Preserve disagreement when different long reviews point in different directions.
6. Do not simply dump raw quote excerpts as the final narrative. The final `findings.md` should be a structured analyst summary backed by quotes.

### Section 4

Run last by default.
Use only for the latest meaningful test phase.
Prioritize quality of selected videos over quantity.

Before any Section 4 collection starts, explain these inputs in plain Chinese:

- `candidates-file`: shortlisted creator videos to analyze
- `transcripts-file`: transcript content for those selected videos
- `transcript-video-id`: only needed when the transcript is a single SRT file without embedded video id

The preferred automatic path is now:

1. shortlist videos via `candidates-file`
2. let the Python runner download native subtitles or audio automatically
3. if native subtitles exist, use them directly
4. if only audio exists, run the configured STT backend to generate transcript segments

**STT Provider Options:**

- `auto`: Try local Whisper first, fall back to manual template if unavailable
- `local-whisper`: Use local Whisper CLI (requires `pip install openai-whisper`)
- `volcengine`: Use Volcano Engine (火山引擎) cloud ASR (~0.8 CNY/hour, best for Chinese content)
- `manual-template`: Generate empty CSV template for manual transcription

**Volcano Engine Setup:**

1. Create account at https://console.volcengine.com/speech/app
2. Create an application and get API token
3. Store token in one of:
   - `--volcengine-token` command line argument
   - `VOLCENGINE_ASR_TOKEN` environment variable
   - `.volcengine_token` file in project root

If the user does not have transcripts but is okay with automatic generation, do **not** mark Section 4 as blocked immediately. Prefer the automatic route first.

If the user does not already have a shortlist, tell them they can first generate one with `scripts/search_section_4_candidates.py --game-name "<游戏名>"`.

After the Python transcript / claim pipeline finishes, the Agent must treat those files as structured evidence, not as the final report text.

The Agent must perform deep analysis by reading the generated transcript text files:

- `section_4_creator_reviews/generated_transcripts/<video_id>_volcengine.txt` — full verbatim transcript per video

Agent requirements for Section 4 deep analysis:

1. Read the actual transcript excerpts and claim rows.
2. Produce per-video diagnosis with:
   - creator stance
   - core praise
   - core concerns
   - strongest supporting quotes
3. Then produce cross-video synthesis by dimension, not just by video.
4. Re-organize creator evidence into the same generic dimensions used by the final report.
5. Explicitly separate:
   - creator interpretation
   - creator firsthand observation
   - analyst inference

## Interactive Intake Flow

When the user says something like "分析《xxx》游戏" or asks to run this skill end-to-end, you (the AI Agent) must act as the **Frontend Coordinator**.

### ⛔ HARD RULES — READ BEFORE DOING ANYTHING

> **RULE 1 — NO EARLY EXECUTION:**
> You MUST NOT call any Python script, run any section runner, or invoke any backend tool until **Turn 5 is fully complete** and the user has explicitly confirmed all inputs. Collecting Section 2 inputs in Turn 2 does NOT give you permission to start Section 2. Collecting Section 3 inputs in Turn 3 does NOT give you permission to start Section 3. The one and only moment you may launch any execution is the end of Turn 5.

> **RULE 2 — ONE LAUNCH, ALL AT ONCE:**
> Sections 2, 3, and 4 must launch **simultaneously in a single parallel call** at the end of Turn 5. Never launch them one-by-one as their inputs arrive. The purpose of Turn 1–5 is purely input collection. Execution begins only after all inputs are gathered.

> **RULE 3 — SECTION 4 VIDEO CONFIRMATION IS MANDATORY:**
> If the user asks you to search for Section 4 candidate videos, you MUST run `scripts/search_section_4_candidates.py`, then **show the results to the user and wait for their explicit video selection confirmation**. You MUST NOT proceed to Section 4 execution until the user has replied with which videos to include.

> **RULE 4 — VOLCENGINE API KEY IS REQUIRED BEFORE TRANSCRIPTION:**
> You MUST NOT start any Section 4 transcription without a Volcano Engine API Key explicitly provided by the user. If the user has not provided one, ask again before proceeding. Do not use any default, placeholder, or auto fallback provider for Section 4 transcription.

---

You MUST follow this exact **Multi-turn Progressive Intake Flow** in Chinese:

### Turn 1: Initialization & Section 2 (Official Video)
1. **Confirm Game Name**: "好的，我将为您深入分析《xxx》这款未上线游戏。"
2. **Explain 4 Sections & Flow**: Briefly explain the 4 dimensions (Public Intel, Official Video Comments, Player Reviews, Creator Reviews) and tell the user: "我会先用 Turn 1~5 与您逐步确认 Section 2~4 所需的全部信息，信息收集完毕后，再**一次性并行启动** Section 2、3、4 的分析，最后汇总生成综合报告。"
3. **Start Section 1 Background Task**: Tell the user you will start searching for Public Intel globally right now. **(Agent MUST start using web search immediately in parallel to gather developer info, test timelines, and core gameplay features — this runs in background throughout Turn 1–5.)**
4. **Ask for Section 2 Inputs**: Ask the user: "首先是【官方视频评论分析】。请问您想分析哪个平台的官方视频？(1) YouTube (2) B站 (3) 都有 (4) 跳过此项"
*(Wait for user response — DO NOT start any section execution)*

### Turn 2: Section 2 Credentials Guide
1. **Provide Conditional Guide**: 
   - If the user chose YouTube: Read `references/credentials_guide.md` and provide the step-by-step guide for getting a YouTube API Key.
   - If the user chose B站 (Bilibili): Read `references/credentials_guide.md` and provide the step-by-step guide for extracting B站 Cookies.
   - If both: Provide both guides.
   - If skip: Proceed to Turn 3 immediately.
2. **Provide the Copy-Paste Template**: After the guide, provide the exact credential template block for the user to fill out, along with asking for the video URLs.
*(Wait for user to paste credentials and URLs — DO NOT start any section execution)*

### Turn 3: Section 3 (Homepage Reviews)
1. **Acknowledge**: "收到官方视频信息！接下来是【玩家主页/预约评价分析】。"
2. **Ask for Section 3 Inputs**: "请问您想抓取哪个平台的玩家评价？(1) TapTap (2) B站游戏中心 (3) 跳过此项"
*(Wait for user response — DO NOT start any section execution)*

### Turn 4: Section 3 Guide & Section 4 (Creator Reviews)
1. **Conditional Section 3 Guide**:
   - If TapTap: Just ask for the TapTap game page URL.
   - If B站: Warn the user that B站 game pages have strict anti-bot measures. Read `references/section_3_bilibili_semi_auto_guide.md` and provide the step-by-step tutorial on how to right-click in DevTools and "Copy as cURL (bash)", and ask them to paste it.
2. **Ask for Section 4 Inputs & ASR Setup**: 
   - Explain to the user: "最后是【创作者评测分析】。这部分我们需要将视频转为文字以便深度分析。我们默认使用**火山引擎 ASR**，原因如下：\n  1. **配置极其简单**：纯 API 调用，不需要本地配置复杂的 Python 或 GPU 环境。\n  2. **新用户白嫖额度**：新用户开通即送 20 小时免费转录额度（即使超额，价格也仅需约 2.3元/小时）。\n  3. **精准度高**：内置标点与智能断句，非常适合评测分析。"
   - Provide the setup guide:
     "**【火山引擎 API Key 获取指南】**\n     1. 登录 [火山引擎控制台](https://console.volcengine.com/)\n     2. 搜索并开通 **语音技术** -> **大模型录音文件识别**（注意是录音文件识别，非流式）\n     3. 在控制台左侧导航栏找到"应用管理"或"凭证管理"，生成你的 `API Key`（注意：不需要 AppID，只需要 API Key 即可）。"
   - Ask for their inputs: "请问您是否已经有想要分析的 UP主/主播视频清单？如果没有，我可以帮您自动搜索候选名单。(1) 我有清单 (2) 请帮我搜索候选 (3) 跳过此项。请将您的选择，以及火山引擎 API Key 一并发送给我。"
*(Wait for user response — DO NOT start any section execution)*

### Turn 5: Section 4 Video Confirmation & Parallel Launch

#### Step A — Resolve Section 4 Video List
- **If user has their own list**: Ask them to paste the video URLs/IDs or CSV file path. Wait for them to provide it.
- **If user wants you to search**: Run `scripts/search_section_4_candidates.py` in background. Once results are ready, **show the top candidates to the user and ask: "以上是我找到的候选视频，请告诉我您希望保留哪几个（例如回复序号 1、3、5），确认后我将开始正式执行分析。"** ⛔ **DO NOT proceed until the user has replied with their confirmed video selection.**
- **If user skips Section 4**: Note it and proceed without Section 4.

#### Step B — Verify Volcano Engine API Key
- ⛔ **If Section 4 is not skipped and no Volcano Engine API Key has been provided**, explicitly ask: "请提供您的火山引擎 API Key，没有这个 Key 我无法进行视频转录，Section 4 将无法执行。" **DO NOT proceed to Step C until the key is explicitly provided.**

#### Step C — Parallel Launch (THE ONE AND ONLY LAUNCH MOMENT)
Once ALL of the following are confirmed:
- ✅ Section 2 credentials + video URLs (or skipped)
- ✅ Section 3 page URL / cURL bundle (or skipped)
- ✅ Section 4 confirmed video list + Volcano Engine API Key (or skipped)

**Only now**, execute the master runner `scripts/run_research.py` in headless mode using the `--parallel` flag, passing all collected arguments simultaneously. Tell the user: "所有信息已收齐，现在开始并行启动 Section 2、3、4 的数据采集与分析！"

#### Step D — Finalize Section 1
While Sections 2–4 run, ensure your background web search for Section 1 is complete. Write the structured intelligence to `projects/<game_slug>/section_1_data.json`.
- The JSON MUST include a `facts` array for hard facts (with source tracking).
- The JSON MUST include a `findings` string structured exactly like the **Module B: 游戏具体分析框架** (including 基础信息, 多维度评估产品, 核心乐趣与品类定位, 品类基准比较, 品类趋势).
- **Do not send unverified claims**. If info is missing, write "根据目前公开信息，暂无相关报道" in the `findings`.

Once all sections complete, run `scripts/assemble_report.py` then perform Agent-level synthesis rewrite of the executive summary and final report.

## Multi-Agent Structure

Use a thin multi-agent workflow.

Recommended roles:

- `Coordinator`: initializes project, tracks progress, enforces artifact schema
- `Section Agent 1`: public intel
- `Section Agent 2`: official video comments
- `Section Agent 3`: homepage reviews
- `Section Agent 4`: creator reviews
- `Normalization Agent`: cleaning, translation, sentiment pre-processing, topic mapping
- `Editor-in-Chief`: synthesis only, reads section outputs and writes final report

Agents must hand off through files, not memory.
Each section must write artifacts before synthesis begins.

## Parallel Execution Flow

Preferred execution chain:

1. `Coordinator` collects missing user inputs through the intake flow above
2. launch `Section Agent 1` through `Section Agent 4` in parallel whenever their required inputs are available
3. if one section is blocked by missing inputs, do not block the other sections
4. every section writes its own artifacts first
5. only after all runnable sections finish, launch `Editor-in-Chief` for synthesis

Important concurrency rule:

- if multiple sections may update `sources/source_registry.csv`, serialize or lock those writes so that parallel collection does not lose rows
- parallelism is desirable, but data loss is not acceptable

## Source Handling

Every source must be added to `sources/source_registry.csv`.

For every source:

- assign `source_id`
- record `source_type`
- record `official_status`
- record `reliability_score`
- record `bias_risk`
- record `capture_status`

Never cite material in findings if it is missing from the source registry.

## Evidence Rules

Every major conclusion in any `findings.md` must map to at least one `source_id` or `evidence_id`.

Use these evidence classes:

- fact
- player_opinion
- creator_opinion
- analyst_inference

Never present `analyst_inference` as direct evidence.

## Bias Rules

Apply `references/bias_control.md` at all times.

Minimum requirements:

- mark likely promotional framing
- separate firsthand experience from expectation
- separate creator interpretation from confirmed observation
- preserve disagreement across sections
- lower confidence when evidence is narrow, repetitive, or translation-sensitive

## Section Output Contract

Every section must produce:

- `findings.md`
- `evidence_table.csv`
- section-specific structured files defined in the section reference
- confidence and limitations note

If capture fails:

- record the failure
- describe what was attempted
- state how this weakens confidence
- continue with the best supported partial analysis

## Synthesis Rules

The synthesis layer must produce:

- `synthesis/executive_summary.md`
- `synthesis/final_report.md`

The synthesis must include:

- a Chinese executive summary
- a dimension-based summary organized around generic game-analysis dimensions such as:
  - `题材与定位`
  - `美术与视听`
  - `交互体验与战斗`
  - `核心玩法与内容循环`
  - `商业化与成长压力`
  - `技术表现与优化`
  - `市场讨论与竞品比较`
- the full detailed outputs from Section 1 through Section 4 after the summary
- confidence level and unresolved questions

### Agent-Driven Deep Analysis (Section 3, Section 4 & Synthesis)

While the Python scripts are responsible for raw data extraction (fetching comments, transcripts, building baseline CSVs), **deep dimensional analysis is the responsibility of the Agent**. 

The fundamental logic of this skill is a funnel of increasing analytical depth:
- Section 2: Broad audience sentiment (High volume, macro trends)
- Section 3: Core tester reviews (Medium volume, detailed text)
- Section 4: Professional creator reviews (Low volume, extreme depth per sample)

When generating the final report or rewriting section findings:
1. Do not rely solely on the Python script's single-label extraction.
2. Read the raw text from `review_sample.csv` (for Section 3) and `transcript_segments.csv` / `claim_evidence_map.csv` (for Section 4), as well as the detailed AI findings from Section 1.
3. Use your own built-in LLM capabilities to perform a multi-dimensional breakdown. For example, if a TapTap long review covers both `美术` and `战斗`, explicitly split and analyze those points into the respective dimension buckets in the final output.
4. Structure the output clearly with positive and negative points per dimension, supported by exact quotes from the raw data.
5. Treat the Python outputs as **contracts and evidence tables**, not as the final narrative standard.
6. The final polished report text should be Agent-authored, evidence-backed, and significantly more structured than the raw script summaries.

**Specific Requirement for Synthesis (Executive Summary & Final Report):**
The `scripts/assemble_report.py` will generate a basic scaffolding for the synthesis files. However, the Agent **MUST NOT** just leave the script-generated files as the final output. 
The Agent must:
1. Read the script-generated scaffolding in `synthesis/executive_summary.md` and `synthesis/final_report.md`.
2. Rewrite the "总体判断" (Overall Judgment) and "维度级总结" (Dimensional Summary) using its own deep understanding of the 4 sections.
3. Ensure the Executive Summary reads like a cohesive analyst memo, not a mechanical list of bullet points. Identify where Section 1's intended gameplay loop conflicts with Section 3's player feedback, or where Section 4's creator reviews highlight deep systemic issues.
4. Keep the structure defined by the script, but entirely replace the generated content under each section heading with the Agent's own high-quality synthesized analysis.

**Specific Requirement for Section 4 Findings:**
Because Section 4 deals with a small number of professional/deep reviews, the Agent MUST output the following exact structure:
1. **多维度综合共识 (Multi-dimensional Synthesis):** Similar to Section 3, summarize the collective creator viewpoints grouped by universal game dimensions (e.g., 美术与视听, 交互体验与战斗, 商业化). Under each dimension, list the synthesized positive points and negative/concern points.
2. **逐视频深度诊断 (Per-Video Deep Dive):** For each selected creator video, provide a dedicated summary that includes:
   - Creator's overall stance/conclusion
   - Positive points identified by this specific creator
   - Negative points / concerns raised by this creator
   - **MUST include direct quotes** from the creator's transcript to back up these points.

This means the architecture is intentionally balanced:

- **Python layer**: capture, normalize, dedupe, basic tagging, structured evidence export
- **Agent layer**: deep reading, dimensional synthesis, contradiction handling, analyst-style writing

Do not hardcode game-specific dimensions like `剧情与侦探感` into the universal final report template. Those can appear inside a specific game's section findings if evidence supports them, but the top-level report skeleton must stay genre-agnostic.

Do not flatten contradictions.
If Section 2 is optimistic and Section 3 is cautious, preserve that difference.
If Section 4 explains but does not confirm a concern, write that clearly.

## Visualization Rules

Use visuals only when they clarify evidence.

Recommended visuals:

- milestone timeline
- sentiment distribution by milestone
- topic coverage by milestone
- positive vs negative topic concentration
- creator consensus vs disagreement map

Do not create decorative charts with little analytical value.

## Export Rules

Primary deliverable:

- markdown artifact set

Optional deliverable:

- PDF in `exports/final_report.pdf`

If PDF generation fails:

- deliver markdown
- preserve chart assets
- record export failure without blocking the research output

## Fallback Rules

Use fallback behavior when:

- APIs are unavailable
- page structures change
- comments are inaccessible
- transcripts are low quality
- translations are ambiguous

Fallbacks may include:

- manual URL lists
- manual source copy ingestion
- smaller samples with explicit caveats
- markdown-only delivery

## Reporting Style

Write like a strategy analyst, not a marketer.

Use:

- concise claims
- visible evidence grounding
- explicit uncertainty
- cross-source comparison
- topic-level clarity

Avoid:

- hype language
- inflated certainty
- generic game-media praise
- smooth summaries that erase tension in the evidence

## Forbidden Moves

- Do not treat official messaging as neutral proof of quality.
- Do not treat repeated news rewrites as multiple confirmations.
- Do not treat one comment section as market consensus.
- Do not treat creator polish as evidence rigor.
- Do not hide partial capture or failed extraction.
- Do not invent internal team structure or undisclosed development details.
- Do not collapse all four sections into a single undifferentiated sentiment score.

---

## Quick Start

### One-Time Setup

1. Install Python 3.11+ (no external dependencies required)
2. Clone or copy this skill to your workspace

### Run a Complete Study

```bash
# Step 1: Initialize project
python scripts/run_research.py --init --game-name "City of Silver" --game-slug cityofsilver

# Step 2: Run Section 1 (AI-driven web search)
# Follow references/section_1_public_intel.md for structured research

# Step 3: Run Section 2 with credentials
python scripts/run_research.py \
  --project-dir ./projects/cityofsilver \
  --section 2 \
  --youtube-api-key YOUR_KEY \
  --bilibili-cookie-file ./credentials/bilibili.json

# Step 4: Run Section 3 (TapTap reviews)
python scripts/run_research.py \
  --project-dir ./projects/cityofsilver \
  --section 3 \
  --page-url "https://www.taptap.cn/app/12345"

# Step 5: Run Section 4 (Creator reviews — auto transcribe via Volcano Engine)
python scripts/run_research.py \
  --project-dir ./projects/cityofsilver \
  --section 4 \
  --candidates-file ./imports/creators.csv \
  --volcengine-api-key YOUR_VOLCENGINE_API_KEY

# Alternatively, if you already have manual transcripts:
# python scripts/run_research.py \
#   --project-dir ./projects/cityofsilver \
#   --section 4 \
#   --candidates-file ./imports/creators.csv \
#   --transcripts-file ./imports/transcripts.csv

# Step 6: Synthesize final report
python scripts/run_research.py \
  --project-dir ./projects/cityofsilver \
  --synthesize
```

### Quick Commands

```bash
# List all sections and what they do
python scripts/run_research.py --list-sections

# Check what sections are ready to run
python scripts/run_research.py --project-dir ./projects/cityofsilver --check-readiness

# Validate all required artifacts exist
python scripts/run_research.py --project-dir ./projects/cityofsilver --validate-contract

# Run everything from Section 3 onwards
python scripts/run_research.py --project-dir ./projects/cityofsilver --from-section 3

# Dry run (see what would execute without running)
python scripts/run_research.py --project-dir ./projects/cityofsilver --from-section 2 --dry-run
```

### Individual Section Runners

Each section can also be run independently:

```bash
# Section 2: Official video comments
python scripts/run_section_2.py \
  --project-dir ./projects/cityofsilver \
  --manifest ./imports/videos.csv

# Section 3: Homepage reviews
python scripts/run_section_3.py \
  --project-dir ./projects/cityofsilver \
  --page-url "https://www.taptap.cn/app/12345"

# Section 4: Creator reviews
python scripts/run_section_4.py \
  --project-dir ./projects/cityofsilver \
  --candidates-file ./imports/creators.csv \
  --transcripts-file ./imports/transcripts.csv

# Synthesis only
python scripts/assemble_report.py ./projects/cityofsilver
```

### Resume Capabilities

All section runners support resume:

```bash
# Resume Section 2 from sentiment analysis step
python scripts/run_section_2.py \
  --project-dir ./projects/cityofsilver \
  --from-step sentiment \
  --skip-collect

# Resume Section 3 from annotation step
python scripts/run_section_3.py \
  --project-dir ./projects/cityofsilver \
  --from-step annotate

# Check what steps are available
python scripts/run_section_2.py --project-dir ./projects/cityofsilver --list-steps

# Check section readiness
python scripts/run_section_2.py --project-dir ./projects/cityofsilver --check-readiness
```

---

## Credential Management

### For Non-Technical Users

The master runner will prompt for credentials if missing. Provide them in this format:

```
YouTube API Key: AIzaSyB...
Bilibili SESSDATA: abc123...
Bilibili bili_jct: def456...
Bilibili DedeUserID: 12345678
Bilibili buvid3: xyz789...
```

### Environment Variables

Set these for automatic credential detection:

```bash
export YOUTUBE_API_KEY="your_key_here"
export BILIBILI_SESSDATA="your_sessdata"
export BILIBILI_BILI_JCT="your_bili_jct"
export BILIBILI_DEDEUSERID="your_userid"
export BILIBILI_BUVID3="your_buvid3"
```

### Credential Files

For Bilibili, create a JSON file:

```json
{
  "SESSDATA": "your_sessdata",
  "bili_jct": "your_bili_jct",
  "DedeUserID": "your_userid",
  "buvid3": "your_buvid3"
}
```

See `references/credentials_guide.md` for step-by-step instructions.

---

## Input Manifests

### Video Manifest (Section 2)

CSV format for batch video collection:

```csv
video_ref,milestone_id,platform,notes
Nq4bY86b61E,alpha1,youtube,Alpha test announcement
BV1vicDz9EE3,alpha1,bilibili,Chinese alpha preview
```

### Creator Candidates (Section 4)

CSV format for importing creator videos:

```csv
video_id,platform,url,title,creator_name,publish_date
BV1abc123,bilibili,https://bilibili.com/video/BV1abc123,Review Title,CreatorName,2024-01-15
```

### Transcript Import (Section 4)

Supports CSV, JSON, JSONL, or SRT formats. CSV columns:

```csv
segment_id,video_id,timestamp_start,timestamp_end,quote_original
seg_001,BV1abc123,00:01:30,00:01:45,Original quote text here
```

---

## Output Structure

After running all sections:

```
projects/cityofsilver/
├── project.yaml                    # Project metadata
├── sources/
│   ├── source_registry.csv         # All source provenance
│   └── source_notes.md             # Analyst source notes
├── section_1_public_intel/
│   ├── findings.md                 # AI-researched public intel
│   ├── timeline.csv                # Milestone timeline
│   └── team_profile.csv            # Studio/team analysis
├── section_2_official_video_comments/
│   ├── findings.md                 # Video comment analysis
│   ├── evidence_table.csv          # Structured evidence
│   ├── sentiment_summary.csv       # Sentiment distribution
│   ├── topic_summary.csv           # Topic mentions
│   └── video_registry.csv          # Tracked videos
├── section_3_homepage_reviews/
│   ├── findings.md                 # Homepage review analysis
│   ├── evidence_table.csv          # Structured evidence
│   ├── review_registry.csv         # All reviews tracked
│   ├── review_sample.csv           # Analyzed sample
│   ├── reviewer_tags.csv           # Reviewer classifications
│   ├── sentiment_summary.csv       # Sentiment distribution
│   └── topic_summary.csv           # Topic mentions
├── section_4_creator_reviews/
│   ├── findings.md                 # Creator video analysis
│   ├── evidence_table.csv          # Structured evidence
│   ├── candidate_videos.csv        # All candidates
│   ├── selected_videos.csv         # Videos selected for analysis
│   ├── transcript_segments.csv     # Video transcripts
│   ├── creator_profiles.csv        # Creator credibility ratings
│   ├── claim_evidence_map.csv      # Claims cross-referenced
│   └── topic_consensus.csv         # Creator consensus by topic
└── synthesis/
    ├── executive_summary.md        # Cross-section synthesis
    └── final_report.md             # Complete research report
```

---

## Integration Architecture

### Master Runner (run_research.py)

The master runner orchestrates all sections:

1. **Credential Preflight**: Checks for required API keys/cookies
2. **Section Sequencing**: Runs sections in order (1→2→3→4)
3. **Resume Support**: Can resume from any section
4. **Cross-Section Validation**: Ensures contracts are met before synthesis
5. **Synthesis Trigger**: Calls assemble_report.py for final output

### Section Runners

Each section has its own runner:

- `run_section_2.py`: YouTube + Bilibili comment collection
- `run_section_3.py`: TapTap + Bilibili review collection
- `run_section_4.py`: Creator video import + annotation

All support:
- `--from-step`: Resume from specific pipeline step
- `--skip-capture`: Skip collection, start from analysis
- `--check-readiness`: Validate prerequisites
- `--list-steps`: Show available pipeline steps

### Synthesis Layer (assemble_report.py)

Cross-section analysis that:

1. Reads all section `findings.md` files
2. Extracts key conclusions, positive/negative signals
3. Identifies cross-validated claims (mentioned in multiple sections)
4. Identifies contradictions (different sentiment on same topic)
5. Generates executive summary with overall judgment
6. Generates final report with all sections embedded

---

## Troubleshooting

### Section 2: No credentials

If you see "No video platform credentials found":

1. Get YouTube API key from Google Cloud Console
2. Or get Bilibili cookie from browser DevTools
3. Set environment variables or pass as arguments
4. See `references/credentials_guide.md`

### Section 3: Bilibili requires cookie

Bilibili game pages require authentication. Use the semi-automatic flow:

1. Open browser DevTools on the Bilibili game page
2. Copy any API request as cURL
3. Save to a file and pass to `--biligame-request-bundle-file`
4. See `references/section_3_bilibili_semi_auto_guide.md`

### Missing findings.md

If a section shows "missing" in readiness check:

1. Check that the section was actually run
2. Verify the section directory exists
3. Run the section again if needed
4. Or create empty `findings.md` with template if section is intentionally skipped

### Synthesis shows low confidence

Cross-section confidence is based on:
- Number of completed sections
- Individual section confidence ratings
- Amount of cross-validated evidence

To improve confidence:
1. Complete more sections
2. Gather more evidence per section
3. Look for claims that appear in multiple sections

---

## Development & Extension

### Adding a New Platform

1. Create collector script in `scripts/collect_<platform>_comments.py`
2. Follow CSV output contract from `references/report_schema.md`
3. Add platform detection in section runner
4. Update credentials guide

### Modifying CSV Schemas

CSV schemas are defined in section common modules:

- Section 2: Inline in collector scripts
- Section 3: `section_3_common.py`
- Section 4: `section_4_common.py`

Update both the common module and any existing data files.

### Adding Analysis Steps

Section runners use `STEP_ORDER` arrays:

```python
STEP_ORDER = ["capture", "normalize", "sentiment", "topics", "finalize"]
```

Add new steps by:
1. Creating the script
2. Adding to `STEP_ORDER`
3. Adding to `STEP_ALIASES`
4. Updating `STEP_FILE_REQUIREMENTS`

---

## Version History

**v1.0.0** - Initial release
- Sections 1-4 implemented
- YouTube + Bilibili support for Section 2
- TapTap + Bilibili support for Section 3
- Creator review pipeline for Section 4
- Cross-section synthesis layer
- Unified master runner
