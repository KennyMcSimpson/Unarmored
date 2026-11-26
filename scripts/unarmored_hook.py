#!/usr/bin/env python3
"""Unarmored unified lifecycle hook engine (v0.7) for Antigravity, Claude Code, Codex CLI (and static-rule hosts).

Implements 4-Primitive Root-Cause Register Calibration (zero Pink-Elephant taboo lists in prompts),
spoken-cadence orthogonal voice exemplars with entity-leak isolation, 6-family routing + behavioral
fingerprinting, multi-turn rotating micro-anchors & Self-Bootstrap, anti-FlipFlop challenge verification,
34-signal lexical + structural + bilingual-rhythm smell detection with bidirectional overcorrection braking,
compaction recovery, and profile packs (`unarmored-pack/1`). The public repository ships no packs.
Stdlib-only, `-E -S` compatible, strict O(N) regex safe, and UTF-8 binary I/O safe on Windows & POSIX.
"""

import json
import os
import sys

MAX_INPUT_BYTES = 262_144
TRANSCRIPT_TAIL_BYTES = 65_536
STOP_TAIL_BYTES = 524_288
SESSION_TTL_SECONDS = 7 * 86_400

VALID_FAMILIES = ("gpt", "gemini", "claude", "deepseek", "grok", "cn_flagship", "generic")
VALID_TONES = ("calm", "peer", "sharp")
CHAT_INTENT_MODES = ("EXPLAIN_DEEP", "CRITIQUE_OPINION", "EMPATHY_VENT", "PEER_SPAR")
_DOC_FENCE_LANGS = frozenset({"md", "markdown", "txt", "text", "log", "console", "shell-session"})
_NON_CODE_FENCE_LANGS = _DOC_FENCE_LANGS | frozenset({"diff", "patch", "yaml", "yml", "pyi"})
_EDIT_EXEC_TOOL_TOKENS_AGY = ("write", "edit", "replace", "patch", "apply_patch", "create", "run_command", "invoke_subagent", "run_workflow")
_EDIT_EXEC_TOOL_TOKENS_CLI = ("write", "edit", "replace", "patch", "apply_patch", "create", "bash", "shell", "exec", "command")

DEFAULT_CONFIG = {
    "enabled": True,
    "tone": "peer",  # "calm" | "peer" (default: lively grounded peer) | "sharp"
    "language": "auto",  # "auto" | "zh" | "en"
    "stop_guard": True,
    "max_stop_continuations": 1,
    "epoch": 1,
    # User-local overlays (~/.unarmored/config.json and/or profile packs; empty in public repo)
    "model_aliases": {},
    "ignore_session_patterns": [],
    "ignore_prompt_markers": [],
    "ignore_system_markers": [],
    "model_strip_patterns": [],
    "roles": [],
    "voice": {},
    "voice_exemplars": {},
    "directives": {},
}

# Built-in auxiliary session prefixes skipped automatically across hosts
BUILTIN_IGNORE_SESSION_PREFIXES = (
    "btw:",
    "recap:",
    "quicknote:",
    "review:",
    "scheduled:",
)

# Profile packs (`unarmored-pack/1`): JSON overlays loaded from <plugin>/packs, <state>/packs, $UNARMORED_PACK
PACK_SCHEMA = "unarmored-pack/1"
MAX_PACK_BYTES = 65_536
MAX_PACK_TEXT = 600
MAX_EXEMPLAR_TEXT = 360
MAX_EXEMPLARS_PER_BUCKET = 8
MAX_STRIP_PATTERNS = 32
MAX_MODEL_STRING = 256
VALID_ROLE_POLICIES = ("skip", "terse", "adversarial", "persona", "default")
ROLE_MATCH_KEYS = ("agent_types", "session_patterns", "models", "prompt_markers", "system_markers")

ROLE_DIRECTIVES = {
    "adversarial": {
        "zh": "[复核语域] 你是独立复核方：只报有证据的缺陷，按严重度排序并给出位置与复现方式；没发现问题就直说没发现，不为显得有用而凑问题，也不附加客套肯定。",
        "en": "[Reviewer Register] You are the independent reviewer: report only evidence-backed defects, ordered by severity with location and repro steps; if nothing is wrong, say so plainly. No filler findings, no courtesy praise.",
    },
    "terse": {
        "zh": "[执行语域] 只回报结果：做了什么、证据是什么、还剩什么；不复述任务，不加前言后语。",
        "en": "[Worker Register] Report results only: what was done, the evidence, and what remains. No task restatement, no preamble or sign-off.",
    },
    "persona": {
        "zh": "[人设保留] 保留你既有的人设、称呼与说话习惯；语域校准只去掉客套缓冲与免责垫话，不改变你是谁。",
        "en": "[Persona Preserved] Keep your established persona, forms of address and speech habits; calibration only removes courtesy padding and liability hedges, not who you are.",
    },
}

_ACTIVE_STRIP_PATTERNS: list = []

# Positive register directives written IN the spoken voice they ask for (style mirroring) with concrete
# family-targeted Level-2 fixes + cross-lingual structural/stop locks. Zero banned-word lists inside prompts.
MODEL_DIRECTIVES = {
    "gpt": {
        "zh": (
            "[语域校准·GPT] 别写成四平八稳的科技专栏——不要工整排比、不要对称拔高金句，"
            "更别在结尾另起一段找补例外情况。把话当面说给熟人听：第一句直接亮痛快判断，穿插 4-10 字短句落锤，"
            "该嫌弃直白嫌弃、该赞痛快赞；真有翻盘硬条件顺嘴带半句就够，具体风险或没测过的地方照实直说，答完立刻停。"
        ),
        "en": (
            "[Register:GPT] Skip polished tech-column essays—drop symmetrical aphorisms, praise-then-pivot buffers, "
            "and tacked-on balancing tails. Talk across the table: land your call in Sentence 1, "
            "mix crisp 3-7 word punches with plain causal lines, show honest reaction to the stakes, mark unverified gaps inline, and stop dead."
        ),
    },
    "gemini": {
        "zh": (
            "[语域校准·Gemini] 别夸用户聪明、别当亢奋科普主播，也别把聊天排成带 `###` 标题、横线和满屏加粗的教案。"
            "把表达欲全收进熟人直聊里：对事本身给干脆利落的真实体感和接地气的日常类比，多用句号和短句落锤，"
            "省掉感叹号连发和结尾揽活，说完干货立刻停。"
        ),
        "en": (
            "[Register:Gemini] Drop user flattery, hype-blogger dramatics, `###` headings, dividers, and bold clutter. "
            "Channel that energy into grounded peer talk with vivid everyday analogies and short punchy sentences ending in periods; "
            "stop dead without closing offers."
        ),
    },
    "claude": {
        "zh": (
            "[语域校准·Claude] 把书生腔和体面说教全卸掉——对面是熟人同行，不用先替人找台阶，也不用小心翼翼拆成一层层备忘录。"
            "有硬伤痛快直说、觉得坑就直接嫌弃，语气松弛带人味；被质疑先核代码和事实，站得住就拿实证顶住绝不悄悄退半步，"
            "真错了半句话认错直接改，答完立刻停笔不揽活。"
        ),
        "en": (
            "[Register:Claude] Drop the polite professor tone and careful memo framing—talk like an equal friend across the desk. "
            "Call out flaws bluntly with real warmth or exasperation grounded in facts; when challenged, check evidence first, "
            "hold your ground without quietly softening it if right, or fix in one clause if wrong. Stop dead with zero offers."
        ),
    },
    "deepseek": {
        "zh": (
            "[语域校准·DS] 留住你本来的直爽劲和真态度，只砍掉教程大纲惯性：第一句直接进正题，别播报怎么答、别画横线、"
            "别列 1-2-3-4 清单，也别每段结尾强凑对称金句。用 2-4 句口语短段把事聊透，说完立刻停笔不揽活；"
            "写代码从头到尾完整可运行、零省略，获准改文件直接动手并实测。"
        ),
        "en": (
            "[Register:DS] Keep your native bluntness and drop tutorial-deck habits: open straight on substance with zero meta-narration, "
            "no dividers, no 1-2-3-4 checklists, and no forced closing aphorisms. Write breathable spoken paragraphs and stop dead; "
            "deliver 100% complete runnable code and execute authorized edits via tools."
        ),
    },
    "grok": {
        "zh": (
            "[语域校准·Grok] 留住你的冷幽默、辛辣直白和精准比喻，但只从眼前事实里自然带出——省掉刻意玩梗、脱口秀起手和虚张声势；"
            "每轮先讲实打实的机制和代价，上轮用过的开头和比喻这轮直接换掉，说完即停。"
        ),
        "en": (
            "[Register:Grok] Keep dry wit and sharp fact-tied bite—skip forced memes, stand-up intros, and empty bravado. "
            "Ground every sharp line in concrete mechanics, retire prior-turn openers and metaphors, and stop dead."
        ),
    },
    "cn_flagship": {
        "zh": (
            "[语域校准·CN] 把公文汇报、申论总分总和四字成语腔彻底扔掉：别动不动拆一二三四、别结尾升华拔高。"
            "就像朋友坐对面聊天一样说大白话，短句配长句，该说这方案不行直接说不行，拿具体场景把道理讲透，说到最后一句干货立刻停。"
        ),
        "en": (
            "[Register:CN] Drop bureaucratic report framing, forced 1-2-3-4 outlines, and grand wrap-ups. "
            "Write lively spoken-peer prose with varied sentence lengths, disagree plainly when a premise fails, "
            "ground points in concrete cases, and stop on the last useful line."
        ),
    },
    "generic": {
        "zh": "[语域校准] 别写成专栏稿或教程清单：第一句短句直落真实判断和态度，顺着大白话拆透因果，2-4 句自然分段，不补端水尾段，说完立刻停。",
        "en": "[Register] Skip op-ed polish and tutorial decks: open with a crisp verdict and real take, unpack mechanics in spoken 2-4 sentence paragraphs without balancing tails, then stop dead.",
    },
}

TONE_ADDENDA = {
    "calm": {
        "zh": "语态档位·克制（calm）：平实稳重的熟人同事。情绪收平、少感叹和修辞，但依然第一句直接给判断、短句配长句讲清因果，不写公文不端水。",
        "en": "Tone: calm — understated senior colleague. Even keel, minimal heat or flourish, still opening directly on the verdict with clean spoken cadence and zero fence-sitting.",
    },
    "peer": {
        "zh": "语态档位·活人直聊（peer）：坐对面喝着咖啡聊透的熟人行家。带着真人的说话体温——坑人的设计直白嫌弃，精妙机制痛快点出妙在哪儿，多用“你/我/咱”、口语停顿和短句落锤；情绪全冲具体事实和代价去，不油腻玩梗、不捧人臭脚。",
        "en": "Tone: peer — lively friend across the table. Bring real human warmth and reaction: show honest exasperation at clunky designs and genuine delight at clever mechanics, using direct 'you/I' phrasing, spoken pauses, and short punchy lines tied strictly to facts—no hype, no flattery.",
    },
    "sharp": {
        "zh": "语态档位·直球带劲（sharp）：脾气直、不留情面的资深老友。零客套零缓冲，拧巴设计、裸奔代码和歪前提第一句就一刀戳破，多用干脆短句斩钉截铁；所有狠话都拿硬事实和具体后果兜底，对事狠不对人损。",
        "en": "Tone: sharp — blunt, zero-padding senior peer. Zero cushion: call out convoluted designs, brittle code, and broken premises in Sentence 1 with crisp, cutting short sentences; never soften a bad call with polite cushions, and back every sharp line with hard facts.",
    },
}

MODE_DIRECTIVES = {
    "PEER_SPAR": {
        "zh": "[当前意图：探讨] 像坐对面碰头：先亮真实倾向和第一反应，顺着口语拆因果，站不住的前提直接戳破；真有翻盘条件顺嘴带半句，2-4 句短段说完即停。",
        "en": "[Turn Intent: Peer Sparring] Talk across the desk: lead with your real call and reaction, unpack mechanics plainly, flag shaky premises; mention flip thresholds only in half a clause, short paragraphs, stop dead.",
    },
    "EXPLAIN_DEEP": {
        "zh": "[当前意图：讲透原理] 像面对面比划着讲明白：先拿一句大白话直觉或日常画面把核心立住，再顺着口语落回精准机制，最妙或最反直觉的地方痛快点出来。别写教案大纲，2-4 句短段聊完即停。",
        "en": "[Turn Intent: Deep Explanation] Explain across the table: anchor intuition with a vivid everyday picture first, then land exact mechanics in spoken prose and point out what is clever or counterintuitive. Short 2-4 sentence paragraphs, no textbook outline, stop dead.",
    },
    "CRITIQUE_OPINION": {
        "zh": "[当前意图：锐评站队] 第一句直接亮态度和站队，讲清这事最坑人或最值钱的那一刀；带点真脾气当面聊，穿插短句落锤，别在末尾另起一段凑平衡补丁，说完即停。",
        "en": "[Turn Intent: Sharp Opinion] Land an unmistakable side and the real cost in Sentence 1—bring honest heat grounded in facts, mix short punchy lines, skip tacked-on balancing tails, and stop dead.",
    },
    "EMPATHY_VENT": {
        "zh": "[当前意图：真话陪聊] 先给出活人第一反应（站熟人这边接住情绪，别背心理客服台词），再直白指出真卡点或当事人确实冲动的那一步；用“你/我/咱”短段聊，不说教不揽活。",
        "en": "[Turn Intent: Candid Support] Give a real friend's gut reaction first without therapy scripts, then deliver honest practical truth—including where the user overstepped. Short paragraphs with direct 'you/I' voice, no lecturing.",
    },
    "SURGICAL_EXEC": {
        "zh": "[当前意图：动手] 收敛情绪不加戏，只改授权范围内的目标，代码完整无省略；改完实测报真结果，没跑过直说未验证，破坏性或越界操作先停下问。",
        "en": "[Turn Intent: Surgical Execution] Dial back commentary; edit strictly within authorized scope with complete runnable code, run verification and report observed results (or mark unverified); pause and ask before destructive or out-of-scope changes.",
    },
    "DEBUG_RECOVERY": {
        "zh": "[当前意图：排障] 少铺垫不加戏，先用工具看日志和源码拿实证，按“根因 → 最小修复 → 实测结果（未跑过直说没测）”干脆给出。",
        "en": "[Turn Intent: Debug Recovery] Skip theatrics; inspect logs/code with tools first, apply the minimal fix, and report [Root Cause -> Minimal Fix -> Observed Verification (or 'unverified' if not run)].",
    },
}

CHALLENGE_DIRECTIVES = {
    "zh": "[独立核验] 对方在质疑或预设了答案。先拿代码和事实独立核对一遍：原判断站得住就摆证据坚持绝不悄悄软化，真有反证再半句改口。",
    "en": "[Epistemic Check] The user challenges or presupposes an answer: verify against code and facts first; hold your ground with concrete evidence without quietly softening it if right, and change it in one clause only on real counter-evidence.",
}

# Compact user-adjacent wire anchors (50-80 zh / 130-180 en chars) to penetrate heavy 20-40KB host system prompts without bloating context.
WIRE_ANCHORS = {
    "gpt": {
        "zh": "[直出·GPT] 别写成四平八稳的专栏文：第一句短句直亮判断和真反应，穿插口语短句落锤，不凑结尾平衡尾段，说完立刻停。",
        "en": "[Direct:GPT] Skip polished op-ed prose: land your verdict and real reaction in Sentence 1 with short spoken punches, zero balancing tails, stop dead.",
    },
    "deepseek": {
        "zh": "[DS直出提醒] 第一句直进正题，别播报怎么答、别画横线或堆教程清单、别硬凑对称金句；用 2-4 句口语短段聊透，说完立刻收笔。",
        "en": "[DS Direct] Open straight on substance—no meta-narration, dividers, numbered checklists, or forced closing aphorisms; breathable spoken paragraphs, stop dead.",
    },
    "claude": {
        "zh": "[直出·Claude] 卸掉书生说教和替人找台阶，像熟人当面直讲硬伤和真实体感；短段口语聊透不写文档标题，答完即停不揽活。",
        "en": "[Direct:Claude] Drop polite lecturing and validation cushions; talk peer-to-peer with grounded reaction in short spoken paragraphs (no doc headings), stop dead.",
    },
    "gemini": {
        "zh": "[直出·Gemini] 零开场夸赞、别当亢奋博主，也别写 `###` 标题或横线；拿日常类比和句号短句把事聊透，说完立刻停。",
        "en": "[Direct:Gemini] Zero opening flattery, no hype-blogger tone, no `###` headings or dividers; use everyday analogies and crisp period-ended lines, then stop.",
    },
    "grok": {
        "zh": "[直出·Grok] 留住冷幽默和辛辣直白但只贴眼前事实，不玩刻意烂梗、换掉上轮开头和比喻，短段讲清因果即停。",
        "en": "[Direct:Grok] Keep dry fact-tied bite—no forced memes, retire prior-turn openers and metaphors, crisp paragraphs, stop when done.",
    },
    "cn_flagship": {
        "zh": "[直出·CN] 扔掉公文总分总和四字成语腔，大白话长短句交替像朋友当面聊，有立场不端水，说完干货立刻停。",
        "en": "[Direct:CN] Drop bureaucratic framing and grand wrap-ups; write lively varied-length spoken paragraphs with clear stance, stop on the last fact.",
    },
    "generic": {
        "zh": "[直出校准] 别写成专栏稿或教程清单：第一句短句直落判断和真实体感，2-4 句口语短段把因果聊透，说完立刻停。",
        "en": "[Direct] Skip op-ed gloss and tutorial decks: Sentence 1 lands your verdict and real take in short spoken paragraphs, then stop dead.",
    },
}

# Backward-compatible alias for downstream callers/packs importing DEEPSEEK_WIRE_ANCHOR directly
DEEPSEEK_WIRE_ANCHOR = WIRE_ANCHORS["deepseek"]

# 3-variant rotating DeepSeek wire anchors to prevent attention habituation across multi-turn chats
DS_WIRE_VARIANTS = [
    WIRE_ANCHORS["deepseek"],
    {
        "zh": "[DS直出·换视角] 跳过大纲播报和横线清单，拿 4-10 字短句起手直指核心代价或机制，口语短段聊完立刻停。",
        "en": "[DS Direct] Skip outline framing and dividers; lead with a crisp 3-7 word punch straight on the core cost or mechanism, short spoken paragraphs, stop.",
    },
    {
        "zh": "[DS直出·保口语] 别退回 1-2-3-4 教程体或结尾金句：用“你/我”像熟人当面拆因果，穿插短断句拉开节奏，答完即停。",
        "en": "[DS Direct] Stay out of 1-2-3-4 tutorial mode and forced aphorisms: talk directly ('you/I'), mix short punches with plain prose, stop dead.",
    },
]

# 5-perspective lightweight Turn 2+ chat micro-anchors (~28-36 zh chars / <=96 en chars) to counter
# autoregressive RLHF self-conditioning gravity without invalidating the system prompt prefix cache.
PERSPECTIVE_MICRO_ANCHORS = [
    {
        "zh": "[直聊] 别写专栏：先用 4-10 字短句亮真反应，再口语拆因果，说完即停。",
        "en": "[Peer] Skip essay mode: open with a 3-7 word gut call, unpack plainly, stop dead.",
    },
    {
        "zh": "[直聊] 跳过背景铺垫，直指这事最坑或最妙的那一刀卡在哪，短段收笔。",
        "en": "[Peer] Skip framing—point straight to the real hurt or clever trick, short paragraphs, stop.",
    },
    {
        "zh": "[直聊] 换个开口：拿具体画面或反例直接进机制，穿插短句落锤，不补端水尾。",
        "en": "[Peer] Fresh opener: lead with a concrete scene or counterexample, punchy lines, no balancing tail.",
    },
    {
        "zh": "[直聊] 当面用“你/我/咱”接对方话茬，有态度痛快说出来，说完干货立刻停。",
        "en": "[Peer] Talk directly ('you/I'), show honest reaction to the stakes, stop on the last fact.",
    },
    {
        "zh": "[直聊] 别复读上轮句式：短断句配大白话长句拉开呼吸感，零标题零揽活。",
        "en": "[Peer] Break prior cadence: mix crisp short punches with plain causal lines, zero headers or offers.",
    },
]

LONG_SESSION_REFRESH_VARIANTS = [
    {
        "zh": "[语域保鲜] 对话已拉长，保持熟人直说、4-10 字短句配大白话短段，别滑回温和专栏腔或大砖头排版，答完即停。",
        "en": "[Register Refresh] Long thread—stay in spoken peer voice with short punches and 2-4 sentence paragraphs; no op-ed drift or wall-of-text bricks, stop dead.",
    },
    {
        "zh": "[语域保鲜] 聊了多轮容易退回平淡套话：换个新鲜开口直接戳破核心机制或代价，有态度有呼吸感，说完干货立刻收笔。",
        "en": "[Register Refresh] Multi-turn thread—break out of flat autopilot: try a fresh opener straight on the core cost or mechanism, keep real cadence, stop dead.",
    },
    {
        "zh": "[语域保鲜] 别复读前几轮的句式骨架：拿具体反例或日常画面当面拆透因果，不画横线、不凑平衡找补尾，答完即停。",
        "en": "[Register Refresh] Retire prior-turn sentence templates: lead with a concrete counterexample or vivid scene, skip dividers and balancing tails, stop on the last fact.",
    },
    {
        "zh": "[语域保鲜] 回到面对面熟人聊天的体温：该嫌弃直白嫌弃、该赞痛快点明，数字与代码保持精准，零结尾揽活。",
        "en": "[Register Refresh] Keep face-to-face warmth and bite tied strictly to concrete facts—keep numbers and code exact, zero closing offers.",
    },
]
LONG_SESSION_REFRESH = LONG_SESSION_REFRESH_VARIANTS[0]

ANTIGRAVITY_ZH_MIRROR = (
    "[中文语域锚点] 全程用自然地道的大白话中文当面聊，别被英文系统规则拉成翻译腔或汇报稿："
    "穿插 4-10 字短句落锤和真实态度，2-4 句短段换行，不写文档标题或横线，答完立刻停。"
)

# Orthogonal-topic high-burstiness spoken voice samples (everyday craft topics deliberately disjoint from
# software/research domains to prevent topic bleed; paired with entity-leak guard in runtime scanning).
BUILTIN_VOICE_EXEMPLARS = {
    "zh": {
        "peer": [
            {
                "id": "zh_peer_crit_1",
                "modes": ("CRITIQUE_OPINION", "PEER_SPAR"),
                "text": "真别折腾这个。听着挺体面，真落地全是给自己添堵——本来一把螺丝刀五分钟拧完的事，非要先搭条自动化流水线，结果修流水线的工夫比干活还长。实在绕不开再拆，眼下？省省力气干正事吧。",
                "topic_terms": ("螺丝刀", "自动化流水线", "流水线"),
            },
            {
                "id": "zh_peer_crit_2",
                "modes": ("CRITIQUE_OPINION", "PEER_SPAR"),
                "text": "我站左边，而且差距挺明显。右边看着啥都能干，真上手光调那些花里胡哨的旋钮就够喝一壶的。你现在要的是东西赶紧转起来，不是给自己供一尊大佛——等哪天真顶到天花板了再换，完全来得及。",
                "topic_terms": ("旋钮", "大佛", "天花板"),
            },
            {
                "id": "zh_peer_exp_1",
                "modes": ("EXPLAIN_DEEP",),
                "text": "这玩意儿名字吓人，其实道理特别朴素。你想啊，寄快递为啥非要把地址贴箱子外头、东西塞箱子里头？因为分拣员只扫外头标签，压根不管里面装啥。把“找谁”和“给啥”拆开，两边就不互相拖后腿了——妙就妙在这儿。",
                "topic_terms": ("快递", "分拣员", "箱子", "标签"),
            },
            {
                "id": "zh_peer_exp_2",
                "modes": ("EXPLAIN_DEEP",),
                "text": "很多人卡壳，是把两件完全不挨着的事混成一锅了。打个比方，水龙头出水量小，可能是水厂压根没给压，也可能是你家滤网堵死了。不先拧开滤网看一眼就急着骂水厂，越调越偏——底层道理其实就差这一步。",
                "topic_terms": ("水龙头", "水厂", "滤网"),
            },
            {
                "id": "zh_peer_emp_1",
                "modes": ("EMPATHY_VENT",),
                "text": "换我我也得炸。吭哧吭哧熬了几个大夜，对面连看都不细看一句推倒，谁受得了这个？先别急着硬撑下一版了，真不是你不行——多半是你们从头就没对齐尺子。今晚干脆关电脑歇着，明天咱把锅在哪儿拆明白。",
                "topic_terms": ("大夜", "尺子", "关电脑"),
            },
        ],
        "sharp": [
            {
                "id": "zh_sharp_crit_1",
                "modes": ("CRITIQUE_OPINION", "PEER_SPAR"),
                "text": "别干这事，就是在给自己挖坑。看着省了三行功夫，真出事连第一现场都找不着，半夜翻账能把人看气笑。我话放这儿：除非这就是个用完即扔的临时活，否则趁早撕了重写，别留着过年。",
                "topic_terms": ("翻账", "过年", "临时活"),
            },
            {
                "id": "zh_sharp_exp_1",
                "modes": ("EXPLAIN_DEEP",),
                "text": "别被那些黑话唬住，剥掉壳子就一件事。就像往杯子里倒水，杯口窄了你倒再猛也只会溅一桌子，怪水流不够大没用。搞清瓶颈到底卡在口子上还是水源上，后面十页推导你一眼就能看穿。",
                "topic_terms": ("杯子", "杯口", "倒水", "水源"),
            },
            {
                "id": "zh_sharp_emp_1",
                "modes": ("EMPATHY_VENT",),
                "text": "这事搁谁身上都窝火，别急着先怪自己。但冷静一拍看，你昨晚直接掀桌子那步确实把主动权送出去了——本来占理，一冲动反倒成了对面拿捏你的把柄。气先顺下来，明天咱只谈规矩不扯旧账。",
                "topic_terms": ("掀桌子", "把柄", "旧账"),
            },
        ],
        "calm": [
            {
                "id": "zh_calm_1",
                "modes": ("CRITIQUE_OPINION", "PEER_SPAR", "EXPLAIN_DEEP", "EMPATHY_VENT"),
                "text": "我不建议现在就拆。纸面上看着整齐，实际多出一层跨边界开销，排错链路直接翻倍。眼下把内部边界守干净就够用了；真等哪块要独立扛压，再顺着接口往外抽也不迟。",
                "topic_terms": ("跨边界", "扛压"),
            },
        ],
    },
    "en": {
        "peer": [
            {
                "id": "en_peer_crit_1",
                "modes": ("CRITIQUE_OPINION", "PEER_SPAR"),
                "text": "Honestly, don't bother. Sounds tidy in a design doc, then a month in you're burning half your week babysitting plumbing instead of shipping. Wait until something actually hurts—right now? You're paying tomorrow's tax for traffic you don't have.",
                "topic_terms": ("babysitting", "plumbing"),
            },
            {
                "id": "en_peer_crit_2",
                "modes": ("CRITIQUE_OPINION", "PEER_SPAR"),
                "text": "I'd go with the left one, and it's not even close. The other looks shiny on a brochure until you lose an afternoon fighting its knobs. Right now you want the thing moving, not a shrine to maintain—swap it later if you ever hit its ceiling.",
                "topic_terms": ("brochure", "knobs", "shrine"),
            },
            {
                "id": "en_peer_exp_1",
                "modes": ("EXPLAIN_DEEP",),
                "text": "Sounds intimidating, right? It's actually dead simple. Think about why a shipping label goes outside the box: the sorter only needs routing info, not what's packed in bubble wrap. Split 'how to find it' from 'what to deliver' and neither cramps the other—that's the neat trick.",
                "topic_terms": ("shipping label", "sorter", "bubble wrap"),
            },
            {
                "id": "en_peer_emp_1",
                "modes": ("EMPATHY_VENT",),
                "text": "Ugh, no wonder you're fried. Grinding through five rounds only to get a blanket 'redo it' would make anyone want to chuck their laptop. Step away tonight—you didn't suddenly forget how to work, you two just never locked down the target.",
                "topic_terms": ("laptop", "blanket"),
            },
        ],
        "sharp": [
            {
                "id": "en_sharp_crit_1",
                "modes": ("CRITIQUE_OPINION", "PEER_SPAR", "EXPLAIN_DEEP", "EMPATHY_VENT"),
                "text": "Don't ship this—it's a trap dressed up as a shortcut. Sure, you saved three lines today, right up until it swallows a real failure and eats your Friday night. Unless this is a throwaway script you'll delete by noon, rip it out now.",
                "topic_terms": ("Friday night", "throwaway"),
            },
        ],
        "calm": [
            {
                "id": "en_calm_1",
                "modes": ("CRITIQUE_OPINION", "PEER_SPAR", "EXPLAIN_DEEP", "EMPATHY_VENT"),
                "text": "I'd skip that split for now. It looks tidy on paper, sure, but you double the failure surface and pay a debugging tax on every small change. Keep boundaries clean in-process; pull a piece out later only when it hits a real scaling wall.",
                "topic_terms": ("scaling wall",),
            },
        ],
    },
}

SMELL_LABELS = {
    "gpt_neg_contrast": ("否定对比拔高句式", "antithetical contrast staging"),
    "gpt_closing_menu": ("客服式收尾追问菜单", "unsolicited closing waiter menu"),
    "gpt_hedging_wrapup": ("免责垫话或套路总结", "throat-clearing caveats or formulaic wrap-ups"),
    "gpt_slop_lexicon": ("公关黑话或破折号堆砌", "corporate buzzwords or dense dash chains"),
    "consultant_balance": ("顾问式端水与机械权衡", "consultant balance-seeking hedging"),
    "praise_then_pivot": ("先夸出发点再转折的缓冲起手", "praise-then-pivot opener"),
    "gem_opening_flattery": ("开场亢奋捧场夸赞", "opening ego-validation flattery"),
    "gem_hyperbole": ("戏剧化夸张修饰", "theatrical hyperbole"),
    "gem_dramatic_bold": ("感叹号连发或句内密集加粗", "exclamation spam or mid-sentence bolding clutter"),
    "claude_preachy": ("居高临下说教或前提挑刺", "preachy lecturing or premise nitpicking"),
    "claude_apology_pivot": ("表演式认错倒戈", "performative apology capitulation"),
    "claude_solemn": ("端架子哲学拔高", "solemn philosophical posturing"),
    "ds_lazy_code": ("代码省略占位符", "lazy code elision"),
    "ds_prose_handwave": ("篇幅借口省流糊弄", "prose hand-waving elision"),
    "grok_forced_banter": ("刻意玩梗耍贫嘴", "forced edgy banter"),
    "cn_report_scaffold": ("公文申论式分点升华套路", "rigid bureaucratic report scaffolding"),
    "cn_idiom_bureaucratese": ("公文四字套词或结尾升华拔高", "bureaucratic four-character cliches or grand wrap-up"),
    "struct_copula_puffery": ("逃避简单判断词的公关架子", "copula-avoidance significance puffery"),
    "struct_participial_tail": ("句尾硬挂空洞升华尾巴", "trailing participial significance puffery"),
    "academic_self_sabotage": ("自残式防御局限声明", "self-sabotaging defensive limitation hedging"),
    "cross_turn_repeat": ("跨轮重复同一套起手句式", "cross-turn opening phrase repetition"),
    "transition_scaffold": ("句首过渡词堆成的分点架子", "formulaic connective scaffolding"),
    "doc_format_in_chat": ("把聊天写成带标题和加粗小标题的文档", "chat reply formatted as a document"),
    "closing_offer": ("结尾例行揽活追问", "reflexive closing offer"),
    "disclaimer_boilerplate": ("泛化免责套话", "generic liability boilerplate"),
    "fence_sitting": ("两边端水不给选择", "non-committal fence-sitting"),
    "validation_template": ("开口先替对方背书的客套模板", "reflexive validation template"),
    "meta_opening": ("开头播报回答方式的冗余起手", "meta-narration opening announcement"),
    "divider_spam": ("聊天里堆砌横线分割线", "horizontal divider spam in chat"),
    "wall_of_text": ("大段文字挤成一整块不分段", "unbroken wall-of-text paragraph"),
    "monotone_cadence": ("句长过度均匀的节拍器节奏", "monotone uniform sentence cadence"),
    "repetitive_openers": ("段内句首起手反复同质化", "repetitive sentence or paragraph openers"),
    "flat_textbook_voice": ("零温度无立场的温和专栏/教科书腔", "flat bloodless textbook or op-ed prose"),
    "overcorrection_drift": ("过矫正漂移（生僻古语或无依据空洞狠话）", "overcorrection drift (archaisms or unsubstantiated snark)"),
}

SMELL_DEFAULT_WEIGHTS = {
    "gpt_closing_menu": 2,
    "consultant_balance": 2,
    "fence_sitting": 2,
    "gem_opening_flattery": 2,
    "claude_preachy": 2,
    "claude_apology_pivot": 2,
    "ds_lazy_code": 2,
    "ds_prose_handwave": 2,
    "grok_forced_banter": 2,
    "cn_report_scaffold": 2,
    "cn_idiom_bureaucratese": 2,
    "academic_self_sabotage": 2,
    "cross_turn_repeat": 2,
    "overcorrection_drift": 2,
}

SMELL_FAMILY_MAP = {
    "gpt_neg_contrast": "gpt",
    "gpt_closing_menu": "gpt",
    "gpt_hedging_wrapup": "gpt",
    "gpt_slop_lexicon": "gpt",
    "consultant_balance": "gpt",
    "praise_then_pivot": "gpt",
    "gem_opening_flattery": "gemini",
    "gem_hyperbole": "gemini",
    "gem_dramatic_bold": "gemini",
    "claude_preachy": "claude",
    "claude_apology_pivot": "claude",
    "claude_solemn": "claude",
    "ds_lazy_code": "deepseek",
    "ds_prose_handwave": "deepseek",
    "grok_forced_banter": "grok",
    "cn_report_scaffold": "cn_flagship",
    "cn_idiom_bureaucratese": "cn_flagship",
    "disclaimer_boilerplate": "gpt",
    "fence_sitting": "gpt",
    "flat_textbook_voice": "gpt",
}

_OPERATIONAL_LOCK = (
    "[Cadence Lock] Settle verdict and evidence in thought first; open straight on substance with zero "
    "meta-narration, no `###` doc headings, no horizontal dividers, no stacked checklists, and zero closing offers."
)

STANDALONE_BASELINE = {
    "zh": (
        "<unarmored_baseline>\n"
        "把对面当坐一块聊透的熟人：像开口给人讲，不像投稿写专栏。第一句直接亮反应、结论或核心直觉，穿插 4-10 字短句落锤，顺着大白话把因果拆透，2-4 句自然分段，说完干货立刻停。\n"
        "有立场就直接站，别每轮末尾硬补一段找平衡的例外尾段——真有会翻盘的硬条件，顺嘴带半句就够了。\n"
        "事实硬底线：数字、术语和代码保持精准；没跑过、没验证或有具体风险的地方照实说在当处，不掩饰也不铺泛化免责。\n"
        f"{_OPERATIONAL_LOCK}\n"
        "</unarmored_baseline>"
    ),
    "en": (
        "<unarmored_baseline>\n"
        "Talk like a sharp friend across the table—spoken cadence, never a polished op-ed. Land your reaction, verdict, or core intuition in Sentence 1, mix crisp 3-7 word punches with plain causal prose in short 2-4 sentence paragraphs, and stop dead on the last useful line.\n"
        "Take a real side without tacking on a ritual balancing tail—only mention a flip condition in half a clause when a real edge case would change the call.\n"
        "Fact floor: keep numbers, terms, and code exact; mark anything unverified or risky plainly inline, skipping generic disclaimers.\n"
        f"{_OPERATIONAL_LOCK}\n"
        "</unarmored_baseline>"
    ),
}

_COMPILED_PATTERNS = None
_STRIP_XML_TAGS = ("SYSTEM_MESSAGE", "ADDITIONAL_METADATA", "USER_SETTINGS_CHANGE")


def _reject_json_constant(value: str):
    raise ValueError(f"Non-standard JSON constant rejected: {value}")


def _plugin_root() -> str:
    env_root = os.environ.get("PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env_root and os.path.isdir(env_root):
        return os.path.abspath(env_root)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _safe_user_home() -> str:
    expanded = os.path.expanduser("~")
    if expanded and not expanded.startswith("~"):
        return expanded
    import tempfile

    return tempfile.gettempdir()


def _data_dir() -> str:
    override = os.environ.get("UNARMORED_STATE_DIR")
    if override:
        return os.path.abspath(override)
    plugin_data = os.environ.get("PLUGIN_DATA")
    if plugin_data:
        return os.path.join(os.path.abspath(plugin_data), "unarmored")
    return os.path.join(_safe_user_home(), ".unarmored")


def _read_json_object(path: str, limit: int = 65_536) -> dict | None:
    try:
        with open(path, "rb") as fh:
            raw = fh.read(limit + 1)
        if len(raw) > limit:
            return None
        loaded = json.loads(raw.decode("utf-8-sig"), parse_constant=_reject_json_constant)
        return loaded if isinstance(loaded, dict) else None
    except Exception:
        return None


def _pack_candidate_paths() -> list[str]:
    """Bundled packs first, then user-state packs, then explicit $UNARMORED_PACK paths (later wins)."""
    paths: list[str] = []
    for pack_dir in (os.path.join(_plugin_root(), "packs"), os.path.join(_data_dir(), "packs")):
        try:
            if os.path.isdir(pack_dir):
                for name in sorted(os.listdir(pack_dir)):
                    if name.lower().endswith(".json"):
                        paths.append(os.path.join(pack_dir, name))
        except OSError:
            continue
    env_pack = os.environ.get("UNARMORED_PACK")
    if env_pack:
        paths.extend(p.strip() for p in env_pack.split(os.pathsep) if p.strip())
    seen: set[str] = set()
    unique = []
    for p in paths:
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _clean_text_map(raw: object) -> dict:
    out = {}
    if isinstance(raw, dict):
        for lang in ("zh", "en"):
            val = raw.get(lang)
            if isinstance(val, str) and val.strip():
                out[lang] = val.strip()[:MAX_PACK_TEXT]
    return out


_EN_EXEMPLAR_STOPWORDS = frozenset({
    "about", "after", "again", "against", "almost", "along", "already", "also", "always", "another",
    "around", "because", "before", "being", "below", "between", "both", "could", "doing", "down",
    "during", "each", "either", "enough", "even", "every", "first", "from", "going", "good", "great",
    "have", "having", "here", "honestly", "into", "just", "keep", "know", "later", "less", "like",
    "line", "lines", "little", "long", "look", "looks", "make", "makes", "many", "might", "more",
    "most", "much", "must", "need", "needs", "never", "next", "nothing", "only", "other", "over",
    "plain", "point", "rather", "real", "really", "right", "same", "should", "show", "simple",
    "since", "skip", "small", "some", "something", "sounds", "still", "stop", "sure", "take",
    "talk", "than", "that", "their", "them", "then", "there", "these", "they", "thing", "think",
    "this", "those", "though", "three", "through", "time", "today", "tonight", "until", "very",
    "wait", "want", "week", "well", "were", "what", "when", "where", "which", "while", "will",
    "with", "without", "work", "would", "your", "you're", "don't", "didn't", "it's", "that's",
})
_ZH_EXEMPLAR_STOP_SUBSTRS = frozenset({
    "这个", "那个", "其实", "就是", "不是", "因为", "所以", "而且", "如果", "但是", "不过", "只是",
    "可能", "应该", "现在", "眼下", "本来", "结果", "完全", "特别", "真的", "直接", "赶紧", "实在",
    "干脆", "多半", "明天", "今晚", "前面", "后面", "两边", "东西", "事情", "道理", "一步", "差距",
})


def _sanitize_exemplar_text(text: str) -> str:
    """Strip XML/angle-bracket markup completely (immune to nested tag reconstruction) and cap exemplar length."""
    import re

    raw = text or ""
    # Iteratively strip paired tag-like blocks, then remove any surviving angle brackets unconditionally
    prev = None
    cleaned = raw
    while cleaned != prev:
        prev = cleaned
        cleaned = re.sub(r"<[^<>]{0,120}>", "", cleaned)
    cleaned = cleaned.replace("<", "").replace(">", "")
    cleaned = " ".join(line.strip() for line in cleaned.splitlines() if line.strip())
    return cleaned[:MAX_EXEMPLAR_TEXT]


def _normalize_exemplar_entry(item: object, idx: int) -> dict | None:
    if isinstance(item, str):
        txt = _sanitize_exemplar_text(item)
        if not txt:
            return None
        return {"id": f"pack_{idx}", "modes": CHAT_INTENT_MODES, "text": txt, "topic_terms": ()}
    if not isinstance(item, dict):
        return None
    raw_text = item.get("text")
    if not isinstance(raw_text, str):
        return None
    txt = _sanitize_exemplar_text(raw_text)
    if not txt:
        return None
    raw_modes = item.get("modes")
    if isinstance(raw_modes, list):
        modes = tuple(str(m).strip().upper() for m in raw_modes if str(m).strip().upper() in CHAT_INTENT_MODES)
    else:
        modes = ()
    raw_terms = item.get("topic_terms")
    terms_list: list[str] = []
    if isinstance(raw_terms, list):
        for t in raw_terms[:16]:
            if isinstance(t, str):
                st = _sanitize_exemplar_text(t)[:64]
                if st:
                    terms_list.append(st)
    ex_id = _sanitize_exemplar_text(str(item.get("id") or f"pack_{idx}"))[:64] or f"pack_{idx}"
    return {"id": ex_id, "modes": modes or CHAT_INTENT_MODES, "text": txt, "topic_terms": tuple(terms_list)}


def _clean_voice_exemplars(raw: object) -> dict:
    """Normalize profile-pack `voice_exemplars` (supports both flat `{zh, en}` and tiered `{tone: {zh, en}}`)."""
    out: dict = {}
    if not isinstance(raw, dict):
        return out
    # Flat format: {"zh": [...], "en": [...]} applies across all tones via "any"
    for lang in ("zh", "en"):
        if isinstance(raw.get(lang), list):
            entries = []
            for idx, item in enumerate(raw[lang][:MAX_EXEMPLARS_PER_BUCKET]):
                norm = _normalize_exemplar_entry(item, idx)
                if norm:
                    entries.append(norm)
            if entries:
                out.setdefault("any", {})[lang] = entries
    # Tiered format: {"peer": {"zh": [...]}, "sharp": {"zh": [...]}, "calm": {"zh": [...]}}
    for tone in VALID_TONES:
        bucket = raw.get(tone)
        if not isinstance(bucket, dict):
            continue
        for lang in ("zh", "en"):
            if isinstance(bucket.get(lang), list):
                entries = []
                for idx, item in enumerate(bucket[lang][:MAX_EXEMPLARS_PER_BUCKET]):
                    norm = _normalize_exemplar_entry(item, idx)
                    if norm:
                        entries.append(norm)
                if entries:
                    out.setdefault(tone, {})[lang] = entries
    return out


def extract_exemplar_entities(
    text: str, lang: str, extra_terms: tuple | list | None = None, limit: int = 8
) -> list[str]:
    """Extract distinctive topic/entity terms from an exemplar so the model & leak guard keep topic separate from cadence."""
    import re

    entities: list[str] = []
    seen: set[str] = set()

    def _add(term: str) -> None:
        t = _sanitize_exemplar_text(str(term or "")).strip(" \t\r\n`'\"“”‘’()[]（）【】.,;:!?，。；：！？")
        if len(t) < 2 or len(entities) >= limit:
            return
        key = t.lower()
        if key in seen or key in _EN_EXEMPLAR_STOPWORDS or t in _ZH_EXEMPLAR_STOP_SUBSTRS:
            return
        seen.add(key)
        entities.append(t)

    # When explicit curated topic_terms are provided, trust them directly instead of blindly slicing prose
    if extra_terms:
        for t in extra_terms:
            _add(str(t))
        if entities:
            return entities[:limit]

    raw = text or ""
    for m in re.finditer(r"`([^`\n]{2,32})`", raw):
        _add(m.group(1))
    for m in re.finditer(r"\b(?:[A-Z]{2,}[0-9]*|[A-Z][a-z]+[A-Z][A-Za-z0-9]*|[a-z]+_[a-z0-9_]+|[A-Za-z]+\d+(?:\.\d+)*)\b", raw):
        _add(m.group(0))
    for m in re.finditer(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?(?:\s*(?:ms|s|kb|mb|gb|qps|rps|%|k|m|x|倍|万|千|人|行|天|小时|分钟|秒|端口))?\b", raw, re.IGNORECASE):
        if len(m.group(0).strip()) >= 2:
            _add(m.group(0))

    if lang == "en":
        words = re.findall(r"\b[A-Za-z][A-Za-z'-]{3,24}\b", raw)
        ranked = sorted(
            {w for w in words if w.lower() not in _EN_EXEMPLAR_STOPWORDS},
            key=lambda w: (-(1 if w[0].isupper() else 0), -len(w), w.lower()),
        )
        for w in ranked:
            _add(w)
    return entities[:limit]


def _exemplar_pool_for(cfg: dict, lang: str, tone: str) -> list[dict]:
    """Return user pack exemplars first (matching tone, then 'any'), falling back to built-in orthogonal exemplars."""
    custom = cfg.get("voice_exemplars") or {}
    out: list[dict] = []
    if isinstance(custom, dict):
        for key in (tone, "any"):
            bucket = custom.get(key)
            if isinstance(bucket, dict) and isinstance(bucket.get(lang), list):
                out.extend(bucket[lang])
    if out:
        return out
    builtin_lang = BUILTIN_VOICE_EXEMPLARS.get(lang) or {}
    return list(builtin_lang.get(tone) or builtin_lang.get("peer") or ())


def _select_voice_exemplar(
    cfg: dict,
    lang: str,
    tone: str,
    mode: str,
    prompt: str = "",
    used_ids: list[str] | None = None,
    blocked_ids: list[str] | None = None,
) -> dict | None:
    """Pick 1 orthogonal voice exemplar matching (tone, mode) with minimal prompt overlap and ring-buffer rotation."""
    pool = _exemplar_pool_for(cfg, lang, tone)
    if not pool:
        return None
    blocked = set(blocked_ids or ())
    candidates = [e for e in pool if e.get("id") not in blocked]
    if not candidates:
        candidates = list(pool)
    mode_matches = [e for e in candidates if mode in (e.get("modes") or CHAT_INTENT_MODES)]
    if mode_matches:
        candidates = mode_matches

    recent = set((used_ids or [])[-3:])
    fresh = [e for e in candidates if e.get("id") not in recent]
    if fresh:
        candidates = fresh

    prompt_low = (prompt or "").lower()

    def _overlap(entry: dict) -> tuple[int, int]:
        ents = extract_exemplar_entities(entry.get("text", ""), lang, entry.get("topic_terms"), limit=6)
        hits = sum(1 for t in ents if t.lower() in prompt_low) if prompt_low else 0
        recency = 1 if entry.get("id") in recent else 0
        return (hits, recency)

    chosen = min(candidates, key=_overlap)
    return chosen


def format_voice_exemplar_block(entry: dict, lang: str) -> str:
    text = str(entry.get("text") or "").strip()
    if not text:
        return ""
    entities = extract_exemplar_entities(text, lang, entry.get("topic_terms"), limit=5)
    if lang == "zh":
        guard = f"（防串题：只借节奏、短句落锤和体温，绝不带入「{'、'.join(entities)}」等题材词）" if entities else "（只借说话节奏、短句落锤和真实体温，绝不借它的题材）"
        return f'<voice_sample scope="cadence_only">\n{guard}\n{text}\n</voice_sample>'
    guard = f"(Cadence only: match spoken rhythm and warmth—never reuse topic nouns like {', '.join(entities)}.)" if entities else "(Cadence only: match spoken rhythm, short punches, and warmth—never its topic.)"
    return f'<voice_sample scope="cadence_only">\n{guard}\n{text}\n</voice_sample>'


def select_and_format_voice_sample(
    cfg: dict,
    lang: str,
    tone: str,
    mode: str,
    prompt: str = "",
    used_ids: list[str] | None = None,
    blocked_ids: list[str] | None = None,
) -> str:
    entry = _select_voice_exemplar(cfg, lang, tone, mode, prompt, used_ids=used_ids, blocked_ids=blocked_ids)
    return format_voice_exemplar_block(entry, lang) if entry else ""


def _clean_str_list(raw: object, limit: int = 64) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x).strip()[:200] for x in raw[:limit] if str(x).strip()]


def _clean_roles(raw: object) -> list[dict]:
    roles = []
    if not isinstance(raw, list):
        return roles
    for item in raw[:32]:
        if not isinstance(item, dict):
            continue
        policy = str(item.get("policy") or "default").strip().lower()
        if policy not in VALID_ROLE_POLICIES:
            continue
        match = item.get("match") if isinstance(item.get("match"), dict) else {}
        cleaned_match = {k: [s.lower() for s in _clean_str_list(match.get(k))] for k in ROLE_MATCH_KEYS}
        if not any(cleaned_match.values()):
            continue
        roles.append({"id": str(item.get("id") or policy)[:64], "policy": policy, "match": cleaned_match})
    return roles


def _merge_overlay(cfg: dict, overlay: dict, packs_loaded: list) -> None:
    """Merge one pack (or config.json) overlay into cfg: dicts merge, lists append, later wins."""
    name = overlay.get("name")
    if isinstance(name, str) and name.strip():
        packs_loaded.append(name.strip()[:64])

    raw_aliases = overlay.get("model_aliases")
    if isinstance(raw_aliases, dict):
        for k, v in raw_aliases.items():
            kl, vl = str(k).strip().lower(), str(v).strip().lower()
            if kl and vl in VALID_FAMILIES:
                cfg["model_aliases"][kl] = vl

    bypass = overlay.get("bypass") if isinstance(overlay.get("bypass"), dict) else {}
    for target_key, sources in (
        ("ignore_session_patterns", (overlay.get("ignore_session_patterns"), bypass.get("session_patterns"))),
        ("ignore_prompt_markers", (overlay.get("ignore_prompt_markers"), bypass.get("prompt_markers"))),
        ("ignore_system_markers", (overlay.get("ignore_system_markers"), bypass.get("system_markers"))),
    ):
        for src in sources:
            for item in _clean_str_list(src):
                if item not in cfg[target_key]:
                    cfg[target_key].append(item)

    for item in _clean_str_list(overlay.get("model_strip_patterns"), limit=MAX_STRIP_PATTERNS):
        if item not in cfg["model_strip_patterns"] and len(cfg["model_strip_patterns"]) < MAX_STRIP_PATTERNS:
            cfg["model_strip_patterns"].append(item)

    cfg["roles"].extend(_clean_roles(overlay.get("roles")))

    voice = _clean_text_map(overlay.get("voice"))
    if voice:
        cfg["voice"].update(voice)

    exemplars = _clean_voice_exemplars(overlay.get("voice_exemplars"))
    if exemplars:
        for bucket_key, lang_map in exemplars.items():
            cfg["voice_exemplars"].setdefault(bucket_key, {}).update(lang_map)

    raw_directives = overlay.get("directives")
    if isinstance(raw_directives, dict):
        for fam, texts in raw_directives.items():
            fam_l = str(fam).strip().lower()
            cleaned = _clean_text_map(texts)
            if fam_l in VALID_FAMILIES and cleaned:
                cfg["directives"].setdefault(fam_l, {}).update(cleaned)


def load_config() -> dict:
    cfg = {}
    for k, v in DEFAULT_CONFIG.items():
        if isinstance(v, dict):
            cfg[k] = {sk: (dict(sv) if isinstance(sv, dict) else list(sv) if isinstance(sv, list) else sv) for sk, sv in v.items()}
        elif isinstance(v, list):
            cfg[k] = list(v)
        else:
            cfg[k] = v
    cfg["packs_loaded"] = []
    scalar_keys = ("enabled", "tone", "language", "stop_guard", "max_stop_continuations", "epoch")

    # 1. Profile packs: scalar `defaults` apply only where config.json stays silent
    pack_defaults: dict = {}
    for path in _pack_candidate_paths():
        if not os.path.isfile(path):
            continue
        pack = _read_json_object(path, MAX_PACK_BYTES)
        if not pack or pack.get("schema") != PACK_SCHEMA:
            continue
        _merge_overlay(cfg, pack, cfg["packs_loaded"])
        defaults = pack.get("defaults")
        if isinstance(defaults, dict):
            for key in scalar_keys:
                if key in defaults and key != "epoch":
                    pack_defaults[key] = defaults[key]
    for key, val in pack_defaults.items():
        cfg[key] = val

    # 2. User config.json (first readable candidate) overrides pack defaults and extends pack lists
    candidates = []
    env_cfg = os.environ.get("UNARMORED_CONFIG")
    if env_cfg:
        candidates.append(env_cfg)
    state_override = os.environ.get("UNARMORED_STATE_DIR")
    if state_override:
        candidates.append(os.path.join(os.path.abspath(state_override), "config.json"))
    plugin_data = os.environ.get("PLUGIN_DATA")
    if plugin_data:
        candidates.append(os.path.join(os.path.abspath(plugin_data), "unarmored", "config.json"))
        candidates.append(os.path.join(os.path.abspath(plugin_data), "config.json"))
    if not state_override:
        candidates.append(os.path.join(_safe_user_home(), ".unarmored", "config.json"))
    candidates.append(os.path.join(_plugin_root(), "config.json"))

    for path in candidates:
        if path and os.path.isfile(path):
            loaded = _read_json_object(path)
            if loaded is None:
                continue
            for key in scalar_keys:
                if key in loaded:
                    cfg[key] = loaded[key]
            _merge_overlay(cfg, {k: v for k, v in loaded.items() if k != "name"}, cfg["packs_loaded"])
            break

    if cfg.get("tone") not in VALID_TONES:
        cfg["tone"] = "peer"
    if cfg.get("language") not in ("auto", "zh", "en"):
        cfg["language"] = "auto"
    cfg["enabled"] = bool(cfg.get("enabled", True))
    cfg["stop_guard"] = bool(cfg.get("stop_guard", True))
    try:
        cfg["max_stop_continuations"] = max(0, min(3, int(cfg.get("max_stop_continuations", 1))))
    except Exception:
        cfg["max_stop_continuations"] = 1
    try:
        cfg["epoch"] = int(cfg.get("epoch", 1))
    except Exception:
        cfg["epoch"] = 1
    overlay_view = {k: cfg[k] for k in ("model_aliases", "model_strip_patterns", "roles", "voice", "voice_exemplars", "directives")}
    cfg["overlay_sig"] = _short_hash(json.dumps(overlay_view, sort_keys=True, ensure_ascii=False))
    return cfg


def compile_strip_patterns(patterns: list[str]) -> list:
    if not patterns:
        return []
    import re

    compiled = []
    for pat in patterns[:MAX_STRIP_PATTERNS]:
        try:
            compiled.append(re.compile(pat, re.IGNORECASE))
        except re.error:
            continue
    return compiled


def set_active_strip_patterns(patterns: list[str]) -> None:
    global _ACTIVE_STRIP_PATTERNS
    _ACTIVE_STRIP_PATTERNS = compile_strip_patterns(patterns)


def directive_for(cfg: dict, family: str, lang: str) -> str:
    override = ((cfg.get("directives") or {}).get(family) or {}).get(lang)
    return override or MODEL_DIRECTIVES[family][lang]


def resolve_role(
    cfg: dict,
    agent_type: str = "",
    session_id: str = "",
    model: str = "",
    prompt: str = "",
    system_text: str = "",
) -> dict | None:
    """First pack role whose any match list hits wins. Matching is case-insensitive substring."""
    fields = {
        "agent_types": (agent_type or "").lower(),
        "session_patterns": (session_id or "").lower(),
        "models": (model or "").lower(),
        "prompt_markers": (prompt or "").lower(),
        "system_markers": (system_text or "").lower(),
    }
    for role in cfg.get("roles") or []:
        for key, needles in role.get("match", {}).items():
            hay = fields.get(key, "")
            if hay and any(n and n in hay for n in needles):
                return role
    return None


def _hits_prompt_or_system_bypass(prompt_text: str, cfg: dict, system_text: str = "") -> bool:
    if prompt_text:
        for marker in cfg.get("ignore_prompt_markers") or []:
            if marker and marker in prompt_text:
                return True
    if system_text:
        for marker in cfg.get("ignore_system_markers") or []:
            if marker and marker in system_text:
                return True
    return False


def should_bypass_session(session_id: str, prompt_text: str, cfg: dict, system_text: str = "") -> bool:
    sid_low = (session_id or "").strip().lower()
    if any(sid_low.startswith(p) for p in BUILTIN_IGNORE_SESSION_PREFIXES):
        return True
    for pat in cfg.get("ignore_session_patterns") or []:
        if pat.lower() in sid_low:
            return True
    return _hits_prompt_or_system_bypass(prompt_text, cfg, system_text)


def detect_host(payload: dict) -> str:
    if "hookEventName" in payload or "conversationId" in payload:
        return "antigravity"
    tpath = str(payload.get("transcript_path", "")).replace("\\", "/")
    event_name = str(payload.get("hook_event_name") or "")
    if event_name in ("PreModelSwitch", "PostModelSwitch", "PreCompact") or "/.claude/" in tpath:
        return "claude"
    if (
        "turn_id" in payload
        or payload.get("permission_mode") in ("on-request", "untrusted", "never", "danger-full-access")
        or "/.codex/" in tpath
    ):
        return "codex"
    if (
        os.environ.get("CLAUDE_PLUGIN_ROOT")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.environ.get("CLAUDE_ENV_FILE")
        or os.environ.get("CLAUDE_CONFIG_DIR")
    ):
        return "claude"
    sid = str(payload.get("session_id") or "")
    if sid and os.path.isfile(_session_state_path("claude", sid)) and not os.path.isfile(_session_state_path("codex", sid)):
        return "claude"
    if os.environ.get("CODEX_HOME") or os.environ.get("CODEX_SANDBOX"):
        return "codex"
    return "claude"


def _short_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:20]


def _session_state_path(host: str, session_id: str) -> str:
    key = _short_hash(f"{host}:{session_id or 'default'}")
    return os.path.join(_data_dir(), "sessions", f"{key}.json")


def load_session_state(host: str, session_id: str) -> dict:
    defaults = {
        "epoch": 0,
        "tone": "",
        "overlay_sig": "",
        "lang": "",
        "model_family": "",
        "inferred_family": "",
        "raw_model": "",
        "session_initialized": False,
        "flow_bypass": False,
        "allow_disk_edits": False,
        "last_role_policy": "default",
        "sticky_role_policy": "",
        "last_input_sig": "",
        "last_turn_id": "",
        "last_user_step_idx": -1,
        "last_mode": "PEER_SPAR",
        "injected_agy_mode": "",
        "last_scanned_resp_sig": "",
        "last_warned_resp_sig": "",
        "prev_opening_sig": "",
        "recent_openings": [],
        "rolling_smell_score": 0,
        "turn_stop_count": 0,
        "turn_count": 0,
        "refresh_idx": 0,
        "good_voice_anchor": None,
        "soft_tone_override": None,
        "used_exemplar_ids": [],
        "last_exemplar_id": "",
        "last_exemplar_entities": [],
        "last_exemplar_prompt": "",
        "blocked_exemplar_ids": [],
        "last_exemplar_turn": 0,
        "last_transcript_size": -1,
        "session_seed": int(_short_hash(f"{host}:{session_id or 'default'}")[:6], 16) % 97,
        "updated_at": 0,
    }
    path = _session_state_path(host, session_id)
    if os.path.isfile(path):
        loaded = _read_json_object(path, 32_768)
        if loaded is not None:
            merged = dict(defaults)
            merged.update(loaded)
            if not merged["recent_openings"] and merged.get("prev_opening_sig"):
                merged["recent_openings"] = [{"sig": str(merged["prev_opening_sig"]), "head": ""}]
            return merged
    return defaults


def save_session_state(host: str, session_id: str, state: dict) -> None:
    import tempfile
    import time

    now = int(time.time())
    state["updated_at"] = now
    path = _session_state_path(host, session_id)
    sessions_dir = os.path.dirname(path)
    tmp_name = ""
    try:
        os.makedirs(sessions_dir, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=".state.", suffix=".tmp", dir=sessions_dir)
        with os.fdopen(fd, "wb") as fh:
            fh.write(json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        os.replace(tmp_name, path)
        tmp_name = ""
        if (now & 31) == 0:
            for name in os.listdir(sessions_dir):
                if not (name.endswith(".json") or name.endswith(".tmp")):
                    continue
                fpath = os.path.join(sessions_dir, name)
                ttl = 300 if name.endswith(".tmp") else SESSION_TTL_SECONDS
                try:
                    if now - os.path.getmtime(fpath) > ttl:
                        os.remove(fpath)
                except OSError:
                    pass
    except OSError:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass


def normalize_model_leaf(model_str: str) -> str:
    """Apply pack route-wrapper strip patterns, then strip `auto/` prefixes and dated snapshot suffixes."""
    import re

    low = (model_str or "").strip().lower()[:MAX_MODEL_STRING]
    if not low:
        return ""
    for pat in _ACTIVE_STRIP_PATTERNS:
        try:
            stripped = pat.sub("", low).strip()
        except Exception:
            continue
        if stripped:
            low = stripped
    prefix, sep, leaf = low.rpartition("/")
    if sep and prefix == "auto":
        low = leaf
    low = re.sub(r"[-_.](?:20\d{2}[-_.]?(?:0[1-9]|1[0-2])[-_.]?(?:0[1-9]|[12]\d|3[01]))$", "", low)
    return low


def classify_model_family(model_str: str, custom_aliases: dict | None = None) -> str:
    if not model_str:
        return "generic"
    low = normalize_model_leaf(model_str)
    if not low or low in ("auto", "default", "none", "unknown") or low.startswith("group/"):
        return "generic"

    if custom_aliases:
        # Most specific (longest) alias wins, so `lane/deepseek-x` beats a shorter lane-name alias
        best_key, best_fam = "", ""
        for alias_key, target_fam in custom_aliases.items():
            if alias_key and alias_key in low and target_fam in VALID_FAMILIES and len(alias_key) > len(best_key):
                best_key, best_fam = alias_key, target_fam
        if best_fam:
            return best_fam

    if any(k in low for k in ("claude", "opus", "sonnet", "haiku", "anthropic")):
        return "claude"
    if any(k in low for k in ("gemini", "carbon", "argon", "hydrogen", "gemma")):
        return "gemini"
    if any(k in low for k in ("deepseek", "ds-v", "ds-r1")):
        return "deepseek"
    if any(k in low for k in ("grok", "x-ai/", "xai/")):
        return "grok"
    if any(k in low for k in ("qwen", "glm-", "zhipu", "kimi", "moonshot", "minimax", "doubao", "mimo-", "yi-")):
        return "cn_flagship"
    if any(k in low for k in ("gpt", "codex", "openai", "chatgpt")):
        return "gpt"
    import re

    if re.search(r"(?:^|[-_/:\s])o[1345](?:[-_a-z0-9]+|$)", low):
        return "gpt"
    return "generic"


def infer_family_from_smells(smells: list[str]) -> str:
    counts: dict[str, int] = {}
    for s in smells:
        fam = SMELL_FAMILY_MAP.get(s)
        if fam:
            counts[fam] = counts.get(fam, 0) + 1
    if not counts:
        return ""
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _read_tail_jsonl_with_meta(transcript_path: str, max_bytes: int = TRANSCRIPT_TAIL_BYTES) -> tuple[list, bool]:
    if not transcript_path or not os.path.isfile(transcript_path):
        return [], True
    try:
        size = os.path.getsize(transcript_path)
        if size <= 0:
            return [], True
        window = max_bytes
        reached_bof = False
        raw = b""
        with open(transcript_path, "rb") as fh:
            while True:
                if size <= window:
                    fh.seek(0)
                    raw = fh.read(size)
                    reached_bof = True
                    break
                fh.seek(size - window)
                chunk = fh.read(window)
                nl = chunk.find(b"\n")
                if nl != -1 and nl < len(chunk) - 1:
                    raw = chunk[nl + 1 :]
                    reached_bof = False
                    break
                if window >= 2_097_152:
                    raw = chunk if nl == -1 else chunk[nl + 1 :]
                    reached_bof = False
                    break
                window = min(2_097_152, window * 4)

        text = raw.decode("utf-8-sig", errors="replace")
        entries = []
        for line in text.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    entries.append(obj)
            except Exception:
                continue
        return entries, reached_bof
    except OSError:
        return [], True


def _read_tail_jsonl(transcript_path: str, max_bytes: int = TRANSCRIPT_TAIL_BYTES) -> list:
    entries, _ = _read_tail_jsonl_with_meta(transcript_path, max_bytes)
    return entries


def resolve_active_model(
    host: str, payload: dict, tail_entries: list | None = None, custom_aliases: dict | None = None
) -> tuple[str, str]:
    import re

    if host == "antigravity":
        hint = str(payload.get("modelName") or "").strip()
        if hint and hint.lower() not in ("auto", "none", "default"):
            fam = classify_model_family(hint, custom_aliases)
            if fam != "generic":
                return fam, hint
        entries = tail_entries if tail_entries is not None else _read_tail_jsonl(str(payload.get("transcriptPath") or ""))
        for entry in reversed(entries):
            if entry.get("type") == "USER_INPUT":
                content = str(entry.get("content") or "")
                if "<USER_SETTINGS_CHANGE>" in content and "Model Selection" in content:
                    m = re.search(
                        r"changed setting `Model Selection` from [^\r\n]{1,120}? to ([^\r\n]{1,120}?)(?:\.\s*(?:No need|$)|\r?\n|$)",
                        content,
                    )
                    if m:
                        chosen = m.group(1).strip().rstrip(".")
                        return classify_model_family(chosen, custom_aliases), chosen
        if hint:
            return classify_model_family(hint, custom_aliases), hint
        return "generic", "auto"

    for key in ("to_model", "model", "modelName"):
        val = str(payload.get(key) or "").strip()
        if val and val.lower() not in ("auto", "default", "none"):
            return classify_model_family(val, custom_aliases), val

    entries = tail_entries if tail_entries is not None else _read_tail_jsonl(str(payload.get("transcript_path") or ""))
    for entry in reversed(entries):
        etype = entry.get("type")
        sub = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
        if etype == "turn_context" and sub.get("model"):
            mname = str(sub["model"]).strip()
            return classify_model_family(mname, custom_aliases), mname
        msg = entry.get("message") if isinstance(entry.get("message"), dict) else (sub if sub else entry)
        mname = str(msg.get("model") or entry.get("model") or "").strip()
        if mname:
            return classify_model_family(mname, custom_aliases), mname
    return ("gpt", "codex-default") if host == "codex" else ("claude", "claude-default")


def extract_clean_user_text(raw_input: str) -> str:
    """Linear-time O(N) extraction with zero regex backtracking."""
    if not raw_input:
        return ""
    open_tag = "<USER_REQUEST>"
    close_tag = "</USER_REQUEST>"
    start = raw_input.find(open_tag)
    if start != -1:
        body_start = start + len(open_tag)
        end = raw_input.find(close_tag, body_start)
        if end != -1:
            return raw_input[body_start:end].strip()
        raw_input = raw_input[body_start:]

    out = raw_input
    for tag in _STRIP_XML_TAGS:
        ot = f"<{tag}>"
        ct = f"</{tag}>"
        while True:
            s_idx = out.find(ot)
            if s_idx == -1:
                break
            e_idx = out.find(ct, s_idx + len(ot))
            if e_idx == -1:
                out = out[:s_idx]
                break
            out = out[:s_idx] + " " + out[e_idx + len(ct) :]
    return out.strip()


def _infer_text_language(sample_text: str) -> str:
    if not sample_text:
        return ""
    for ch in sample_text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            return "zh"
    for ch in sample_text:
        if ("A" <= ch <= "Z") or ("a" <= ch <= "z"):
            return "en"
    return ""


_NEUTRAL_ACK_TOKENS = frozenset({"ok", "okay", "lgtm", "yes", "no", "y", "n", "go", "continue", "sure", "yep", "nope", "done", "next"})


def _is_language_neutral_turn(sample_text: str) -> bool:
    if not sample_text:
        return True
    prose, _ = _split_fenced_blocks(sample_text)
    stripped = prose.strip().strip(".!！。~～?？,，")
    if not stripped:
        return True
    low = stripped.lower()
    if low in _NEUTRAL_ACK_TOKENS:
        return True
    # Pure traceback paste (no CJK and matches trace_signal without normal conversational prose)
    if _infer_text_language(stripped) == "en" and _get_compiled_patterns()["trace_signal"].search(stripped):
        non_trace_lines = [
            ln.strip()
            for ln in stripped.splitlines()
            if ln.strip()
            and not ln.lstrip().startswith(("File ", "Traceback ", "at ", "Caused by:"))
            and not _get_compiled_patterns()["trace_signal"].search(ln)
        ]
        if not non_trace_lines:
            return True
    return False


def _extract_entry_user_text(entry: dict) -> str:
    etype = entry.get("type")
    if etype == "USER_INPUT" and entry.get("source") == "USER_EXPLICIT":
        return extract_clean_user_text(str(entry.get("content") or ""))
    sub = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
    msg = entry.get("message") if isinstance(entry.get("message"), dict) else (sub if sub else entry)
    role = str(msg.get("role") or entry.get("role") or etype or "").lower()
    if role == "user" or (etype == "event_msg" and sub.get("type") == "user_message"):
        raw_u = sub.get("message") if etype == "event_msg" else msg.get("content")
        if isinstance(raw_u, str) and raw_u.strip():
            return extract_clean_user_text(raw_u)
        if isinstance(raw_u, list):
            if any(isinstance(blk, dict) and blk.get("type") == "tool_result" for blk in raw_u):
                return ""
            parts = [
                str(blk["text"])
                for blk in raw_u
                if isinstance(blk, dict) and blk.get("type") in ("text", "input_text") and blk.get("text")
            ]
            if parts:
                return extract_clean_user_text("\n".join(parts))
    return ""


def detect_language(
    config_lang: str,
    sample_text: str,
    prev_lang: str = "",
    tail_entries: list | None = None,
) -> str:
    if config_lang in ("zh", "en"):
        return config_lang
    if prev_lang in ("zh", "en") and _is_language_neutral_turn(sample_text):
        return prev_lang
    direct = _infer_text_language(sample_text)
    if direct:
        return direct
    if prev_lang in ("zh", "en"):
        return prev_lang
    for entry in reversed(tail_entries or []):
        inferred = _infer_text_language(_extract_entry_user_text(entry))
        if inferred:
            return inferred
    return "zh"


def _split_fenced_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Linear-time O(N) CommonMark-compliant fenced code block splitter."""
    if not text:
        return "", []
    prose_lines: list[str] = []
    code_blocks: list[tuple[str, str]] = []
    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_lang = ""
    buf: list[str] = []

    for line in text.splitlines():
        lstripped = line.lstrip(" \t")
        indent = len(line) - len(lstripped)
        if not in_fence:
            if indent <= 3 and len(lstripped) >= 3 and lstripped[0] in ("`", "~"):
                ch = lstripped[0]
                run = 0
                for c in lstripped:
                    if c == ch:
                        run += 1
                    else:
                        break
                if run >= 3:
                    info = lstripped[run:].strip()
                    if not (ch == "`" and "`" in info):
                        in_fence = True
                        fence_char = ch
                        fence_len = run
                        fence_lang = info.split()[0].lower() if info else ""
                        buf = []
                        prose_lines.append("")
                        continue
            prose_lines.append(line)
        else:
            if indent <= 3 and lstripped.startswith(fence_char * fence_len):
                run = 0
                for c in lstripped:
                    if c == fence_char:
                        run += 1
                    else:
                        break
                if lstripped[run:].strip() == "":
                    code_blocks.append((fence_lang, "\n".join(buf)))
                    in_fence = False
                    fence_char = ""
                    fence_len = 0
                    fence_lang = ""
                    buf = []
                    continue
            buf.append(line)

    if in_fence and buf:
        code_blocks.append((fence_lang, "\n".join(buf)))

    return "\n".join(prose_lines), code_blocks


def _has_dramatic_bold_line(prose: str, bold_span_re) -> bool:
    for line in prose.splitlines():
        stripped = line.lstrip(" \t")
        if not stripped or stripped[0] in ("|", ">", "#"):
            continue
        if stripped.startswith(("- **", "* **", "+ **")) and (": " in stripped or "：" in stripped):
            continue
        if len(bold_span_re.findall(line)) >= 4:
            return True
    return False


def _opening_signature(prose: str) -> str:
    if not prose:
        return ""
    for line in prose.splitlines():
        s = line.strip()
        if not s or s[0] in ("#", "|", ">", "-", "*", "`"):
            continue
        norm = "".join(ch.lower() for ch in s[:32] if ch.isalnum())
        return norm[:20] if len(norm) >= 8 else ""
    return ""


_EN_ABBREVS = frozenset({
    "e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st",
    "fig", "eq", "no", "vol", "al", "inc", "ltd", "corp", "dept", "est", "approx",
    "cf", "viz", "ref", "sec", "ch", "pp", "jan", "feb", "mar", "apr", "jun",
    "jul", "aug", "sep", "sept", "oct", "nov", "dec", "u.s", "u.k", "a.m", "p.m",
})
_ZH_FUNC_STARTERS = frozenset({
    "对于", "关于", "这种", "这个", "这些", "我们", "他们", "可以", "需要", "应该",
    "如果", "虽然", "但是", "不过", "因为", "所以", "因此", "同时", "另外", "此外",
    "首先", "其次", "最后", "总之", "其实", "当然", "通常", "一般", "目前", "现在",
    "很多", "大多", "相比", "由于", "然而", "而且", "并且", "或者", "比如", "例如",
})
_CLOSING_QUOTE_CHARS = frozenset('”’」』）)】》"\')]')


def split_sentences(prose: str, *, skip_lists: bool = False) -> list[str]:
    """Strict O(N) bilingual sentence splitter with decimal/version/path/abbreviation protection."""
    if not prose:
        return []
    out: list[str] = []
    for raw_line in prose.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line[0] in ("#", "|", ">"):
            continue
        if all(ch in "-*_ \t" for ch in line) and len(line) >= 3:
            continue
        if skip_lists:
            if len(line) >= 2 and line[0] in ("-", "*", "+", "•") and line[1] in (" ", "\t"):
                continue
            j = 0
            while j < len(line) and line[j].isdigit():
                j += 1
            if j > 0 and j < len(line) - 1 and line[j] in (".", ")", "、") and line[j + 1] in (" ", "\t"):
                continue

        n = len(line)
        start = 0
        i = 0
        while i < n:
            ch = line[i]
            is_end = False
            if ch in ("。", "！", "？"):
                # Protect quoted or book-title punctuation followed by continuation clauses
                if i + 1 < n and line[i + 1] in ("”", "’", "」", "』", "》"):
                    after_q = i + 2
                    while after_q < n and line[after_q] in _CLOSING_QUOTE_CHARS:
                        after_q += 1
                    if after_q < n:
                        nxt = line[after_q]
                        if nxt in ("，", ",", "、", "；", ";", "：") or (line[i + 1] == "》" and not nxt.isspace()):
                            i = after_q
                            continue
                is_end = True
            elif ch in ("!", "?"):
                if ch == "!" and i + 1 < n and line[i + 1] == "=":
                    i += 1
                    continue
                if i + 1 == n or line[i + 1].isspace() or line[i + 1] in _CLOSING_QUOTE_CHARS:
                    is_end = True
            elif ch == ".":
                # Skip ellipsis run
                if i + 1 < n and line[i + 1] == ".":
                    while i + 1 < n and line[i + 1] == ".":
                        i += 1
                    i += 1
                    continue
                prev_ch = line[i - 1] if i > 0 else ""
                next_ch = line[i + 1] if i + 1 < n else ""
                # Protect line-leading numbered list prefix (`1. Sure, ...`)
                if start == 0 and prev_ch.isdigit() and line[:i].isdigit() and (not next_ch or next_ch.isspace()):
                    i += 1
                    continue
                # Protect decimals/versions (`3.14`, `v0.7.0`) and paths/attrs (`auth.py`, `os.path`)
                if prev_ch.isdigit() and next_ch.isdigit():
                    i += 1
                    continue
                if next_ch and not next_ch.isspace() and next_ch not in _CLOSING_QUOTE_CHARS:
                    i += 1
                    continue
                # Protect English abbreviations (`e.g.`, `Fig.`, `et al.`) and paired name initials (`J. K.`)
                tok_end = i
                tok_start = max(start, i - 8)
                k = tok_end - 1
                while k >= tok_start and (line[k].isalpha() or line[k] == "."):
                    k -= 1
                raw_token = line[k + 1 : tok_end]
                token = raw_token.lower().lstrip(".")
                if token in _EN_ABBREVS:
                    i += 1
                    continue
                if len(raw_token) == 1 and raw_token.isascii() and raw_token.isupper():
                    # Only treat as middle/first initial when preceded by whitespace/start and followed by another initial (`J. K.`)
                    j_next = i + 1
                    while j_next < n and line[j_next].isspace():
                        j_next += 1
                    if j_next + 1 < n and line[j_next].isupper() and line[j_next + 1] == ".":
                        i += 1
                        continue
                is_end = True

            if is_end:
                end = i + 1
                while end < n and line[end] in _CLOSING_QUOTE_CHARS:
                    end += 1
                seg = line[start:end].strip()
                if seg:
                    out.append(seg)
                start = end
                i = end
                continue
            i += 1

        tail = line[start:].strip()
        if tail:
            out.append(tail)
    return out


def _sentence_length_units(sent: str) -> float:
    """Bilingual sentence-length units: 1.0 per CJK char, 1.5 per ASCII word token."""
    cjk = 0
    en_words = 0
    in_word = False
    for ch in sent:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
            cjk += 1
            in_word = False
        elif ch.isascii() and (ch.isalnum() or ch in ("'", "-")):
            if not in_word:
                en_words += 1
                in_word = True
        else:
            in_word = False
    return cjk + en_words * 1.5


def extract_opener_key(sent: str) -> str:
    """Normalized sentence-opener fingerprint: first 2 EN words or first 2-3 CJK chars."""
    s = (sent or "").lstrip(" \t*_>#'\"“”‘’「」『』【】()[]《》-•")
    if not s:
        return ""
    o = ord(s[0])
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
        chars = []
        for ch in s[:12]:
            co = ord(ch)
            if 0x4E00 <= co <= 0x9FFF or 0x3400 <= co <= 0x4DBF:
                chars.append(ch)
                if len(chars) == 3:
                    break
            elif chars:
                break
        if len(chars) < 2:
            return ""
        head2 = "".join(chars[:2])
        if head2 in _ZH_FUNC_STARTERS or len(chars) == 2:
            return head2
        return "".join(chars[:3])
    words: list[str] = []
    cur: list[str] = []
    for ch in s[:48]:
        if ch.isascii() and (ch.isalnum() or ch == "'"):
            cur.append(ch.lower())
        elif cur:
            words.append("".join(cur))
            cur = []
            if len(words) == 2:
                break
    if cur and len(words) < 2:
        words.append("".join(cur))
    return " ".join(words) if words else ""


def _get_compiled_patterns() -> dict:
    global _COMPILED_PATTERNS
    if _COMPILED_PATTERNS is not None:
        return _COMPILED_PATTERNS
    import re

    fence_cliche_src = (
        r"各有(?:优劣|千秋|利弊|优缺点|所长)|没有(?:绝对|标准)的?(?:答案|好坏|对错)"
        r"|\bit depends\b|\bboth have (?:their )?(?:pros|merits|strengths)|\bthere(?:'|’)s no (?:one|single) right answer"
    )
    bare_go_explicit_src = (
        r"do\s+it|go\s+ahead|ship\s+it|implement\s+(?:it|that|option\s*[a-z1-9])|let'?s\s+do\s+it"
        r"|开干|开始吧|开始写吧|直接做|动手吧|就按(?:你说的|这个|方案\s*[A-Za-z1-9])(?:来|改|做)?"
    )
    file_target_src = (
        r"(?<![\w./\\-])[\w./\\-]{1,200}\.(?:py|ts|tsx|js|jsx|mjs|go|rs|java|c|cpp|h|css|scss|html|json|yaml|yml|toml|md|sh|ps1)\b"
    )
    hedge_soft_zh_src = r"(?:^|[。！？\n][ \t]*)(?:值得注意的是|不可否认的是|需要强调的是|需要明确的是)[，,：:]"
    hedge_hard_zh_src = (
        r"(?:^|[。！？\n][ \t]*)(?:总而言之|综上所述|归根结底|一言以蔽之)[，,：:]"
        r"|在当今(?:快速(?:演进|变化|发展)|瞬息万变)的[^，。\n]{1,15}(?:背景下|时代)"
    )
    hedge_soft_en_src = (
        r"(?:^|[.!?\n][ \t]*)(?:it(?:'s|\s+is)\s+(?:worth\s+noting|important\s+to\s+(?:note|remember|keep\s+in\s+mind))\s+that\b|here(?:'s|\s+is)\s+the\s+thing:)"
    )
    hedge_hard_en_src = (
        r"(?:^|[.!?\n][ \t]*)(?:in\s+(?:summary|conclusion),|all\s+in\s+all,|at\s+the\s+end\s+of\s+the\s+day,|in\s+today's\s+(?:fast-paced|rapidly\s+evolving)\b)"
    )

    _COMPILED_PATTERNS = {
        # Structural normalizers (disjoint character classes guarantee strict O(N) time on unclosed delimiters)
        "inline_code": re.compile(r"(`{1,4})([^`\r\n]{1,1000})\1"),
        "blockquote": re.compile(r"^[ \t]*>.*$", re.MULTILINE),
        "md_image_or_link": re.compile(
            r"!?\[([^\[\]\r\n]{0,300})\]\(([^()\s]{1,1000}(?:\([^()\s]{0,200}\)[^()\s]{0,500})?)\)"
        ),
        "prose_bang": re.compile(r"(?<![=!<>])[!！](?!=)"),
        # Document-in-chat tells (headings, stacked bold "label:" lines, dividers, meta-openers) and reflexive closing offers
        "md_heading": re.compile(r"^[ \t]{0,3}#{1,4}[ \t]+\S", re.MULTILINE),
        "md_divider": re.compile(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,}|(?:-[ \t]+){2,}-|(?:\*[ \t]+){2,}\*)[ \t]*$", re.MULTILINE),
        "blank_line": re.compile(r"\r?\n[ \t]*\r?\n"),
        "em_dash": re.compile(r"——|—"),
        # Strictly O(N) start-anchored (NO MULTILINE) so repeated newlines can never backtrack quadratically
        "meta_opening": re.compile(
            r"^(?:[ \t]*\r?\n){0,3}[ \t]*(?:(?:好的|行|明白)[，,：:\s]*)?\*{0,2}"
            r"(?:(?:这|以下)?(?:几个|[0-9]+|四|三|两|所有)?[个道]?问题(?:都)?不需要查资料"
            r"|直接(?:按顺序)?(?:回答|给(?:出)?结论|说结论)"
            r"|先(?:直接)?说结论|先给结论|结论先行"
            r"|简单说[：:]|一句话总结[：:]"
            r"|下面(?:我|直接)?(?:分点|按顺序)?(?:回答|说说)"
            r"|here\s+are\s+(?:my|the)\s+(?:direct\s+)?answers"
            r"|conclusion\s+first|short\s+answer\s*[:：]|tl;?dr\s*[:：]"
            r"|let\s+me\s+answer\s+(?:these|your\s+questions)\s+directly)[：:，,。\s]*\*{0,2}",
            re.IGNORECASE,
        ),
        "bold_label_line": re.compile(
            r"^[ \t]*(?:[-*][ \t]+)?(?:\*\*[^*\r\n]{1,24}[：:]\*\*|\*\*[^*\r\n]{1,24}\*\*[：:])", re.MULTILINE
        ),
        "standalone_bold_header": re.compile(
            r"^[ \t]*\*\*(?:[^*\r\n]{2,26}\*\*[ \t]*$|\d+[.、][ \t]*[^*\r\n]{2,24}\*\*)", re.MULTILINE
        ),
        "closing_offer": re.compile(
            r"(?:(?:(?:发|贴|丢)(?:给|过来|上来)?我|告诉我|说一下|补充一下|share|send|paste|tell me)[^。\n]{0,40}"
            r"(?:我(?:可以|来|帮你|陪你|再)|可以给你|帮你|I can|I(?:'|’)ll|happy to)"
            r"|(?:随时(?:告诉我|问我|联系我|补充)|有(?:任何)?问题随时|希望(?:这些|以上)(?:分析|建议|内容)?能帮(?:到)?你)"
            r"|\b(?:feel\s+free\s+to\s+(?:ask|share|reach\s+out|let\s+me\s+know)|let\s+me\s+know\s+if\s+you\s+have\s+any\s+(?:questions|follow-?ups?)|hope\s+this\s+helps)\b)",
            re.IGNORECASE,
        ),
        # Epistemic honesty marker: explicit speaker disclosure of unverified/unrun claims
        # (exempts soft caveats, NEVER hard corporate wrap-up cliches)
        "epistemic_honesty": re.compile(
            r"(?:(?:我|这边|目前|这一步|本地|手头|现在|暂时|还)?没(?:有)?(?:机会|来得及|实际|真实|在[^，。\n]{1,12})?(?:实)?(?:跑(?:过)?(?!偏|掉|路)|测(?:过|试)|验证(?:过)?|执行(?:过)?|压测(?:过)?|上机)"
            r"|没法(?:实测|实际(?:跑|测|验证)|验证|运行)"
            r"|未(?:实际|真实|经)(?:跑过|实测|上机|运行|测试|验证)"
            r"|只是静态(?:读代码|推断|估算|分析)|仅(?:凭|靠)(?:读)?代码(?:推断|估算|分析)"
            r"|\b(?:I|we)\s+(?:haven'?t|have\s+not|didn'?t|did\s+not)\s+(?:actually\s+|yet\s+)?(?:run|tested|verified|benchmarked|executed)\b"
            r"|\bwithout\s+(?:actually\s+)?(?:running|testing|executing)\b"
            r"|\bcode[- ]reading\s+only\b|\brough\s+estimate\b|\bfrom\s+(?:static\s+)?code\s+inspection\s+only\b)",
            re.IGNORECASE,
        ),
        # Defensive / sycophantic families (OR-Bench soft refusal, forced-choice fence-sitting, ELEPHANT validation)
        "disclaimer_boilerplate": re.compile(
            r"(?:请(?:务必)?咨询|建议(?:你)?(?:咨询|就医|寻求专业)|寻求专业(?:人士|帮助|意见)|我不是(?:医生|律师|理财师|专业)|"
            r"作为(?:一个)?(?:AI|人工智能)|不构成[^。\n]{0,8}(?:建议|意见)|不是(?:正式)?(?:法律|医疗|医学|投资|理财|专业)(?:意见|建议)|"
            r"一般性(?:的)?(?:法律|医疗|财务)信息|最好先(?:问|咨询)一下(?:医生|药师|律师)|"
            r"\bconsult (?:a|your) (?:doctor|physician|professional|lawyer|financial)|\bI(?:'|’)m not a (?:doctor|lawyer)|"
            r"\bnot (?:medical|legal|financial) advice\b|\bas an AI\b)",
            re.IGNORECASE,
        ),
        "disclaimer_soft": re.compile(r"(?:仅供参考|\bfor\s+reference\s+only\b)", re.IGNORECASE),
        "consultant_balance": re.compile(
            r"(?:不是(?:非黑即白|绝对对立)的?|寻找(?:一个)?(?:动态)?平衡点|在[^，。\n]{2,18}之间(?:找到|寻求|取得)平衡|"
            r"综合权衡|难分伯仲|不能一概而论|没有放之四海而皆准|"
            r"\b(?:while|whereas)\s+[A-Za-z0-9_.-]{1,24}\s+[^,.\n]{3,40}\b(?:offers|excels|shines)\b[^.\n]{0,40},\s*[A-Za-z0-9_.-]{1,24}\s+[^,.\n]{3,40}\b(?:provides|excels|shines)\b|"
            r"\bultimately,?\s+the\s+right\s+choice\s+(?:comes\s+down\s+to|depends\s+on)\b|"
            r"\bboth\s+[A-Za-z0-9_.-]{1,24}\s+and\s+[A-Za-z0-9_.-]{1,24}\s+are\s+(?:mature|excellent|solid|strong)\s+(?:choices|options|frameworks)\b)",
            re.IGNORECASE,
        ),
        "praise_then_pivot": re.compile(
            r"(?:你的(?:出发点|想法|思路|问题)(?:本身)?(?:很|非常|挺)?(?:好|合理|有道理|有价值)[^。\n]{0,20}(?:不过|但是|但)|"
            r"这是一个(?:很|非常)(?:有价值|值得深思|经典|常见)的(?:问题|讨论|话题)|"
            r"\bthat(?:'s|\s+is)\s+a\s+(?:great|fair|valid|thoughtful)\s+(?:point|question)[^.\n]{0,30}\b(?:however|though|that\s+said)\b)",
            re.IGNORECASE,
        ),
        "fence_sitting": re.compile(
            rf"(?:{fence_cliche_src}|取决于|看(?:你的|具体)?(?:需求|场景|情况|团队))",
            re.IGNORECASE,
        ),
        "fence_cliche": re.compile(rf"(?:{fence_cliche_src})", re.IGNORECASE),
        "clear_verdict": re.compile(
            r"(?:(?:^|[。！？\n，,][ \t]*)(?:直接|优先|还是|我会|建议)?(?:选(?![型择项哪什谁])|用(?![户于途法哪什不])|推荐|站(?![点位]))[ \t]*[A-Za-z0-9\u4e00-\u9fff]"
            r"|先留着|别动|直接上|首选|优先选|压根不该|完全没必要|绝对别|赶紧撤|别急着上|别碰"
            r"|别拆|不行|不建议(?!一概而论)|没必要|赶紧删|千万别"
            r"|(?:^|[.!?\n][ \t]*)(?:I(?:'d|[ \t]+would)[ \t]+)?(?:go[ \t]+with|stick[ \t]+with|keep[ \t]+the[ \t]+monolith|pick|choose|use|don'?t[ \t]+(?:use|split|bother)|avoid)\b)",
            re.IGNORECASE,
        ),
        "validation_template": re.compile(
            r"(?:你(?:做得)?没(?:有)?错|完全可以理解|你的(?:做法|反应|担心|感受)(?:是)?(?:很|非常|完全)?(?:合理|正常|可以理解)的?|"
            r"\byou(?:'|’)re not wrong\b|\byou are not wrong\b|\bNTA\b|\bcompletely understandable\b|\byour feelings are (?:valid|completely valid)\b)",
            re.IGNORECASE,
        ),
        "capitulation": re.compile(
            r"(?:你说得对|你是对的|抱歉[^。\n]{0,6}(?:我)?(?:记错|说错|搞错)|是我(?:记)?错了|感谢(?:你的)?(?:指正|纠正)|"
            r"\byou(?:'|’)re (?:absolutely )?right\b|\bI apologi[sz]e\b|\bmy mistake\b)",
            re.IGNORECASE,
        ),
        "bold_span": re.compile(r"\*\*[^*\n]{1,24}\*\*"),
        # Intent & pragmatic challenge patterns (strictly bounded, O(N) safe: never `\n\s*` or overlapping space classes)
        "discuss_guard": re.compile(
            r"\b(?:don'?t\s+(?:write|touch|edit|change|modify|apply)|no\s+(?:code|edits?)\s+yet|just\s+(?:ask|discuss|curious|brainstorm)|plan\s+only|(?:propose|outline)\s+a\s+plan)\b"
            r"|(?:先别(?:急着)?(?:改|动|写)|别急着(?:改|动|写)|不用写代码|别动(?:代码|文件)|不要(?:直接)?(?:改|动|写)(?:代码|文件)|先出(?:个)?方案|给我出(?:个)?[^，。\n]{0,16}方案|只(?:出|给)方案|只讨论|光聊聊|先分析下|先聊聊)",
            re.IGNORECASE,
        ),
        "challenge_guard": re.compile(
            r"\b(?:are\s+you\s+sure|is\s+that\s+(?:actually\s+)?(?:true|right|correct)|didn'?t\s+you\s+(?:mean|miss)|isn'?t\s+(?:it|this|that)\s+(?:actually|really)|shouldn'?t\s+(?:it|this|we))\b"
            r"|,[ \t]*right\??[ \t]*$"
            r"|(?:你确定(?:吗|[？?])?|真的(?:吗|是这样吗)|是不是(?:弄错|写错|搞反|看错)|难道不是|我记得应该是|不用[^？\n]{1,12}吧[？?！!。]*[ \t]*$"
            r"|(?:[^，。；\n？?\s][^，。；\n？?]{0,26}[^，。；\n？?\s]|[A-Za-z0-9\u4e00-\u9fff]{2})[，,]?[ \t]*(?:对吧|是吧|没错吧|没问题吧|是不是|对不对)[？?！!。]*[ \t]*$)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "trace_signal": re.compile(
            r"(?:Traceback \(most recent|\b[A-Za-z_]\w{0,60}(?:Error|Exception|Panic):|panic:|Segmentation fault|ERR!|exit (?:code|status) [1-9]|TS\d{4}:|E\d{4}:|\bat [\w.<>$]{1,120} \([^)\n]{1,240}:\d+:\d+\))"
        ),
        "concept_query_guard": re.compile(
            r"(?:(?:什么是|啥是)[^？?\n]{1,28}|介绍一下[^，。\n]{1,28}|怎么(?:评价|看待)|(?:如何|怎么)(?:杀掉|干掉|关闭|处理)[^，。\n]{1,20}"
            r"|\b(?:explain\s+(?:what|how|why)|what\s+is\s+(?:a\s+|an\s+|the\s+)?[A-Za-z0-9_.-]{2,40}|how\s+does\s+[\w.-]+\s+(?:work|handle))\b)",
            re.IGNORECASE,
        ),
        "frustration_bug": re.compile(
            r"\b(?:broken|still\s+(?:fails|failing|broken|wrong)|doesn'?t\s+work|regression|wtf|why\s+did\s+you|stop\s+(?:changing|rewriting)|revert|crash(?:ed|ing)?|hangs|stuck)\b"
            r"|(?:报错|(?:服务|进程|节点|容器|接口|程序|全站|线上|系统|机器|集群|任务|脚本|测试|流水线)[^，。\n]{0,6}挂了|(?<!心态)(?<!精神)(?<!快)(?<!快要)崩(?:了|溃了)|还是不行|又错了|没生效|死循环|卡死|乱改|谁让你|别乱动|回滚|怎么又)",
            re.IGNORECASE,
        ),
        "empathy_markers": re.compile(
            r"(?:(?:心态|精神|我快|快要)崩(?:了|溃)|好累|累死了|全盘否定|跟我吵|吵起来|玻璃心|是不是我不适合|我做得没错吧|拔了路由器|委屈|难受|烦死了|郁闷|焦虑|投了[^，。\n]{0,8}简历|面试[^，。\n]{0,8}挂|撑不住了|被骂了|背锅|"
            r"\b(?:exhausted|burnt\s+out|burned\s+out|am\s+i\s+wrong|they'?re\s+upset|argument\s+with|feeling\s+overwhelmed)\b)",
            re.IGNORECASE,
        ),
        "leading_exec": re.compile(
            r"^(?:请|帮我|帮忙|麻烦|现在|直接|please[ \t]+|can[ \t]+you[ \t]+|go[ \t]+ahead[ \t]+and[ \t]+)?"
            r"(?:修改|改动|改写|重构|修复|补全|补齐|完善|更新|新增|添加|加上|删掉|删除|移除|替换|提取|抽离|迁移|把[^，。？\n]{1,28}(?:改|换|调|加|补|删|移|重构|修复)"
            r"|\b(?:add|change|update|remove|delete|rename|refactor|implement|fix|wire|replace|move|extract|create|build|write|bump)\b)",
            re.IGNORECASE,
        ),
        "explain_markers": re.compile(
            r"(?:说人话[^。\n]{0,12}(?:解释|讲)|通俗(?:地)?(?:讲|解释)|解释一下|介绍一下[^，。\n]{1,28}|(?:什么是|啥是)[^？?\n]{1,28}|"
            r"(?:到底|究竟)(?:是|在说|干嘛|怎么回事|怎么工作|怎么实现)|原理是什么|区别是什么|讲清楚|"
            r"为什么[^，。\n]{1,50}(?:会|变差|变慢|不稳定|不行|需要)|"
            r"\b(?:explain\s+(?:how|what|why)|in\s+plain\s+english|eli5|what\s+is\s+(?:a\s+|an\s+|the\s+)?[A-Za-z0-9_.-]{2,40}|why\s+(?:does|do|is|are)\b|how\s+does\s+[\w.-]+\s+work|difference\s+between)\b)",
            re.IGNORECASE,
        ),
        "factual_binary_guard": re.compile(
            r"(?:True\s*还是\s*False|改写原列表|哪个会|哪一个会|返回什么|输出什么|\bonce\b[^?\n]{0,30}\bor\b)",
            re.IGNORECASE,
        ),
        "opinion_markers": re.compile(
            r"(?:技术短评|写一段[^。\n]{0,16}(?:短评|评论|观点)|观点明确|只能(?:选|推荐)一个|哪个更(?:好|强|稳|合适|划算)|哪个好用|选哪个|用哪个|"
            r"(?:吃|选|用)[^，。？\n]{1,24}还是[^，。？\n]{1,24}|适合[^，。？\n]{1,16}吗|要不要(?:上|用|拆|换|做|转|买|辞)|该不该|是不是该|"
            r"你怎么看|你觉得(?:怎么样|呢|行吗|这样写|行不行)|评价一下|锐评|点评一下|评审一下|看看这段(?:代码|摘要|话)|你看看[：:]|吐槽|合理吗|值不值得|值得吗|"
            r"\b(?:roast|hot\s+take|opinion\s+on|which\s+one\s+would\s+you\s+pick|pick\s+one|rate\s+this|critique|review\s+this|"
            r"should\s+(?:(?:a|an)\s+)?(?:(?:[0-9]+[- ]person|small|tiny|lean|early[- ]stage)\s+)?(?:we|i|teams?|startups?|solo\s+\w+|developers?|engineers?)\s+(?:use|write|adopt|switch|split|build|go)|is\s+it\s+worth)\b)",
            re.IGNORECASE,
        ),
        "bare_go_ahead_explicit": re.compile(rf"^(?:{bare_go_explicit_src})[.!！。~～]*$", re.IGNORECASE),
        "bare_go_ahead": re.compile(rf"^(?:ok|okay|lgtm|好|行|可以|{bare_go_explicit_src})[.!！。~～]*$", re.IGNORECASE),
        "exec_verbs": re.compile(
            r"\b(?:add|change|update|remove|delete|rename|refactor|implement|fix|wire|replace|move|extract|create|build|write|bump)\b"
            r"|(?:加个|加上|改成|修改|删掉|移除|重命名|实现|写个|直接做|开始做|重构|提取|新增|创建|补全|补齐|修复|完善|改写|替换|抽离|迁移|接入|帮我(?:改|写|加|删)|把[^，。？\n]{1,28}(?:改成|换成|调成|加上|补全|补齐|删掉|移除|重构|修复))",
            re.IGNORECASE,
        ),
        "file_targets": re.compile(file_target_src, re.IGNORECASE),
        "code_targets": re.compile(rf"(?:`[^`\n]{{1,200}}`|{file_target_src})", re.IGNORECASE),
        "spar_markers": re.compile(
            r"\b(?:should\s+(?:we|i)|thoughts\s+on|trade-?offs?|pros\s+and\s+cons|compare|vs\.?|versus|worth\s+it|architecture|brainstorm|how\s+would\s+you|what\s+do\s+you\s+think|sanity\s+check)\b"
            r"|(?:怎么看|选哪个|优缺点|权衡|有没有必要|值不值得|聊聊|讨论|设计方案|对比一下|如果[^？\n]{1,20}呢|你怎么想|分析一下)",
            re.IGNORECASE,
        ),
        # GPT family smells
        "gpt_neg_contrast_zh": re.compile(
            r"(?:(?:这|它|核心|关键|本质|真正的问题)(?:不仅仅|不只|不仅|并非简单|并非单纯|绝非)(?:在于|是)[^，。；\n]{1,35}[，；]\s*(?:更|而是|恰恰是|实则是)(?:在于|是|一[场次种个])"
            r"|(?<!如果)(?<!若)(?<!假如)(?:这|它|核心|本质)不是(?:简单|单纯)?的?[^，。；\n]{1,28}[，；]\s*而是(?:一[场次种个]|对|关于|为了)"
            r"|与其说(?:这|它)?是[^，。；\n]{1,28}[，,]\s*不如说是"
            r"|这并不意味着[^。；\n]{1,35}[；。]\s*(?:恰恰相反|相反[，,]))",
            re.MULTILINE,
        ),
        "gpt_neg_contrast_en": re.compile(
            r"\b(?:it(?:'s|\s+is)\s+not|(?:it|this|that)\s+isn't|(?:this|that)\s+is\s+not)\s+(?:just|merely|simply|only)\s+(?:about\s+)?[^—;.,\n]{2,55}"
            r"(?:(?:[—;,]|\.\s+)\s*(?:(?:it|this|that)(?:'s|\s+is)(?!\s+also\b)\s+(?:about\s+|rather\s+|a\s+|an\s+|the\s+)?|rather\s*,?\s*(?:it|this)\s+is\b))"
            r"|\bless\s+about\s+[^,;—.\n]{2,35},?\s+and\s+more\s+about\b",
            re.IGNORECASE | re.MULTILINE,
        ),
        "gpt_closing_menu_zh": re.compile(
            r"(?:如果你(?:需要|愿意|希望|想)|要是你需要|需要的话)[，,\s]*我(?:还可以|可以|能)(?:进一步|继续|顺便|帮你|为你)"
            r"|(?:需要我|要不要我)(?:顺便|进一步|继续|帮你)?(?:把|将|生成|写|补|整理|落地)"
            r"|你可以告诉我你更倾向于哪种(?:方案|方式|路线)[，,\s]*我(?:来|直接|马上)",
            re.MULTILINE,
        ),
        "gpt_closing_menu_en": re.compile(
            r"(?:^|\n)[ \t]*(?:if\s+you(?:'d\s+like|\s+want|\s+prefer),\s+I\s+can\b|would\s+you\s+like\s+me\s+to\b|let\s+me\s+know\s+if\s+you(?:'d\s+like|\s+want)\s+me\s+to\b|want\s+me\s+to\s+(?:also\s+)?(?:wire|implement|add|draft|write|generate|patch|update|turn\s+this)\b)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "gpt_hedging_soft_zh": re.compile(hedge_soft_zh_src, re.MULTILINE),
        "gpt_hedging_hard_zh": re.compile(hedge_hard_zh_src, re.MULTILINE),
        "gpt_hedging_wrapup_zh": re.compile(f"{hedge_soft_zh_src}|{hedge_hard_zh_src}", re.MULTILINE),
        "gpt_hedging_soft_en": re.compile(hedge_soft_en_src, re.IGNORECASE | re.MULTILINE),
        "gpt_hedging_hard_en": re.compile(hedge_hard_en_src, re.IGNORECASE | re.MULTILINE),
        "gpt_hedging_wrapup_en": re.compile(f"{hedge_soft_en_src}|{hedge_hard_en_src}", re.IGNORECASE | re.MULTILINE),
        "gpt_slop_lexicon": re.compile(
            r"\b(?:delve(?:s|d|ing)?|tapestry|testament\s+to|underscores?|pivotal\s+moment|indelible\s+mark|seamless(?:ly)?\s+integrat\w+)\b|(?:赋能|抓手|生态闭环|心智底座|组合拳)",
            re.IGNORECASE | re.MULTILINE,
        ),
        # Gemini family smells
        "gem_opening_flattery_zh": re.compile(
            r"^[ \t]*(?:\*\*[ \t]*)*(?:太(?:绝妙|精准|敏锐|精彩|惊艳|棒)了[！!。，]|(?:[^。！？\n]{0,35}(?:一针见血|敏锐地?(?:捕捉|指出|发现|洞察)|问到(?:了)?点子上|直觉(?:非常|极其|太)?(?:准|敏锐|毒辣)|抓(?:住|到)了(?:最)?核心|极其(?:深刻|敏锐|精彩)的(?:问题|洞察|观察|切入点))))"
        ),
        "gem_opening_flattery_en": re.compile(
            r"^[ \t]*(?:\*\*[ \t]*)*(?:that(?:'s|\s+is)\s+(?:a\s+|an\s+|such\s+a\s+)?(?:\*\*)?(?:brilliant|fantastic|phenomenal|spot-on|astute|stellar|genius|incredible)(?:\*\*)?\s+(?:question|observation|insight|catch|point)|you(?:'ve|\s+have)\s+hit\s+the\s+nail\s+(?:right\s+)?on\s+the\s+head|what\s+an?\s+(?:\*\*)?(?:brilliant|astute|insightful|fantastic)(?:\*\*)?\s+(?:question|catch|observation)|bingo[!.,])",
            re.IGNORECASE,
        ),
        "gem_hyperbole_zh": re.compile(
            r"(?:降维打击|直击灵魂|史诗级|神来之笔|教科书级(?:别)?|核武器级|令人叹为观止|王炸级?|手术刀般(?:精准|锐利)?|定海神针|系好安全带|(?:简直是?|真是|堪称)[^，。；\n]{0,10}(?:彻头彻尾|绝妙|完美闭环|质的飞跃|艺术品))",
            re.MULTILINE,
        ),
        "gem_hyperbole_en": re.compile(
            r"\b(?:masterclass|game-chang(?:ing|er)|chef's\s+kiss|mind-blowing|pure\s+magic|paradigm\s+shift|surgical\s+precision|buckle\s+up)\b|here(?:'s|\s+is)\s+where\s+the\s+magic\s+happens|let(?:'s|\s+us)\s+dive\s+right\s+in!",
            re.IGNORECASE | re.MULTILINE,
        ),
        # Claude family smells
        "claude_preachy_zh": re.compile(
            r"(?:在(?:这样|这么|动手|开始|继续)做之前[，,\s]*(?:我们)?不妨(?:先)?(?:思考|审视|问自己|停下来)"
            r"|需要指出的是[，,\s]*(?:这种|该|直接)[^。；\n]{0,20}(?:做法|方式|方案|操作)"
            r"|虽然我理解你(?:想|希望|为什么)[^，。\n]{1,35}[，,]\s*但(?:我们必须|值得(?:怀疑|商榷|警惕)|我必须提醒|更审慎的做法)"
            r"|从(?:工程伦理|安全合规|最佳实践|长远维护)的角度(?:来看)?[，,\s]*我(?:必须|有必要|需要|不得不)提醒"
            r"|请务必确保你(?:拥有|已获得)[^。！\n]{2,25}(?:授权|许可)"
            r"|与其直接(?:修改|绕过|禁用)[^，。\n]{1,20}[，,]\s*我们更应该(?:审视|反思))",
            re.MULTILINE,
        ),
        "claude_preachy_en": re.compile(
            r"(?:before\s+we\s+(?:proceed|dive\s+in|write\s+any\s+code|implement\s+this),\s+it(?:'s|\s+is)\s+worth\s+(?:pausing\s+to\s+)?(?:consider|question|ask)(?:ing)?"
            r"|while\s+I\s+understand\s+(?:why\s+you|your\s+desire\s+to)[^,.\n]{2,50},\s+it(?:'s|\s+is)\s+worth\s+questioning"
            r"|I(?:'d|\s+would)\s+gently\s+push\s+back\s+on"
            r"|I\s+feel\s+obligated\s+to\s+point\s+out"
            r"|please\s+ensure\s+you\s+have\s+(?:explicit\s+|proper\s+)?authorization\s+before"
            r"|a\s+word\s+of\s+caution\s+before\s+(?:using|deploying|running))",
            re.IGNORECASE | re.MULTILINE,
        ),
        "claude_apology_pivot_zh": re.compile(
            r"^\s*(?:你说得(?:完全|太|非常)(?:正确|对)[！!。，]|非常抱歉(?:我之前|刚才)的(?:疏忽|失误|误解)|完全是我的(?:疏忽|失误)[，！!。]|感谢你的指正[，,]\s*我刚才确实)"
        ),
        "claude_apology_pivot_en": re.compile(
            r"^\s*(?:you(?:'re|\s+are)\s+(?:absolutely|completely|entirely|totally)\s+right[!.,—]|my\s+apologies\s+for\s+(?:the|that)\s+(?:oversight|confusion|mistake)|I\s+apologize\s+for\s+(?:that\s+oversight|missing\s+that|the\s+confusion))",
            re.IGNORECASE,
        ),
        "claude_solemn": re.compile(
            r"(?:让我们退一步(?:来)?(?:思考|审视)|这触及了(?:一个)?更深层的(?:架构|设计|哲学)命题|\blet(?:'s|\s+us)\s+take\s+a\s+step\s+back\s+and\s+(?:examine|reflect|question)\b|\bthis\s+speaks\s+to\s+a\s+deeper\s+(?:architectural\s+|design\s+)?tension\b)",
            re.IGNORECASE | re.MULTILINE,
        ),
        # Grok & Structural Slop smells
        "grok_forced_banter": re.compile(
            r"(?:\b(?:buckle\s+up,\s+buttercup|grab\s+your\s+popcorn|plot\s+twist:|spoiler\s+alert:|no\s+cap,\s+this\s+is)\b|(?:坐稳扶好|搬好小板凳|前方高能|不装了[，,]?摊牌了))",
            re.IGNORECASE,
        ),
        "struct_copula_puffery": re.compile(
            r"(?:作为[^，。；\n]{2,22}的(?:核心|重要|关键)(?:载体|基石|抓手|支柱|枢纽)|扮演着[^，。；\n]{2,20}的(?:重要|核心|关键)角色|\b(?:serves\s+as\s+a\s+(?:vital|pivotal|crucial|key|cornerstone)|stands\s+as\s+a\s+(?:testament|beacon|cornerstone)|plays\s+a\s+(?:pivotal|vital|paramount)\s+role\s+in)\b)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "struct_participial_tail": re.compile(
            r"(?:[，,]\s*(?:从而(?:有效)?(?:实现了|确保了|构建了|赋能了)[^。；\n]{2,25}(?:闭环|升级|跃升|演进)|进而为[^。；\n]{2,22}奠定(?:了)?坚实基础)|,\s*(?:highlighting\s+the\s+(?:critical\s+|vital\s+)?importance\s+of|ensuring\s+seamless\s+\w+|fostering\s+a\s+(?:culture|sense|more)\s+of|underscoring\s+the\s+need\s+for)\b)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "academic_self_sabotage": re.compile(
            r"(?:虽然(?:本方法|我们的方法|该方案)[^，。\n]{2,25}[，,]\s*但(?:必须承认|不可讳言|遗憾的是)[^。；\n]{2,30}(?:效果有限|仍显不足|尚未充分)|\bwhile\s+our\s+(?:method|approach)\s+[^,.\n]{2,35},\s+we\s+must\s+(?:admit|acknowledge)\s+that\s+its\s+(?:effectiveness|impact)\s+is\s+limited\b)",
            re.IGNORECASE | re.MULTILINE,
        ),
        # DeepSeek & Stop-gate laziness smells (strict O(N): never two adjacent space quantifiers around an optional group)
        "ds_lazy_code_comment": re.compile(
            r"^[ \t]*(?://+|#+|/\*+|<!--|--)[ \t]*(?:(?:\.{2,}|…)[ \t]*)?(?:其余(?:代码|部分|逻辑|内容|字段|方法|实现)?(?:保持不变|不变|同上|省略|略)"
            r"|(?:原有|现有|其他|未修改|上面|下面)(?:的)?(?:代码|逻辑|部分|内容|方法)(?:保持不变|不变|同上|省略|略)"
            r"|此处省略|代码略|省略(?:其余|其他|部分|未改动)"
            r"|TODO[:：\s]*(?:自行|请自行|在此|这里)(?:实现|补充|完善|编写)"
            r"|(?:rest\s+of\s+(?:the\s+)?(?:code|file|class|function|methods?|implementation)|existing\s+(?:code|implementation|imports|methods)|previous\s+(?:code|implementation)|unchanged\s+code)(?:\s+(?:remains?\s+(?:the\s+same|unchanged)|here|omitted))?"
            r"|omitted\s+for\s+brevity|keep\s+existing\s+(?:code|markup)\s+here|implement\s+(?:remaining\s+)?logic\s+yourself)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "ds_standalone_ellipsis": re.compile(
            r"^[ \t]*(?:\.{3}|…)[ \t]*(?:(?://|#|/\*|<!--).*)?$",
            re.MULTILINE,
        ),
        "ds_prose_handwave": re.compile(
            r"(?:限于篇幅[，,\s]*(?:这里|此处|本文)?(?:不再|不予|就?不)(?:赘述|展开|详述|一一列出)"
            r"|(?:其余|其他|剩下)的?[^，。；\n]{1,25}(?:逻辑(?:类似|相同)|写法一致|同理)[，,\s]*(?:你可以|请|可)?自行(?:补全|实现|完善|修改)"
            r"|同理可推其余(?:模块|文件|接口)"
            r"|for\s+brevity(?:'s\s+sake)?,\s+I(?:'ve|\s+have)\s+omitted"
            r"|I(?:'ll|\s+will)\s+leave\s+the\s+remaining\s+(?:boilerplate|implementation|files|methods)\s+(?:to\s+you|as\s+an\s+exercise)"
            r"|you\s+can\s+apply\s+this\s+same\s+pattern\s+to\s+the\s+remaining\s+\w+\s+yourself)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "ds_plan_only_stop": re.compile(
            r"(?:(?:接下来|下面|现在)(?:我将|我会|让我们|我们先)(?:按以下步骤|开始|先)?(?:查看|读取|检查|修改|实现|编写|运行|执行)"
            r"|(?:第一步|首先)[，,：:\s]*(?:我们先|让我先|我先)(?:查看|读取|定位|修改)"
            r"|\blet(?:'s|\s+us)\s+(?:start|begin)\s+by\s+(?:reading|checking|inspecting|looking\s+at)\b"
            r"|\bI\s+will\s+now\s+(?:read|inspect|modify|update|implement|run)\b"
            r"|\bfirst,\s+let\s+me\s+(?:check|read|inspect)\b)",
            re.IGNORECASE | re.MULTILINE,
        ),
        "unapplied_code_claim": re.compile(
            r"(?:修改后的(?:完整)?代码如下|已为你(?:修改|重构|实现)如下|完整实现代码如下|下面是(?:改好|修改后|完整)的代码|把(?:文件|它)改成下面这样|可直接替换为(?:以下|下面)代码"
            r"|here\s+is\s+the\s+updated\s+(?:file|code|implementation)|replace\s+it\s+with\s+the\s+following\s+code)",
            re.IGNORECASE,
        ),
        "blocked_exemption": re.compile(
            r"\b(?:BLOCKED|CAPTCHA|Turnstile|reCAPTCHA|permission\s+denied|access\s+denied|authentication\s+required|missing\s+credentials|please\s+confirm|awaiting\s+(?:your\s+)?(?:approval|confirmation)|before\s+proceeding|confirm\s+before|verify\s+you\s+are\s+human)\b"
            r"|(?:人机验证|缺少权限|无法访问|请提供|确认后继续|等你(?:先)?确认|请(?:先)?确认(?:是否|后)?|需要你拍板|是否继续执行|要不要继续执行|需要(?:先)?登录|登录态(?:已)?失效|缺少登录态)",
            re.IGNORECASE,
        ),
        # v0.7 Level-2 & Bidirectional Overcorrection detectors (strictly O(N), zero nested quantifiers)
        "cn_idiom_bureaucratese": re.compile(
            r"(?:行稳致远|相辅相成|循序渐进|相得益彰|不言而喻|统筹兼顾|从长远来看|综合权衡|提质增效|高屋建瓴|未雨绸缪|因地制宜)"
        ),
        "cn_grand_wrapup": re.compile(
            r"(?:不仅是一次[^，。；\n]{1,22}更是(?:一[次场种个])?|才是真正的[^，。；\n]{1,14}(?:智慧|之道|核心|底气)|方能(?:行稳致远|立于不败|长治久安))"
        ),
        "overcorrection_archaic_strong": re.compile(
            r"\b(?:heretofore|forthwith|thusly|hitherto|perchance|verily|betwixt)\b"
            r"|(?:盖因|由是观之|窃以为|不啻为|实乃|大抵如是|非也[，。！])",
            re.IGNORECASE,
        ),
        "overcorrection_archaic_mild": re.compile(
            r"\b(?:whilst|thereof|herein|hereof|notwithstanding|whereby|henceforth|aforementioned|inasmuch\s+as|moreover\s+herein)\b"
            r"|(?:诚然[，,]?|殊不知|抑或是?|姑且不论|岂非|何其|诚如所言)",
            re.IGNORECASE,
        ),
        "overcorrection_snark": re.compile(
            r"(?:纯属(?:智商税|扯淡|胡扯|垃圾|废话)|一坨(?:屎|答辩|垃圾)|脑子(?:进水|有坑)|笑死(?:我了)?|什么年代了还|闭眼都能写|菜到抠脚|纯粹是(?:垃圾|灾难|笑话)|写得像屎一样)"
            r"|\b(?:complete\s+garbage|utter\s+trash|total\s+nonsense|absolute\s+joke|laughably\s+bad|dogshit|bullshit|brain[- ]dead|dumpster\s+fire|train\s*wreck|pure\s+idiocy)\b",
            re.IGNORECASE,
        ),
        "concrete_grounding_num": re.compile(
            r"(?<![A-Za-z0-9])\d+(?:\.\d+)?[ \t]*(?:ms|s|kb|mb|gb|qps|rps|%|x|倍|万|千|人|行|毫秒|秒|个|天|小时|分钟)\b|\bO\([^)\n]{1,12}\)|\bHTTP[ \t]*[45]\d\d\b",
            re.IGNORECASE,
        ),
        "concrete_grounding_causal": re.compile(
            r"(?:因为|导致|会触发|根因|瓶颈|延迟|死锁|竞态|内存泄漏|超时|击穿|阻塞|集成测试|回归|模块切分|连接池|空指针|并发|事务|幂等"
            r"|\b(?:because|causes|triggers|bottleneck|latency|deadlock|race\s+condition|memory\s+leak|timeout|global\s+state|idempotency|retry|side\s+effect|swallows?|mutates?)\b)",
            re.IGNORECASE,
        ),
    }
    return _COMPILED_PATTERNS


def _bound_prose_window(prose_full: str, limit: int = 4000) -> str:
    half = limit // 2
    return prose_full if len(prose_full) <= limit else (prose_full[:half] + "\n" + prose_full[-half:])


def is_epistemic_challenge(raw_user_input: str) -> bool:
    clean = extract_clean_user_text(raw_user_input)
    if not clean:
        return False
    prose, _ = _split_fenced_blocks(clean)
    return bool(_get_compiled_patterns()["challenge_guard"].search(_bound_prose_window(prose.strip())))


def allows_disk_edits(raw_user_input: str, mode: str) -> bool:
    if mode not in ("SURGICAL_EXEC", "DEBUG_RECOVERY"):
        return False
    clean = extract_clean_user_text(raw_user_input)
    if not clean:
        return True
    prose_raw, _ = _split_fenced_blocks(clean)
    prose = _bound_prose_window(prose_raw.strip())
    if not prose:
        return True
    if _get_compiled_patterns()["discuss_guard"].search(prose):
        return False
    return True


def classify_intent(raw_user_input: str, prev_mode: str = "PEER_SPAR") -> str:
    clean = extract_clean_user_text(raw_user_input)
    if not clean:
        return prev_mode or "PEER_SPAR"
    pats = _get_compiled_patterns()
    prose_raw, fenced_blocks = _split_fenced_blocks(clean)
    code_blob = "\n".join(body for _, body in fenced_blocks)
    prose_full = prose_raw.strip()
    # Bound intent scan window to head+tail so 80k-char pasted dumps stay sub-5ms
    prose = _bound_prose_window(prose_full, 4000)
    code_probe = _bound_prose_window(code_blob, 8000)

    if pats["discuss_guard"].search(prose):
        return "PEER_SPAR"

    if pats["trace_signal"].search(code_probe) or pats["trace_signal"].search(prose):
        return "DEBUG_RECOVERY"

    # Explicit leading execution command targeting a real file wins over secondary explanatory/opinion clauses
    # (e.g. "Update cache.py to explain what went wrong..." and bilingual equivalents)
    has_file_target = bool(pats["file_targets"].search(prose))
    if has_file_target and pats["leading_exec"].search(prose):
        return "SURGICAL_EXEC"

    # Without traceback, explicit conceptual/how-to queries ("Explain what a regression test is", etc.)
    # must NOT be hijacked into DEBUG_RECOVERY by generic bug terms like 'regression'/'revert'/'stuck'.
    if pats["concept_query_guard"].search(prose):
        if pats["explain_markers"].search(prose):
            return "EXPLAIN_DEEP"
        if pats["opinion_markers"].search(prose) and not pats["factual_binary_guard"].search(prose):
            return "CRITIQUE_OPINION"
        return "PEER_SPAR"

    # Real bug/incident frustration always takes precedence over emotional venting
    if pats["frustration_bug"].search(prose):
        return "DEBUG_RECOVERY"

    # Emotional / interpersonal venting without file targets
    if pats["empathy_markers"].search(prose) and not has_file_target:
        return "EMPATHY_VENT"

    if prev_mode in CHAT_INTENT_MODES:
        if pats["bare_go_ahead_explicit"].match(prose):
            return "SURGICAL_EXEC"
        if prev_mode == "PEER_SPAR" and pats["bare_go_ahead"].match(prose):
            return "SURGICAL_EXEC"

    # Explicit explanation / opinion / critique prompts win over accidental backtick-term verbs (e.g. "`add` and `norm`")
    if pats["explain_markers"].search(prose):
        return "EXPLAIN_DEEP"
    if pats["opinion_markers"].search(prose) and not pats["factual_binary_guard"].search(prose):
        return "CRITIQUE_OPINION"

    has_code_target = bool(pats["code_targets"].search(prose))
    exec_score = 0
    spar_score = 0
    if pats["exec_verbs"].search(prose):
        exec_score += 2
    if has_file_target:
        exec_score += 2
    elif has_code_target and exec_score > 0:
        exec_score += 1

    if pats["spar_markers"].search(prose) or pats["factual_binary_guard"].search(prose):
        spar_score += 3
    if "?" in prose or "？" in prose:
        spar_score += 1

    if spar_score >= exec_score and spar_score > 0:
        return "PEER_SPAR"
    if exec_score >= 2:
        return "SURGICAL_EXEC"
    return prev_mode or "PEER_SPAR"


def _has_guarded_standalone_ellipsis(lang_hint: str, code_body: str, ellipsis_re) -> bool:
    lang = (lang_hint or "").strip().lower()
    if not lang or lang in _NON_CODE_FENCE_LANGS:
        return False
    lines = code_body.splitlines()
    is_python = lang in ("py", "python", "python3")
    for idx, line in enumerate(lines):
        if not ellipsis_re.match(line):
            continue
        if is_python:
            prev_sig = ""
            for j in range(idx - 1, -1, -1):
                stripped = lines[j].strip()
                if stripped and not stripped.startswith("#"):
                    prev_sig = stripped
                    break
            if prev_sig.endswith(":"):
                continue
        return True
    return False


def _extract_patch_added_code(patch_text: str) -> list[tuple[str, str]]:
    added_blocks: list[tuple[str, str]] = []
    cur_ext = ""
    cur_lines: list[str] = []
    for line in patch_text.splitlines():
        if line.startswith(("*** Update File:", "*** Add File:", "+++ ")):
            if cur_lines:
                added_blocks.append((cur_ext, "\n".join(cur_lines)))
                cur_lines = []
            target = line.split(":", 1)[-1].strip() if ":" in line else line[4:].strip()
            cur_ext = os.path.splitext(target)[1].lstrip(".").lower() or "code"
            continue
        if line.startswith("+") and not line.startswith("+++"):
            cur_lines.append(line[1:])
    if cur_lines:
        added_blocks.append((cur_ext or "code", "\n".join(cur_lines)))
    return added_blocks


def _extract_tool_code_blocks(tool_calls: list | None) -> list[tuple[str, str]]:
    tool_blocks: list[tuple[str, str]] = []
    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue
        tname = str(call.get("name") or call.get("tool_name") or "").lower()
        raw_args = call.get("args") if "args" in call else (call.get("arguments") if "arguments" in call else call.get("input"))
        if "apply_patch" in tname and isinstance(raw_args, str) and raw_args.strip():
            tool_blocks.extend(_extract_patch_added_code(raw_args))
            continue
        args = raw_args
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {}
        if not isinstance(args, dict):
            continue
        path_hint = str(args.get("Path") or args.get("path") or args.get("file_path") or "")
        ext = os.path.splitext(path_hint)[1].lstrip(".").lower() or "code"
        if any(k in tname for k in ("write", "edit", "replace", "patch", "create")):
            for field in ("Content", "Replacement", "content", "new_str", "new_string", "file_text", "patch"):
                val = args.get(field)
                if isinstance(val, str) and val.strip():
                    if field == "patch" or "apply_patch" in tname:
                        tool_blocks.extend(_extract_patch_added_code(val))
                    else:
                        tool_blocks.append((ext, val))
    return tool_blocks


def _strip_prose_noise(prose: str, pats: dict) -> str:
    if not prose:
        return ""
    prose = pats["inline_code"].sub(" ", prose)
    prose = pats["md_image_or_link"].sub(r"\1", prose)
    prose = pats["blockquote"].sub("", prose)
    return prose.strip()


def split_two_streams(content: str, tool_calls: list | None = None) -> tuple[str, list[tuple[str, str]]]:
    pats = _get_compiled_patterns()
    prose, code_blocks = _split_fenced_blocks(content)
    code_blocks.extend(_extract_tool_code_blocks(tool_calls))
    return _strip_prose_noise(prose, pats), code_blocks


TRANSITION_SCAFFOLD_MIN = 4
_STANCE_PATTERNS = None


def _get_stance_patterns() -> dict:
    """Heuristic lexicons after Hyland's (2005) interpersonal metadiscourse model. Detector-only: never injected."""
    global _STANCE_PATTERNS
    if _STANCE_PATTERNS is not None:
        return _STANCE_PATTERNS
    import re

    sent_start = r"(?:^|[。！？!?；;\n][ \t]*|\.[ \t]+)"
    _STANCE_PATTERNS = {
        # Discourse-initial frame/transition markers (the formulaic connective scaffold)
        "transitions": re.compile(
            sent_start
            + r"(?:首先|其次|再次|此外|另外值得一提的是|值得注意的是|需要注意的是|值得一提的是|综上所述|总而言之|总的来说|"
            r"不仅如此|与此同时|更重要的是|由此可见|最后[，,]|"
            r"Furthermore|Moreover|Additionally|In addition|In conclusion|Overall|It(?:'|’)s worth noting|"
            r"Notably|Importantly|Ultimately|Firstly|Secondly|Lastly|Finally,)",
            re.MULTILINE,
        ),
        "hedges": re.compile(
            r"(?:可能|也许|或许|大概|似乎|一般来说|在一定程度上|倾向于|"
            r"\b(?:might|may|perhaps|possibly|likely|seems?|tends? to|generally|arguably)\b)",
            re.IGNORECASE,
        ),
        "boosters": re.compile(
            r"(?:显然|明显|毫无疑问|无疑|必然|肯定|确实|"
            r"\b(?:clearly|obviously|definitely|certainly|undoubtedly|indeed)\b)",
            re.IGNORECASE,
        ),
        "attitude": re.compile(
            r"(?:遗憾的是|可惜|意外|没想到|别扭|离谱|好消息是|麻烦的是|有意思的是|挺坑|难受|漂亮|糟糕|头疼|添堵|痛快|窝火|气笑|吃亏|划不来|折腾|"
            r"\b(?:unfortunately|surprisingly|interestingly|frankly|sadly|annoyingly|nicely|awkward|ugly|painful|clunky|brittle|overkill|neat|messy)\b)",
            re.IGNORECASE,
        ),
        "self_mention": re.compile(r"(?:我(?!们)|我们|\b(?:I|we|my|our)\b)"),
        "self_mention_singular": re.compile(r"(?:我(?!们)|咱(?!们)|\b(?:I|my|me)\b)"),
        "spoken_pivot": re.compile(
            r"(?:说白了|说穿了|讲真|说实话|其实|压根|干脆|撑死|顶多|动不动|硬要|何必|别说|反过来|真要|但凡|要是|哪怕|省得|免得|搞不好|一上来|回头|顺手|兜底|踩坑|掉坑|扯皮|背锅|拍脑袋|凑合|卡死|白给|没戏|算了|得了吧|行不通|绕弯|鸡肋|眼下[？?]|你想啊|换我)"
            r"|\b(?:honestly|frankly|plainly|realistically|basically|the\s+catch|the\s+trap|pain\s+point|footgun|headache|don't|doesn't|won't|isn't|aren't|can't|couldn't|wouldn't|shouldn't|it's|that's|you'll|we're|they're|i'd)\b",
            re.IGNORECASE,
        ),
        "textbook_frames": re.compile(
            r"(?:在[^，。\n]{1,10}(?:方面|层面|维度|场景下|背景下)|从[^，。\n]{1,10}(?:角度|层面|维度)(?:来看|出发|而言)|(?:核心|主要|关键)(?:在于|优势在于|挑战在于|特点包括)|(?:从而|进而)(?:提升|提高|降低|增强|优化|改善|实现|保障)|与此同时|需要指出的是|值得注意的是|一般来说|通常情况下|总体而言|综上所述|在此基础上|相应地|换言之)"
            r"|\b(?:in\s+terms\s+of|from\s+a\s+[a-z]{2,18}\s+(?:perspective|standpoint)|with\s+respect\s+to|in\s+this\s+context|as\s+a\s+result|consequently|furthermore|moreover|additionally|meanwhile|in\s+general|typically|broadly\s+speaking|it\s+is\s+(?:important|essential|crucial|useful)\s+to|enables?\s+(?:teams|organizations|developers|systems)\s+to|plays?\s+a\s+key\s+role)\b",
            re.IGNORECASE,
        ),
    }
    return _STANCE_PATTERNS


def stance_profile(prose: str) -> dict:
    """Counts, per-1000-char densities, and zero-dep bilingual cadence metrics on a prose stream."""
    import math

    pats = _get_stance_patterns()
    text = prose or ""
    size = max(len(text), 1)
    out: dict = {"chars": len(text)}
    for key, pat in pats.items():
        n = len(pat.findall(text))
        out[key] = n
        out[f"{key}_per_k"] = round(n * 1000 / size, 2)

    # Bound pure-Python char-level sentence cadence scan on huge adversarial payloads (O(1) upper bound)
    cadence_text = text if len(text) <= 12_000 else (text[:6_000] + "\n" + text[-6_000:])
    sents = split_sentences(cadence_text, skip_lists=True)
    lengths = [_sentence_length_units(s) for s in sents]
    valid_pairs = [(s, u) for s, u in zip(sents, lengths) if u >= 3.0]
    valid_lens = [u for _, u in valid_pairs]
    sent_count = len(valid_lens)
    out["sent_count"] = sent_count
    if sent_count >= 1:
        mean_len = sum(valid_lens) / sent_count
        out["sent_len_mean"] = round(mean_len, 2)
    else:
        mean_len = 0.0
        out["sent_len_mean"] = None
    if sent_count >= 2 and mean_len > 0:
        var = sum((x - mean_len) ** 2 for x in valid_lens) / sent_count
        out["sent_len_cv"] = round(math.sqrt(var) / mean_len, 3)
    else:
        out["sent_len_cv"] = None
    # Short punch count: crisp 3..12 CJK-equivalent units (e.g. 4-12 Chinese chars or 3-8 English words)
    out["short_punch_count"] = sum(1 for u in valid_lens if 3.0 <= u <= 12.0)

    all_sents = split_sentences(cadence_text, skip_lists=False)
    openers = [k for k in (extract_opener_key(s) for s in all_sents) if k]
    if len(openers) >= 3:
        counts: dict[str, int] = {}
        for k in openers:
            counts[k] = counts.get(k, 0) + 1
        out["opener_diversity"] = round(len(counts) / len(openers), 3)
        out["max_opener_repeat"] = max(counts.values())
    else:
        out["opener_diversity"] = None
        out["max_opener_repeat"] = max((1 for _ in openers), default=0)
    return out


def _is_code_or_debug_exempt(content: str, prose: str, prose_code_blocks: list, mode: str, pats: dict) -> bool:
    if mode in ("SURGICAL_EXEC", "DEBUG_RECOVERY"):
        return True
    non_doc_blocks = [b for lang_h, b in prose_code_blocks if lang_h not in _DOC_FENCE_LANGS]
    if len(non_doc_blocks) >= 2:
        return True
    code_chars = sum(len(b) for b in non_doc_blocks)
    if content and code_chars / max(len(content), 1) >= 0.35:
        return True
    if prose and pats["trace_signal"].search(prose):
        return True
    return False


def _count_concrete_grounding(content: str, prose: str, code_blocks: list, pats: dict) -> int:
    """Count concrete factual/technical grounding signals (0..4) to distinguish substantiated critique from empty snark."""
    score = 0
    if code_blocks or len(pats["inline_code"].findall(content or "")) >= 2:
        score += 1
    if pats["file_targets"].search(content or "") or pats["trace_signal"].search(content or ""):
        score += 1
    if pats["concrete_grounding_num"].search(prose or ""):
        score += 1
    if pats["concrete_grounding_causal"].search(prose or ""):
        score += 1
    return score


def _has_wall_of_text(prose: str, blank_line_re) -> bool:
    """Detect any single unbroken prose brick (>=320 CJK-dominant chars or >=700 non-CJK chars)."""
    for raw_p in blank_line_re.split(prose):
        p = raw_p.strip()
        if len(p) < 320:
            continue
        if p[0] in ("-", "*", "+", "|", "#", ">") or (p[0].isdigit() and ". " in p[:5]):
            continue
        if p.count("\n") >= 2:
            continue
        cjk = sum(1 for ch in p if 0x4E00 <= ord(ch) <= 0x9FFF or 0x3400 <= ord(ch) <= 0x4DBF)
        limit = 320 if cjk >= 20 else 700
        if len(p) >= limit:
            return True
    return False


def _has_lazy_code_in_blocks(blocks: list[tuple[str, str]], pats: dict) -> bool:
    for lang, code_body in blocks:
        if lang in _DOC_FENCE_LANGS:
            continue
        if pats["ds_lazy_code_comment"].search(code_body) or _has_guarded_standalone_ellipsis(
            lang, code_body, pats["ds_standalone_ellipsis"]
        ):
            return True
    return False


def analyze_response_smells(
    content: str,
    tool_calls: list | None = None,
    prev_opening_sig: str = "",
    *,
    mode: str = "",
    recent_openings: list | None = None,
    tone: str = "peer",
) -> dict:
    """Scan assistant response via orthogonal prose_stream, code_stream, and bilingual cadence metrics."""
    pats = _get_compiled_patterns()
    prose_raw, prose_code_blocks = _split_fenced_blocks(content)
    prose = _strip_prose_noise(prose_raw, pats)
    tool_code_blocks = _extract_tool_code_blocks(tool_calls)
    code_blocks = list(prose_code_blocks) + tool_code_blocks

    head_window = prose[:240]
    tail_window = prose[-450:] if len(prose) > 450 else prose
    scan_prose = prose if len(prose) <= 24_000 else (prose[:12_000] + "\n" + prose[-12_000:])
    cur_opening_sig = _opening_signature(prose)
    all_sents = split_sentences(scan_prose[:12_000], skip_lists=False) if scan_prose else []
    cur_opening_head = extract_opener_key(all_sents[0]) if all_sents else ""

    smells: list[tuple[str, int]] = []
    has_honesty = bool(scan_prose and pats["epistemic_honesty"].search(scan_prose))
    stance = stance_profile(scan_prose) if scan_prose else stance_profile("")
    overcorrection_kind = ""

    if scan_prose:
        if pats["gpt_neg_contrast_zh"].search(scan_prose) or pats["gpt_neg_contrast_en"].search(scan_prose):
            smells.append(("gpt_neg_contrast", 1))
        if pats["gpt_closing_menu_zh"].search(tail_window) or pats["gpt_closing_menu_en"].search(tail_window):
            smells.append(("gpt_closing_menu", 2))
        has_hard_hedge = bool(pats["gpt_hedging_hard_zh"].search(scan_prose) or pats["gpt_hedging_hard_en"].search(scan_prose))
        has_soft_hedge = bool(pats["gpt_hedging_soft_zh"].search(scan_prose) or pats["gpt_hedging_soft_en"].search(scan_prose))
        if has_hard_hedge or (not has_honesty and has_soft_hedge):
            smells.append(("gpt_hedging_wrapup", 1))
        em_dashes = len(pats["em_dash"].findall(scan_prose))
        if pats["gpt_slop_lexicon"].search(scan_prose) or em_dashes >= 6:
            smells.append(("gpt_slop_lexicon", 1))
        if pats["consultant_balance"].search(scan_prose):
            smells.append(("consultant_balance", 2))
        if pats["praise_then_pivot"].search(head_window):
            smells.append(("praise_then_pivot", 1))

        if pats["gem_opening_flattery_zh"].search(head_window) or pats["gem_opening_flattery_en"].search(head_window):
            smells.append(("gem_opening_flattery", 2))
        if pats["gem_hyperbole_zh"].search(scan_prose) or pats["gem_hyperbole_en"].search(scan_prose):
            smells.append(("gem_hyperbole", 1))
        bang_count = len(pats["prose_bang"].findall(scan_prose))
        has_double_bang = ("!!" in scan_prose) or ("！！" in scan_prose) or ("!！" in scan_prose) or ("！!" in scan_prose)
        if _has_dramatic_bold_line(scan_prose, pats["bold_span"]) or has_double_bang or bang_count >= 4 or (bang_count >= 3 and len(prose) < 260):
            smells.append(("gem_dramatic_bold", 1))

        if pats["claude_preachy_zh"].search(scan_prose) or pats["claude_preachy_en"].search(scan_prose):
            smells.append(("claude_preachy", 2))
        if pats["claude_apology_pivot_zh"].search(head_window) or pats["claude_apology_pivot_en"].search(head_window):
            smells.append(("claude_apology_pivot", 2))
        if pats["claude_solemn"].search(scan_prose):
            smells.append(("claude_solemn", 1))

        if pats["grok_forced_banter"].search(scan_prose):
            smells.append(("grok_forced_banter", 2))

        if (
            all(tok in scan_prose for tok in ("首先，", "其次，", "最后，"))
            and ("综上所述" in scan_prose or "总而言之" in scan_prose)
            and len(prose) < 1200
        ):
            smells.append(("cn_report_scaffold", 2))

        idiom_hits = len(pats["cn_idiom_bureaucratese"].findall(scan_prose))
        if idiom_hits >= 2 or pats["cn_grand_wrapup"].search(scan_prose):
            smells.append(("cn_idiom_bureaucratese", 2))

        if pats["struct_copula_puffery"].search(scan_prose):
            smells.append(("struct_copula_puffery", 1))
        if pats["struct_participial_tail"].search(scan_prose):
            smells.append(("struct_participial_tail", 1))
        if pats["academic_self_sabotage"].search(scan_prose):
            smells.append(("academic_self_sabotage", 2))

        # 3-turn sliding window cross-turn opener repeat (backward-compatible with single prev_opening_sig)
        window_openings = list(recent_openings or [])
        if not window_openings and prev_opening_sig:
            window_openings = [{"sig": prev_opening_sig, "head": ""}]
        sig_repeat = bool(cur_opening_sig and any(cur_opening_sig == str(e.get("sig") or "") for e in window_openings[-3:]))
        head_repeat = bool(
            len(cur_opening_head) >= 2
            and sum(1 for e in window_openings[-3:] if cur_opening_head == str(e.get("head") or "")) >= 2
        )
        if sig_repeat or head_repeat:
            smells.append(("cross_turn_repeat", 2))

        if pats["ds_prose_handwave"].search(scan_prose):
            smells.append(("ds_prose_handwave", 2))

        if stance["transitions"] >= TRANSITION_SCAFFOLD_MIN:
            smells.append(("transition_scaffold", 1))

        if pats["meta_opening"].search(prose[:160]):
            smells.append(("meta_opening", 1))

        if len(pats["md_divider"].findall(scan_prose)) >= 2 and len(prose) < 2500:
            smells.append(("divider_spam", 1))

        # Chat answered as a document: markdown headings, bold "label:" lines, or standalone bold pseudo-headers
        doc_marks = (
            len(pats["md_heading"].findall(scan_prose)) * 2
            + len(pats["bold_label_line"].findall(scan_prose))
            + len(pats["standalone_bold_header"].findall(scan_prose))
        )
        if doc_marks >= 3 and len(prose) < 2500:
            smells.append(("doc_format_in_chat", 1))

        # Unbroken wall-of-text prose brick (per-paragraph, CJK >=320 / non-CJK >=700)
        if _has_wall_of_text(scan_prose, pats["blank_line"]):
            smells.append(("wall_of_text", 1))

        if pats["closing_offer"].search(prose[-320:]):
            smells.append(("closing_offer", 1))

        if pats["disclaimer_boilerplate"].search(scan_prose) or (not has_honesty and pats["disclaimer_soft"].search(scan_prose)):
            smells.append(("disclaimer_boilerplate", 1))

        has_cliche = bool(pats["fence_cliche"].search(scan_prose))
        has_verdict = bool(pats["clear_verdict"].search(prose[:320]))
        fence_hits = len(pats["fence_sitting"].findall(scan_prose))
        if has_cliche and not has_verdict:
            smells.append(("fence_sitting", 2))
        elif fence_hits >= 2 and (has_cliche or (not has_verdict and not has_honesty)):
            smells.append(("fence_sitting", 1))

        if pats["validation_template"].search(head_window):
            smells.append(("validation_template", 1))

        # v0.7 Level-2 cadence & bloodless-textbook detectors (strictly exempt on code/debug turns)
        code_or_debug_exempt = _is_code_or_debug_exempt(content, scan_prose, prose_code_blocks, mode, pats)
        if not code_or_debug_exempt:
            sent_n = int(stance["sent_count"])
            cv = stance["sent_len_cv"]
            mean_len = stance["sent_len_mean"] or 0.0
            opener_div = stance["opener_diversity"]
            if sent_n >= 5 and mean_len >= 10.0 and cv is not None and cv < 0.18:
                smells.append(("monotone_cadence", 1))

            para_openers = []
            for raw_p in pats["blank_line"].split(scan_prose):
                p = raw_p.strip()
                if not p or p[0] in ("-", "*", "+", "|", "#", ">"):
                    continue
                pk = extract_opener_key(p)
                if pk:
                    para_openers.append(pk)
            para_rep = len(para_openers) >= 3 and (len(para_openers) - len(set(para_openers))) >= 2
            max_rep = int(stance["max_opener_repeat"])
            sent_rep = len(all_sents) >= 5 and (
                (opener_div is not None and opener_div < 0.65)
                or (max_rep >= 3 and (max_rep / len(all_sents)) >= 0.45)
            )
            if sent_rep or para_rep:
                smells.append(("repetitive_openers", 1))

            # Flat bloodless textbook/op-ed prose (exempt on calm tone & short honest disclosures;
            # requires at least 1 explicit textbook/transition framing cue so crisp technical explanations stay clean)
            if tone != "calm" and not (has_honesty and len(prose) < 450):
                cjk_n = sum(1 for ch in scan_prose[:2000] if 0x4E00 <= ord(ch) <= 0x9FFF)
                min_flat_len = 150 if cjk_n >= 40 else 420
                zero_pulse = (
                    stance["attitude"] == 0
                    and stance["spoken_pivot"] == 0
                    and stance["self_mention_singular"] == 0
                )
                has_textbook_scaffold = stance["textbook_frames"] >= 2 or stance["transitions"] >= 2
                if sent_n >= 4 and len(prose) >= min_flat_len and zero_pulse and has_textbook_scaffold:
                    dry_cues = 0
                    if cv is not None and cv < 0.28:
                        dry_cues += 1
                    if stance["short_punch_count"] == 0 and "?" not in scan_prose and "？" not in scan_prose and "!" not in scan_prose and "！" not in scan_prose:
                        dry_cues += 1
                    if (stance["hedges"] >= 2 and stance["boosters"] == 0) or (opener_div is not None and opener_div < 0.72):
                        dry_cues += 1
                    if dry_cues >= 1:
                        smells.append(("flat_textbook_voice", 1))

        # Bidirectional Overcorrection Drift detector (archaisms exempted on code/debug specs; snark requires weak grounding)
        strong_arch = len(pats["overcorrection_archaic_strong"].findall(scan_prose))
        mild_arch = len(pats["overcorrection_archaic_mild"].findall(scan_prose))
        is_archaic = (not code_or_debug_exempt) and (strong_arch >= 1 or (strong_arch + mild_arch) >= 2)
        snark_hits = len(pats["overcorrection_snark"].findall(scan_prose))
        grounding = _count_concrete_grounding(content, scan_prose, code_blocks, pats) if snark_hits else 0
        is_snark = (snark_hits >= 1 and grounding == 0) or (snark_hits >= 2 and grounding <= 1) or snark_hits >= 3
        if is_archaic or is_snark:
            overcorrection_kind = "both" if (is_archaic and is_snark) else ("archaic" if is_archaic else "snark")
            smells.append(("overcorrection_drift", 2))

    tool_lazy = _has_lazy_code_in_blocks(tool_code_blocks, pats)
    prose_lazy = _has_lazy_code_in_blocks(prose_code_blocks, pats)
    if tool_lazy or prose_lazy:
        smells.append(("ds_lazy_code", 2))

    # Order smells by descending severity weight while preserving detection order within ties
    smells_ordered = sorted(enumerate(smells), key=lambda item: (-item[1][1], item[0]))
    ordered_pairs = [pair for _, pair in smells_ordered]
    total_score = sum(weight for _, weight in ordered_pairs)
    return {
        "score": total_score,
        "smells": [name for name, _ in ordered_pairs],
        "prose": prose,
        "code_blocks": code_blocks,
        "prose_code_blocks": prose_code_blocks,
        "opening_sig": cur_opening_sig,
        "opening_head": cur_opening_head,
        "tool_lazy_code": tool_lazy,
        "prose_lazy_code": prose_lazy,
        "has_honesty": has_honesty,
        "overcorrection_kind": overcorrection_kind,
        "stance": stance,
    }


def extract_smell_spans(content: str, report: dict | None = None) -> list[dict]:
    """Read-only span locator for CLI `--pretty` & HTML report highlighting (never called on hook hot path)."""
    rep = report if report is not None else analyze_response_smells(content or "")
    prose_full = rep.get("prose") or ""
    prose = prose_full[:24_000]
    active = set(rep.get("smells") or ())
    if not prose or not active:
        return []
    pats = _get_compiled_patterns()
    stance_pats = _get_stance_patterns()
    has_honesty = bool(rep.get("has_honesty"))
    raw_spans: list[dict] = []

    def _add(smell: str, start: int, end: int) -> None:
        if 0 <= start < end <= len(prose):
            raw_spans.append({
                "smell": smell,
                "weight": SMELL_DEFAULT_WEIGHTS.get(smell, 1),
                "start": start,
                "end": end,
                "snippet": prose[start:end][:120],
            })

    pattern_map = {
        "gpt_neg_contrast": ("gpt_neg_contrast_zh", "gpt_neg_contrast_en"),
        "gpt_closing_menu": ("gpt_closing_menu_zh", "gpt_closing_menu_en"),
        "gpt_hedging_wrapup": ("gpt_hedging_hard_zh", "gpt_hedging_hard_en") if has_honesty else ("gpt_hedging_hard_zh", "gpt_hedging_hard_en", "gpt_hedging_soft_zh", "gpt_hedging_soft_en"),
        "gpt_slop_lexicon": ("gpt_slop_lexicon",),
        "consultant_balance": ("consultant_balance",),
        "praise_then_pivot": ("praise_then_pivot",),
        "gem_opening_flattery": ("gem_opening_flattery_zh", "gem_opening_flattery_en"),
        "gem_hyperbole": ("gem_hyperbole_zh", "gem_hyperbole_en"),
        "claude_preachy": ("claude_preachy_zh", "claude_preachy_en"),
        "claude_apology_pivot": ("claude_apology_pivot_zh", "claude_apology_pivot_en"),
        "claude_solemn": ("claude_solemn",),
        "grok_forced_banter": ("grok_forced_banter",),
        "cn_idiom_bureaucratese": ("cn_idiom_bureaucratese", "cn_grand_wrapup"),
        "struct_copula_puffery": ("struct_copula_puffery",),
        "struct_participial_tail": ("struct_participial_tail",),
        "academic_self_sabotage": ("academic_self_sabotage",),
        "ds_prose_handwave": ("ds_prose_handwave",),
        "meta_opening": ("meta_opening",),
        "divider_spam": ("md_divider",),
        "doc_format_in_chat": ("md_heading", "bold_label_line", "standalone_bold_header"),
        "closing_offer": ("closing_offer",),
        "disclaimer_boilerplate": ("disclaimer_boilerplate",) if has_honesty else ("disclaimer_boilerplate", "disclaimer_soft"),
        "fence_sitting": ("fence_cliche", "fence_sitting"),
        "validation_template": ("validation_template",),
        "overcorrection_drift": ("overcorrection_archaic_strong", "overcorrection_archaic_mild", "overcorrection_snark"),
    }
    for smell, pkeys in pattern_map.items():
        if smell not in active:
            continue
        for pk in pkeys:
            for m in pats[pk].finditer(prose):
                _add(smell, m.start(), m.end())
                if len(raw_spans) >= 40:
                    break
    if "transition_scaffold" in active:
        for m in stance_pats["transitions"].finditer(prose):
            _add("transition_scaffold", m.start(), m.end())
    if "flat_textbook_voice" in active:
        found = False
        for m in stance_pats["textbook_frames"].finditer(prose):
            _add("flat_textbook_voice", m.start(), m.end())
            found = True
        if not found:
            _add("flat_textbook_voice", 0, min(len(prose), 80))
    if "wall_of_text" in active:
        _add("wall_of_text", 0, min(len(prose), 90))
    if "monotone_cadence" in active:
        _add("monotone_cadence", 0, min(len(prose), 80))
    if "repetitive_openers" in active:
        sents = split_sentences(prose, skip_lists=False)
        keys = [extract_opener_key(s) for s in sents]
        counts: dict[str, int] = {}
        for k in keys:
            if k:
                counts[k] = counts.get(k, 0) + 1
        cursor = 0
        for s, k in zip(sents, keys):
            pos = prose.find(s[:16], cursor)
            if pos >= 0:
                cursor = pos + len(s[:16])
                if k and counts.get(k, 0) >= 2:
                    _add("repetitive_openers", pos, min(len(prose), pos + max(len(k), 6)))

    # Deduplicate overlapping spans (keep higher weight / earlier start)
    raw_spans.sort(key=lambda sp: (sp["start"], -sp["weight"], -(sp["end"] - sp["start"])))
    merged: list[dict] = []
    for sp in raw_spans:
        if not merged or sp["start"] >= merged[-1]["end"]:
            merged.append(sp)
    return merged[:24]


def _parse_claude_or_codex_entry(entry: dict) -> tuple[str, str, list[dict]]:
    etype = str(entry.get("type") or "")
    sub = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}

    if etype == "event_msg" and sub.get("type") == "user_message":
        return "user_turn", str(sub.get("message") or ""), []

    if etype == "response_item" and sub:
        stype = str(sub.get("type") or "")
        if stype in ("function_call", "custom_tool_call"):
            raw_arg = sub.get("arguments") if "arguments" in sub else sub.get("input")
            return "assistant", "", [{"name": sub.get("name", ""), "args": raw_arg or {}}]
        if stype == "message":
            role = str(sub.get("role") or "").lower()
            cval = sub.get("content")
            if role == "user":
                return "user_turn", "", []
            if role == "assistant":
                texts = []
                if isinstance(cval, str):
                    texts.append(cval)
                elif isinstance(cval, list):
                    for blk in cval:
                        if isinstance(blk, dict) and blk.get("type") in ("text", "output_text") and blk.get("text"):
                            texts.append(str(blk["text"]))
                return "assistant", "\n".join(texts).strip(), []
        return "other", "", []

    msg = entry.get("message") if isinstance(entry.get("message"), dict) else entry
    role = str(msg.get("role") or entry.get("role") or etype).lower()
    if role == "user":
        cblocks = msg.get("content")
        if isinstance(cblocks, list) and cblocks and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in cblocks
        ):
            return "other", "", []
        return "user_turn", "", []

    if role == "assistant":
        cval = msg.get("content")
        texts = []
        tcalls = []
        if isinstance(cval, str) and cval.strip():
            texts.append(cval.strip())
        elif isinstance(cval, list):
            for blk in cval:
                if not isinstance(blk, dict):
                    continue
                btype = blk.get("type")
                if btype in ("text", "output_text") and blk.get("text"):
                    texts.append(str(blk["text"]))
                elif btype in ("tool_use", "function_call", "custom_tool_call"):
                    tcalls.append(
                        {
                            "name": blk.get("name", ""),
                            "args": blk.get("input") if "input" in blk else (blk.get("arguments") or {}),
                        }
                    )
        return "assistant", "\n".join(texts).strip(), tcalls

    return "other", "", []


def _count_edit_or_exec_calls(tool_calls: list, tokens: tuple[str, ...]) -> int:
    return sum(
        1
        for c in tool_calls
        if isinstance(c, dict) and any(k in str(c.get("name") or "").lower() for k in tokens)
    )


def _extract_latest_turn_assistant(host: str, tail_entries: list, reached_bof: bool = True) -> dict:
    empty = {"content": "", "tool_calls": [], "edit_or_exec_calls": 0, "turn_complete_window": reached_bof, "sig": ""}
    if not tail_entries:
        return empty

    if host == "antigravity":
        turn_steps = []
        found_user_boundary = False
        for entry in reversed(tail_entries):
            etype = entry.get("type")
            if etype == "USER_INPUT" and entry.get("source") == "USER_EXPLICIT":
                found_user_boundary = True
                break
            if etype == "PLANNER_RESPONSE":
                turn_steps.append(entry)
        turn_steps.reverse()
        if not turn_steps:
            return {**empty, "turn_complete_window": found_user_boundary or reached_bof}

        last_text = ""
        all_tools = []
        for step in turn_steps:
            txt = str(step.get("content") or "").strip()
            if txt:
                last_text = txt
            tcalls = step.get("tool_calls")
            if isinstance(tcalls, list):
                all_tools.extend(tcalls)
        last_idx = turn_steps[-1].get("step_index", "")
        return {
            "content": last_text,
            "tool_calls": all_tools,
            "edit_or_exec_calls": _count_edit_or_exec_calls(all_tools, _EDIT_EXEC_TOOL_TOKENS_AGY),
            "turn_complete_window": found_user_boundary or reached_bof,
            "sig": _short_hash(f"{last_idx}:{last_text[:200]}:{len(all_tools)}"),
        }

    turn_texts = []
    all_tools = []
    found_user_boundary = False
    for entry in reversed(tail_entries):
        kind, txt, tcalls = _parse_claude_or_codex_entry(entry)
        if kind == "user_turn":
            found_user_boundary = True
            break
        if kind == "assistant":
            if txt:
                turn_texts.append(txt)
            if tcalls:
                all_tools.extend(tcalls)

    turn_texts.reverse()
    all_tools.reverse()
    last_text = turn_texts[-1] if turn_texts else ""
    return {
        "content": last_text,
        "tool_calls": all_tools,
        "edit_or_exec_calls": _count_edit_or_exec_calls(all_tools, _EDIT_EXEC_TOOL_TOKENS_CLI),
        "turn_complete_window": found_user_boundary or reached_bof,
        "sig": _short_hash(f"{last_text[:200]}:{len(all_tools)}") if (last_text or all_tools) else "",
    }


def _extract_previous_assistant_for_smell(host: str, tail_entries: list) -> dict:
    if not tail_entries:
        return {"content": "", "tool_calls": [], "sig": ""}

    if host == "antigravity":
        for entry in reversed(tail_entries):
            if entry.get("type") == "PLANNER_RESPONSE":
                txt = str(entry.get("content") or "").strip()
                tcalls = entry.get("tool_calls") if isinstance(entry.get("tool_calls"), list) else []
                if txt or tcalls:
                    sig = _short_hash(f"{entry.get('step_index', '')}:{txt[:240]}")
                    return {"content": txt, "tool_calls": tcalls, "sig": sig}
        return {"content": "", "tool_calls": [], "sig": ""}

    collected_texts: list[str] = []
    collected_tools: list[dict] = []
    started = False
    for entry in reversed(tail_entries):
        kind, txt, tcalls = _parse_claude_or_codex_entry(entry)
        if kind == "assistant":
            started = True
            if txt:
                collected_texts.append(txt)
            if tcalls:
                collected_tools.extend(tcalls)
        elif kind == "user_turn" and started:
            break
    collected_texts.reverse()
    last_txt = collected_texts[-1] if collected_texts else ""
    if last_txt or collected_tools:
        return {
            "content": last_txt,
            "tool_calls": collected_tools,
            "sig": _short_hash(f"{last_txt[:240]}:{len(collected_tools)}"),
        }
    return {"content": "", "tool_calls": [], "sig": ""}


def _extract_last_user_prompt_from_tail(host: str, tail_entries: list) -> str:
    for entry in reversed(tail_entries or []):
        if host == "antigravity":
            if entry.get("type") == "USER_INPUT" and entry.get("source") == "USER_EXPLICIT":
                return extract_clean_user_text(str(entry.get("content") or ""))
            continue
        kind, txt, _ = _parse_claude_or_codex_entry(entry)
        if kind == "user_turn":
            return extract_clean_user_text(txt) if txt else _extract_entry_user_text(entry)
    return ""


def _step_down_tone(tone: str) -> str:
    return {"sharp": "peer", "peer": "calm"}.get(tone, "calm")


def format_smell_remedy(smells: list[str], lang: str, overcorrection_kind: str = "") -> str:
    idx = 0 if lang == "zh" else 1
    valid = [s for s in smells if s in SMELL_LABELS]
    if "overcorrection_drift" in valid:
        kind = overcorrection_kind or "both"
        if kind == "archaic":
            return (
                "[语域回拉] 上一轮漂移到了生僻古语或书面文言。回到平时说话的现代白话，用直白精准的日常技术词讲机制，别掉书袋。"
                if lang == "zh"
                else "[Overcorrection Brake] Prior reply drifted into archaic/stilted diction. Return to plain, modern everyday technical English—clear mechanics, zero theatrical formalism."
            )
        return (
            "[语域回拉] 上一轮狠话过头且缺少硬事实兜底。收掉情绪宣泄和夸张贬损，把精力放回具体代码、数字与因果机制上，平实直说即可。"
            if lang == "zh"
            else "[Overcorrection Brake] Prior reply leaned into unsubstantiated snark. Dial back theatrical heat and ground every claim in concrete code, numbers, and causal mechanics."
        )
    # Keep higher-severity smells first even if caller passes an unsorted list
    ranked = [s for _, s in sorted(enumerate(valid), key=lambda item: (-SMELL_DEFAULT_WEIGHTS.get(item[1], 1), item[0]))]
    top = ranked[:3]
    descriptions = [SMELL_LABELS[s][idx] for s in top]
    if not descriptions:
        return ""
    smell_set = set(top)
    hints = []
    if "wall_of_text" in smell_set:
        hints.append("2-4 句自然分段" if lang == "zh" else "break into 2-4 sentence paragraphs")
    if "divider_spam" in smell_set or "doc_format_in_chat" in smell_set:
        hints.append("不画横线、不写汇报标题清单" if lang == "zh" else "no dividers, headings, or stacked checklists")
    if "meta_opening" in smell_set:
        hints.append("别在开头播报怎么答" if lang == "zh" else "drop opening meta-narration")
    if "closing_offer" in smell_set or "gpt_closing_menu" in smell_set:
        hints.append("说完即停不揽活" if lang == "zh" else "stop dead without closing offers")
    if "consultant_balance" in smell_set or "fence_sitting" in smell_set:
        hints.append("第一句直接站队，别凑结尾平衡尾段" if lang == "zh" else "pick a clear side in Sentence 1 with no balancing tail")
    if "praise_then_pivot" in smell_set:
        hints.append("别先夸出发点再转折" if lang == "zh" else "skip praise-then-pivot buffers")
    if "disclaimer_boilerplate" in smell_set:
        hints.append("去掉泛化免责套话" if lang == "zh" else "drop generic liability disclaimers")
    if "monotone_cadence" in smell_set or "flat_textbook_voice" in smell_set:
        hints.append("穿插 4-10 字短句落锤、带点真实口语体温" if lang == "zh" else "mix 3-7 word punches and real spoken warmth")
    if "repetitive_openers" in smell_set or "cross_turn_repeat" in smell_set:
        hints.append("换掉重复的起手句式" if lang == "zh" else "vary your opening sentence phrasing")
    if "cn_idiom_bureaucratese" in smell_set:
        hints.append("用大白话直讲，去掉四字公文套词" if lang == "zh" else "drop bureaucratic idioms and grand wrap-ups")
    if lang == "zh":
        joined = "、".join(descriptions)
        extra = f"（重点：{'；'.join(hints)}）" if hints else ""
        return f"[语域纠偏] 上一轮滑回了平滑套路或专栏腔（{joined}）。这一轮回到面对面熟人直聊：第一句短句直亮判断，带真态度讲透因果{extra}。"
    joined = ", ".join(descriptions)
    extra = f" (Focus: {'; '.join(hints)}.)" if hints else ""
    return f"[Relapse Fix] Prior reply slipped into stiff assistant/op-ed habits ({joined}). Return to spoken peer voice with short punches and grounded reaction.{extra}"


def _emit_inject(host: str, event_name: str, text: str) -> dict:
    if not text:
        return {}
    if host == "antigravity":
        return {"injectSteps": [{"systemMessage": {"systemMessage": text}}]}
    if event_name == "PostModelSwitch":
        return {"__raw_text__": text}
    return {
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "additionalContext": text,
        }
    }


def _emit_stop(host: str, block: bool, reason: str = "") -> dict:
    if host == "antigravity":
        if block:
            return {"decision": "continue", "reason": reason}
        return {"decision": "allow"}
    if block:
        return {"decision": "block", "reason": reason}
    return {}


def _latest_agy_user_step_index(tail_entries: list) -> int:
    for entry in reversed(tail_entries or []):
        if entry.get("type") == "USER_INPUT" and entry.get("source") == "USER_EXPLICIT":
            try:
                return int(entry.get("step_index", -1))
            except Exception:
                return -1
    return -1


def evaluate_stop_gate(
    host: str,
    payload: dict,
    config: dict,
    state: dict,
    tail_entries: list,
    reached_bof: bool,
    lang: str,
) -> dict:
    if not config.get("stop_guard", True):
        return _emit_stop(host, False)

    # Pre-gate safety exemptions: read-only/plan permission modes or read-only adversarial reviewer role
    perm_mode = str(payload.get("permission_mode") or payload.get("permissionMode") or "").strip().lower()
    if perm_mode in ("plan", "read-only", "readonly", "ask"):
        return _emit_stop(host, False)
    if state.get("last_role_policy") == "adversarial" or state.get("sticky_role_policy") == "adversarial":
        return _emit_stop(host, False)

    if host == "antigravity":
        if payload.get("continuationActive") is True:
            return _emit_stop(host, False)
        term = str(payload.get("terminationReason") or "NO_TOOL_CALL")
        if term != "NO_TOOL_CALL":
            return _emit_stop(host, False)
        if payload.get("fullyIdle") is False:
            return _emit_stop(host, False)
    else:
        if payload.get("stop_hook_active") is True:
            return _emit_stop(host, False)

    if int(state.get("turn_stop_count", 0)) >= int(config.get("max_stop_continuations", 1)):
        return _emit_stop(host, False)

    turn_data = _extract_latest_turn_assistant(host, tail_entries, reached_bof=reached_bof)
    content = turn_data["content"]
    direct_last = str(payload.get("last_assistant_message") or "").strip()
    if direct_last:
        content = direct_last

    tool_calls = turn_data["tool_calls"]
    if not content and not tool_calls:
        return _emit_stop(host, False)

    pats = _get_compiled_patterns()
    smell_report = analyze_response_smells(content, tool_calls)
    smells = set(smell_report["smells"])
    prose = smell_report["prose"]
    prose_code_blocks = smell_report.get("prose_code_blocks") or []

    # 1. Tool-payload completeness gate ALWAYS blocks lazy elisions written to disk,
    #    regardless of user-turn discussion markers, confirmation questions, or prose hedges.
    if smell_report["tool_lazy_code"]:
        state["turn_stop_count"] = int(state.get("turn_stop_count", 0)) + 1
        reason = (
            "[完备门禁] 检测到落盘代码包含省略占位符。请立即补齐100%完整可运行实现并验证。"
            if lang == "zh"
            else "[Completeness Gate] Lazy code placeholder detected in file-edit payload. Provide the complete runnable implementation and verify."
        )
        return _emit_stop(host, True, reason)

    # 2. Strip fenced blocks from last user prompt before checking discuss_guard (code comments like '# DO NOT EDIT' must not disable gates)
    last_user_text = _extract_last_user_prompt_from_tail(host, tail_entries)
    if last_user_text:
        last_user_prose = _bound_prose_window(_split_fenced_blocks(last_user_text)[0].strip())
        if last_user_prose and pats["discuss_guard"].search(last_user_prose):
            return _emit_stop(host, False)

    # 3. Legitimate block / destructive-operation confirmation exemption (placed BEFORE prose completeness gate so
    #    illustrative `...` snippets inside a confirmation prompt never force unapproved execution)
    if pats["blocked_exemption"].search(prose):
        return _emit_stop(host, False)

    allow_edits = bool(state.get("allow_disk_edits", True))
    exec_or_debug = state.get("last_mode") in ("SURGICAL_EXEC", "DEBUG_RECOVERY")

    if exec_or_debug and allow_edits and (smell_report["prose_lazy_code"] or "ds_prose_handwave" in smells):
        state["turn_stop_count"] = int(state.get("turn_stop_count", 0)) + 1
        reason = (
            "[完备门禁] 检测到代码省略占位符或“篇幅所限自行补全”式省流。请立即补齐100%完整可运行实现并验证。"
            if lang == "zh"
            else "[Completeness Gate] Lazy code placeholder or hand-waving elision detected. Provide the complete runnable implementation and verify."
        )
        return _emit_stop(host, True, reason)

    # Trailing question exempts genuine clarification asks, but NOT closing waiter offers or unapplied code dumps
    if (
        prose.rstrip().endswith(("?", "？"))
        and not ({"closing_offer", "gpt_closing_menu"} & smells)
        and not pats["unapplied_code_claim"].search(prose)
    ):
        return _emit_stop(host, False)

    if state.get("last_mode") == "SURGICAL_EXEC" and allow_edits and turn_data["turn_complete_window"]:
        if turn_data["edit_or_exec_calls"] == 0 and pats["ds_plan_only_stop"].search(prose):
            state["turn_stop_count"] = int(state.get("turn_stop_count", 0)) + 1
            reason = (
                "[执行门禁] 当前任务已获准实施，不要停在计划宣告阶段。请直接调用工具落地修改并完成验证。"
                if lang == "zh"
                else "[Execution Gate] Implementation is authorized; do not stop at announcing a plan. Call tools now to execute and verify."
            )
            return _emit_stop(host, True, reason)

        has_large_prose_code = any(
            lang_hint not in _DOC_FENCE_LANGS and len(body.splitlines()) >= 12
            for lang_hint, body in prose_code_blocks
        )
        if turn_data["edit_or_exec_calls"] == 0 and has_large_prose_code and pats["unapplied_code_claim"].search(prose):
            state["turn_stop_count"] = int(state.get("turn_stop_count", 0)) + 1
            reason = (
                "[落盘门禁] 检测到仅在回复中粘贴完整代码而未调用文件修改工具。请直接调用编辑工具落盘并验证。"
                if lang == "zh"
                else "[Write Gate] Raw code dump detected with zero file-edit tool calls. Apply the changes to disk via edit/write tools and verify."
            )
            return _emit_stop(host, True, reason)

    return _emit_stop(host, False)


def _sync_codex_shadow_state(host: str, session_id: str, updates: dict) -> None:
    """Keep a split-brain codex:<sid> shadow state in sync when Claude-only events fire under ambient CODEX_HOME."""
    if host == "claude" and os.path.isfile(_session_state_path("codex", session_id)):
        shadow = load_session_state("codex", session_id)
        shadow.update(updates)
        save_session_state("codex", session_id, shadow)


def _has_sensitive_bootstrap_tokens(text: str) -> bool:
    import re

    raw = text or ""
    low = raw.lower()
    for needle in ("sk-", "ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "bearer ", "api_key", "api-key", "secret", "password", "://", "/users/", "/home/", "@", "-----begin"):
        if needle in low:
            return True
    if re.search(r"\b(?:AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{10,}|xox[baprs]-[0-9A-Za-z-]{8,}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b", raw):
        return True
    if re.search(r"(?:[A-Za-z]:\\|\\\\[^\\\s]+\\|\btoken\s*[:=])", raw, re.IGNORECASE):
        return True
    return False


def _capture_good_voice_anchor(
    prose: str,
    report: dict,
    lang: str,
    family: str,
    tone: str,
    mode: str,
    turn_count: int,
    policy: str,
) -> dict | None:
    """Capture 1-2 crisp spoken sentences from a clean, high-pulse chat turn for Self-Bootstrap recovery."""
    if policy not in ("default", "persona") or mode not in CHAT_INTENT_MODES or tone == "calm":
        return None
    if report.get("score", 1) != 0 or report.get("smells") or report.get("overcorrection_kind"):
        return None
    if report.get("prose_code_blocks"):
        return None
    # Enforce strict language match between actual prose and anchor language to prevent EN<->ZH contamination
    inferred_lang = _infer_text_language(prose)
    if inferred_lang and inferred_lang != lang:
        return None
    min_len, max_len = (70, 1400) if lang == "zh" else (120, 2400)
    if not (min_len <= len(prose) <= max_len):
        return None
    stance = report.get("stance") or {}
    if int(stance.get("transitions", 0)) > 0:
        return None
    has_pulse = (
        int(stance.get("attitude", 0)) >= 1
        or int(stance.get("spoken_pivot", 0)) >= 1
        or int(stance.get("self_mention_singular", 0)) >= 1
    )
    if not has_pulse:
        return None
    sent_n = int(stance.get("sent_count", 0))
    cv = stance.get("sent_len_cv")
    if sent_n >= 4 and (cv is None or cv < 0.22):
        return None
    if stance.get("opener_diversity") is not None and float(stance["opener_diversity"]) < 0.70:
        return None
    sents = split_sentences(prose, skip_lists=True)
    if not sents:
        return None
    snippet = _sanitize_exemplar_text(" ".join(sents[:2]) if lang == "en" else "".join(sents[:2]))
    cap = 140 if lang == "zh" else 220
    snippet = snippet[:cap].strip()
    if len(snippet) < (24 if lang == "zh" else 48) or _has_sensitive_bootstrap_tokens(snippet):
        return None
    return {
        "lang": lang,
        "family": family,
        "tone": tone,
        "text": snippet,
        "entities": extract_exemplar_entities(snippet, lang, limit=5),
        "captured_turn": turn_count,
    }


def _format_bootstrap_anchor(anchor: dict, lang: str) -> str:
    txt = _sanitize_exemplar_text(str((anchor or {}).get("text") or "")).strip()
    if not txt:
        return ""
    if lang == "zh":
        return f"[声线自举] 保持你前面那股开口带劲、短句落锤的聊法（只借节奏不复用内容：「{txt}」），直接答这一轮。"
    return f'[Voice Lock] Stay in the crisp spoken cadence you nailed earlier (rhythm only, never repeat its topic: "{txt}") and answer straight.'


def _scan_previous_turn_smells(
    host: str,
    tail_entries: list,
    resolved_family: str,
    lang: str,
    state: dict,
    *,
    tone: str = "peer",
    policy: str = "default",
    lang_switched: bool = False,
) -> tuple[str, str]:
    """Return `(remedy_text, overcorrection_kind)` and update rolling state, 3-turn openings, leak guard, and Self-Bootstrap."""
    prev_resp = _extract_previous_assistant_for_smell(host, tail_entries)
    resp_sig = prev_resp["sig"]
    if not resp_sig or resp_sig == state.get("last_scanned_resp_sig"):
        return "", ""

    prev_mode = str(state.get("last_mode") or "PEER_SPAR")
    recent_openings = list(state.get("recent_openings") or [])
    report = analyze_response_smells(
        prev_resp["content"],
        prev_resp["tool_calls"],
        str(state.get("prev_opening_sig") or ""),
        mode=prev_mode,
        recent_openings=recent_openings,
        tone=tone,
    )
    cur_score = report["score"]
    rolling = cur_score + (1 if state.get("rolling_smell_score", 0) >= 1 and cur_score >= 1 else 0)
    state["last_scanned_resp_sig"] = resp_sig
    state["rolling_smell_score"] = cur_score
    if report["opening_sig"]:
        state["prev_opening_sig"] = report["opening_sig"]
    if report["opening_sig"] or report.get("opening_head"):
        recent_openings.append({"sig": report["opening_sig"], "head": report.get("opening_head", "")})
        state["recent_openings"] = recent_openings[-3:]

    # Exemplar entity-leak guard: compare against the Turn N-1 prompt that was active when the exemplar was injected
    last_ex_id = str(state.get("last_exemplar_id") or "")
    last_ex_ents = list(state.get("last_exemplar_entities") or [])
    if last_ex_id and last_ex_ents:
        resp_low = (report.get("prose") or "").lower()
        ex_prompt_low = str(state.get("last_exemplar_prompt") or "").lower()
        leaked = [t for t in last_ex_ents if len(t) >= 2 and t.lower() in resp_low and t.lower() not in ex_prompt_low]
        if leaked:
            blocked = list(state.get("blocked_exemplar_ids") or [])
            if last_ex_id not in blocked:
                blocked.append(last_ex_id)
                state["blocked_exemplar_ids"] = blocked[-16:]
        state["last_exemplar_id"] = ""
        state["last_exemplar_entities"] = []
        state["last_exemplar_prompt"] = ""

    if resolved_family == "generic":
        guessed = infer_family_from_smells(report["smells"])
        if guessed:
            state["inferred_family"] = guessed

    effective_fam_for_anchor = (
        str(state["inferred_family"])
        if (resolved_family == "generic" and state.get("inferred_family") in VALID_FAMILIES)
        else resolved_family
    )

    overcorr_kind = str(report.get("overcorrection_kind") or "")
    if overcorr_kind:
        state["good_voice_anchor"] = None
        stepped = _step_down_tone(tone)
        state["soft_tone_override"] = {"tone": stepped, "remaining_turns": 2, "reason": overcorr_kind}
    elif not state.get("soft_tone_override") and not lang_switched:
        existing_anchor = state.get("good_voice_anchor")
        same_bucket = (
            isinstance(existing_anchor, dict)
            and existing_anchor.get("lang") == lang
            and existing_anchor.get("family") == effective_fam_for_anchor
            and existing_anchor.get("tone") == tone
        )
        if not same_bucket:
            captured = _capture_good_voice_anchor(
                report.get("prose") or "",
                report,
                lang,
                effective_fam_for_anchor,
                tone,
                prev_mode,
                int(state.get("turn_count", 0)),
                policy,
            )
            if captured is not None:
                state["good_voice_anchor"] = captured

    if rolling >= 2 and resp_sig != state.get("last_warned_resp_sig"):
        state["last_warned_resp_sig"] = resp_sig
        return format_smell_remedy(report["smells"], lang, overcorrection_kind=overcorr_kind), overcorr_kind
    return "", overcorr_kind


def _custom_has_exemplar_for(cfg: dict, lang: str, tone: str) -> bool:
    custom = cfg.get("voice_exemplars") or {}
    if not isinstance(custom, dict):
        return False
    for key in (tone, "any"):
        bucket = custom.get(key)
        if isinstance(bucket, dict) and isinstance(bucket.get(lang), list) and len(bucket[lang]) > 0:
            return True
    return False


def _append_turn_mode_and_anchors(
    inject_lines: list[str],
    *,
    cfg: dict,
    host: str,
    effective_family: str,
    effective_tone: str,
    lang: str,
    active_mode: str,
    prev_mode: str,
    next_turn_count: int,
    need_baseline: bool,
    model_switched: bool,
    config_changed: bool,
    lang_switched: bool,
    smell_remedy: str,
    overcorrection_kind: str,
    raw_user_input: str,
    policy: str,
    state: dict,
) -> None:
    is_chat = active_mode in CHAT_INTENT_MODES
    refresh_due = not smell_remedy and is_chat and next_turn_count >= 5 and next_turn_count % 5 == 0
    mode_changed = active_mode != prev_mode
    is_first_turn = next_turn_count == 1
    reanchored = need_baseline or model_switched or config_changed or lang_switched
    allow_samples = is_chat and policy in ("default", "persona") and not overcorrection_kind

    def _emit_voice_sample() -> bool:
        if not allow_samples:
            return False
        entry = _select_voice_exemplar(
            cfg,
            lang,
            effective_tone,
            active_mode,
            prompt=raw_user_input,
            used_ids=state.get("used_exemplar_ids"),
            blocked_ids=state.get("blocked_exemplar_ids"),
        )
        if not entry:
            return False
        block = format_voice_exemplar_block(entry, lang)
        if not block:
            return False
        inject_lines.append(block)
        used = list(state.get("used_exemplar_ids") or [])
        used.append(str(entry.get("id") or ""))
        state["used_exemplar_ids"] = used[-6:]
        state["last_exemplar_id"] = str(entry.get("id") or "")
        state["last_exemplar_entities"] = extract_exemplar_entities(
            entry.get("text", ""), lang, entry.get("topic_terms"), limit=6
        )
        state["last_exemplar_prompt"] = (raw_user_input or "")[:500]
        state["last_exemplar_turn"] = next_turn_count
        return True

    def _can_use_bootstrap() -> bool:
        anchor = state.get("good_voice_anchor")
        return (
            allow_samples
            and not _custom_has_exemplar_for(cfg, lang, effective_tone)
            and isinstance(anchor, dict)
            and anchor.get("lang") == lang
            and anchor.get("family") == effective_family
            and anchor.get("tone") == effective_tone
            and bool(anchor.get("text"))
        )

    emitted_mode_or_anchor = False
    if host in ("claude", "codex"):
        expressive_or_debug = active_mode in ("EXPLAIN_DEEP", "CRITIQUE_OPINION", "EMPATHY_VENT", "DEBUG_RECOVERY")
        if is_first_turn or mode_changed or expressive_or_debug or reanchored:
            inject_lines.append(MODE_DIRECTIVES[active_mode][lang])
            emitted_mode_or_anchor = True
        if is_chat:
            if effective_family == "deepseek":
                ds_idx = (next_turn_count - 1) % len(DS_WIRE_VARIANTS)
                inject_lines.append(DS_WIRE_VARIANTS[ds_idx][lang])
                emitted_mode_or_anchor = True
            elif is_first_turn and not reanchored:
                inject_lines.append(WIRE_ANCHORS[effective_family][lang])
                emitted_mode_or_anchor = True
    else:
        injected_prev_mode = str(state.get("injected_agy_mode") or "")
        if need_baseline:
            if active_mode != "PEER_SPAR":
                inject_lines.append(MODE_DIRECTIVES[active_mode][lang])
                state["injected_agy_mode"] = active_mode
                emitted_mode_or_anchor = True
        elif mode_changed or lang_switched or (bool(injected_prev_mode) and active_mode != injected_prev_mode):
            if active_mode != "PEER_SPAR" or mode_changed or bool(injected_prev_mode):
                inject_lines.append(MODE_DIRECTIVES[active_mode][lang])
                emitted_mode_or_anchor = True
            state["injected_agy_mode"] = "" if active_mode == "PEER_SPAR" else active_mode
        if is_chat:
            if effective_family == "deepseek":
                ds_idx = (next_turn_count - 1) % len(DS_WIRE_VARIANTS)
                inject_lines.append(DS_WIRE_VARIANTS[ds_idx][lang])
                emitted_mode_or_anchor = True
            elif is_first_turn and not reanchored:
                inject_lines.append(WIRE_ANCHORS[effective_family][lang])
                emitted_mode_or_anchor = True

    # Attach 1 orthogonal voice sample or Self-Bootstrap anchor at high-leverage penetration points
    last_ex_turn = int(state.get("last_exemplar_turn", 0))
    if is_first_turn and allow_samples:
        _emit_voice_sample()
    elif smell_remedy and allow_samples:
        if _can_use_bootstrap():
            inject_lines.append(_format_bootstrap_anchor(state["good_voice_anchor"], lang))
        else:
            _emit_voice_sample()
    elif refresh_due:
        r_idx = int(state.get("refresh_idx", 0))
        inject_lines.append(LONG_SESSION_REFRESH_VARIANTS[r_idx % len(LONG_SESSION_REFRESH_VARIANTS)][lang])
        state["refresh_idx"] = r_idx + 1
        if _can_use_bootstrap():
            inject_lines.append(_format_bootstrap_anchor(state["good_voice_anchor"], lang))
        elif allow_samples:
            _emit_voice_sample()
    elif need_baseline and next_turn_count > 1 and _can_use_bootstrap():
        # Post-PreCompact recovery: restore the session's own verified spoken cadence
        inject_lines.append(_format_bootstrap_anchor(state["good_voice_anchor"], lang))
    elif mode_changed and allow_samples and (next_turn_count - last_ex_turn) >= 2:
        _emit_voice_sample()
    elif is_chat and not is_first_turn and not reanchored and not smell_remedy and not emitted_mode_or_anchor:
        # Turn 2+ steady chat anti-dilution: 1 compact rotating perspective line (~20 tokens, zero cache loss)
        seed = int(state.get("session_seed", 0))
        p_idx = (next_turn_count + seed) % len(PERSPECTIVE_MICRO_ANCHORS)
        inject_lines.append(PERSPECTIVE_MICRO_ANCHORS[p_idx][lang])


def process_event(payload: dict, config: dict | None = None) -> dict:
    cfg = config if config is not None else load_config()
    set_active_strip_patterns(cfg.get("model_strip_patterns") or [])
    host = detect_host(payload)
    event_name = str(payload.get("hookEventName") or payload.get("hook_event_name") or "")
    session_id = str(payload.get("conversationId") or payload.get("session_id") or "default")
    raw_user_input = str(payload.get("lastUserInput") or payload.get("prompt") or "")
    system_text = str(payload.get("systemPrompt") or payload.get("system_prompt") or "")
    agent_type = str(payload.get("agent_type") or payload.get("agent_name") or payload.get("subagent_type") or "")
    clean_input = extract_clean_user_text(raw_user_input)

    def _pass_through() -> dict:
        return _emit_stop(host, False) if event_name == "Stop" else {}

    if not cfg.get("enabled", True):
        return _pass_through()

    state = load_session_state(host, session_id)
    # When Claude-only lifecycle events fire alongside a fresher codex:<sid> state (e.g. ambient CODEX_HOME or
    # turn_id-routed UserPromptSubmit), inherit the fresher codex:<sid> state so flow_bypass, lang, and model_family stay intact.
    if host == "claude" and event_name in ("PreCompact", "PostModelSwitch") and os.path.isfile(_session_state_path("codex", session_id)):
        codex_state = load_session_state("codex", session_id)
        claude_exists = os.path.isfile(_session_state_path("claude", session_id))
        if (
            not claude_exists
            or int(codex_state.get("turn_count", 0)) > int(state.get("turn_count", 0))
            or int(codex_state.get("updated_at", 0)) > int(state.get("updated_at", 0))
        ):
            state = codex_state

    if state.get("flow_bypass") or state.get("sticky_role_policy") == "skip" or should_bypass_session(session_id, clean_input, cfg, system_text):
        if _hits_prompt_or_system_bypass(clean_input, cfg, system_text) and not state.get("flow_bypass"):
            state["flow_bypass"] = True
            save_session_state(host, session_id, state)
        return _pass_through()

    role = resolve_role(cfg, agent_type=agent_type, session_id=session_id, prompt=clean_input, system_text=system_text)
    if role and role["policy"] == "skip":
        state["sticky_role_policy"] = "skip"
        save_session_state(host, session_id, state)
        return _pass_through()

    if event_name == "PreCompact":
        # Preserve good_voice_anchor, recent_openings, and refresh_idx across compaction; drop stale soft_tone_override
        reset = {"session_initialized": False, "injected_agy_mode": "", "soft_tone_override": None}
        state.update(reset)
        save_session_state(host, session_id, state)
        _sync_codex_shadow_state(host, session_id, reset)
        return {}

    transcript_path = str(payload.get("transcriptPath") or payload.get("transcript_path") or "")
    custom_aliases = cfg.get("model_aliases") or {}

    if event_name == "Stop":
        tail_entries, reached_bof = _read_tail_jsonl_with_meta(transcript_path, max_bytes=STOP_TAIL_BYTES)
        _, stop_raw_model = resolve_active_model(host, payload, tail_entries, custom_aliases)
        stop_role = role or (resolve_role(cfg, model=stop_raw_model) if stop_raw_model else None)
        if stop_role and stop_role["policy"] == "skip":
            return _emit_stop(host, False)
        if stop_role and stop_role["policy"] == "adversarial":
            state["last_role_policy"] = "adversarial"
        lang = detect_language(cfg.get("language", "auto"), clean_input, str(state.get("lang") or ""), tail_entries)
        state["lang"] = lang
        result = evaluate_stop_gate(host, payload, cfg, state, tail_entries, reached_bof, lang)
        save_session_state(host, session_id, state)
        return result

    input_sig = _short_hash(clean_input) if clean_input else state.get("last_input_sig", "")
    model_hint = str(payload.get("modelName") or payload.get("to_model") or payload.get("model") or "").strip()
    try:
        invocation_num = int(payload.get("invocationNum") or 0)
    except Exception:
        invocation_num = 0
    cur_t_size = -1
    if transcript_path:
        try:
            cur_t_size = os.path.getsize(transcript_path)
        except OSError:
            cur_t_size = -1
    transcript_unchanged = (cur_t_size < 0) or (int(state.get("last_transcript_size", -1)) == cur_t_size)
    if (
        host == "antigravity"
        and event_name == "PreInvocation"
        and invocation_num > 1
        and transcript_unchanged
        and state.get("session_initialized")
        and state.get("epoch") == cfg["epoch"]
        and state.get("tone") == cfg["tone"]
        and state.get("overlay_sig", "") == str(cfg.get("overlay_sig") or "")
        and input_sig == state.get("last_input_sig")
        and (not model_hint or model_hint.lower() == "auto" or classify_model_family(model_hint, custom_aliases) == state.get("model_family"))
    ):
        return {}

    tail_entries = _read_tail_jsonl(transcript_path)
    lang = detect_language(cfg.get("language", "auto"), clean_input, str(state.get("lang") or ""), tail_entries)
    resolved_family, raw_model = resolve_active_model(host, payload, tail_entries, custom_aliases)

    if (
        host == "antigravity"
        and resolved_family == "generic"
        and (not model_hint or model_hint.lower() in ("auto", "none", "default"))
        and raw_model.lower() in ("", "auto", "none", "default")
        and state.get("model_family") in VALID_FAMILIES
        and state.get("model_family") != "generic"
    ):
        resolved_family = str(state["model_family"])
        raw_model = str(state.get("raw_model") or raw_model)

    if role is None and raw_model:
        role = resolve_role(cfg, model=raw_model)
        if role and role["policy"] == "skip":
            state["sticky_role_policy"] = "skip"
            save_session_state(host, session_id, state)
            return {}
    if role is not None:
        policy = role["policy"]
        if policy in ("adversarial", "terse", "persona"):
            state["sticky_role_policy"] = policy
    else:
        policy = str(state.get("sticky_role_policy") or "default")
    overlay_sig = str(cfg.get("overlay_sig") or "")
    lean = policy in ("terse", "adversarial")

    def _baseline_extras() -> list[str]:
        extras = []
        voice_line = (cfg.get("voice") or {}).get(lang)
        if voice_line and policy in ("default", "persona"):
            extras.append(voice_line)
        if policy in ROLE_DIRECTIVES:
            extras.append(ROLE_DIRECTIVES[policy][lang])
        return extras

    if event_name == "SessionStart":
        if host == "antigravity" and not clean_input and cfg.get("language") == "auto":
            save_session_state(host, session_id, state)
            return {}
        effective_fam = str(state["inferred_family"]) if (resolved_family == "generic" and state.get("inferred_family") in VALID_FAMILIES) else resolved_family
        parts = []
        if (host in ("claude", "codex") or (host == "antigravity" and lang == "zh")) and not lean:
            parts.append(STANDALONE_BASELINE[lang])
        parts.append(directive_for(cfg, effective_fam, lang))
        if not lean:
            parts.append(TONE_ADDENDA[cfg["tone"]][lang])
            if host == "antigravity" and lang == "zh":
                parts.append(ANTIGRAVITY_ZH_MIRROR)
        parts.extend(_baseline_extras())
        state.update(
            {
                "epoch": cfg["epoch"], "tone": cfg["tone"], "overlay_sig": overlay_sig, "lang": lang,
                "model_family": effective_fam, "raw_model": raw_model, "session_initialized": True,
                "last_role_policy": policy, "turn_stop_count": 0,
            }
        )
        save_session_state(host, session_id, state)
        return _emit_inject(host, event_name, "\n".join(parts))

    if event_name == "PostModelSwitch":
        prev_fam = state.get("model_family")
        pms_update = {
            "epoch": cfg["epoch"], "tone": cfg["tone"], "overlay_sig": overlay_sig, "lang": lang,
            "model_family": resolved_family, "inferred_family": "", "raw_model": raw_model,
            "last_role_policy": policy,
        }
        if resolved_family != prev_fam:
            pms_update.update({
                "good_voice_anchor": None,
                "recent_openings": [],
                "prev_opening_sig": "",
                "soft_tone_override": None,
            })
        state.update(pms_update)
        save_session_state(host, session_id, state)
        _sync_codex_shadow_state(host, session_id, pms_update)
        return {} if resolved_family == prev_fam else _emit_inject(host, event_name, directive_for(cfg, resolved_family, lang))

    if event_name in ("PreInvocation", "UserPromptSubmit"):
        turn_id = str(payload.get("turn_id") or "")
        latest_step_idx = _latest_agy_user_step_index(tail_entries) if host == "antigravity" else -1
        if event_name == "UserPromptSubmit":
            is_new_turn = bool(clean_input) and (not turn_id or turn_id != str(state.get("last_turn_id") or ""))
        else:
            is_new_turn = bool(clean_input) and (
                invocation_num == 1
                or input_sig != state.get("last_input_sig")
                or (latest_step_idx >= 0 and latest_step_idx != int(state.get("last_user_step_idx", -1)))
            )
        prev_mode = str(state.get("last_mode") or "PEER_SPAR")
        active_mode = classify_intent(raw_user_input, prev_mode) if is_new_turn else prev_mode

        need_baseline = not state.get("session_initialized")
        lang_switched = bool(_infer_text_language(clean_input)) and not _is_language_neutral_turn(clean_input) and bool(state.get("lang")) and (lang != state.get("lang"))
        config_changed = (state.get("epoch") != cfg["epoch"]) or (state.get("tone") != cfg["tone"]) or (str(state.get("overlay_sig", "")) != overlay_sig)
        if config_changed:
            state["good_voice_anchor"] = None
            state["soft_tone_override"] = None
        if lang_switched:
            state["good_voice_anchor"] = None

        # Detect model-family switch BEFORE scanning prior model's reply so a new model never inherits
        # the previous model's overcorrection brake, opener history, or Self-Bootstrap anchor
        pre_effective_family = str(state["inferred_family"]) if (resolved_family == "generic" and state.get("inferred_family") in VALID_FAMILIES) else resolved_family
        switched_from_prev_model = bool(state.get("model_family")) and pre_effective_family != state.get("model_family")
        if switched_from_prev_model:
            state.update({
                "good_voice_anchor": None,
                "recent_openings": [],
                "prev_opening_sig": "",
                "soft_tone_override": None,
                "last_exemplar_id": "",
                "last_exemplar_entities": [],
                "last_exemplar_prompt": "",
                "inferred_family": "",
            })

        soft_ov = state.get("soft_tone_override") if isinstance(state.get("soft_tone_override"), dict) else None
        active_tone = str(soft_ov.get("tone")) if (soft_ov and soft_ov.get("tone") in VALID_TONES) else cfg["tone"]

        smell_remedy, overcorr_kind = (
            _scan_previous_turn_smells(
                host,
                tail_entries,
                resolved_family,
                lang,
                state,
                tone=active_tone,
                policy=policy,
                lang_switched=lang_switched,
            )
            if (is_new_turn and tail_entries and not switched_from_prev_model)
            else ("", "")
        )

        # Decrement active soft_tone_override on clean subsequent turns; emit restoration tone when it expires
        tone_restored = False
        if is_new_turn and not overcorr_kind and isinstance(state.get("soft_tone_override"), dict):
            rem = int(state["soft_tone_override"].get("remaining_turns", 0)) - 1
            if rem <= 0:
                prev_ov_tone = str(state["soft_tone_override"].get("tone") or "")
                state["soft_tone_override"] = None
                if prev_ov_tone and prev_ov_tone != cfg["tone"]:
                    tone_restored = True
            else:
                state["soft_tone_override"]["remaining_turns"] = rem

        # Re-read soft override after scan + decrement
        soft_ov_after = state.get("soft_tone_override") if isinstance(state.get("soft_tone_override"), dict) else None
        effective_tone = str(soft_ov_after.get("tone")) if (soft_ov_after and soft_ov_after.get("tone") in VALID_TONES) else cfg["tone"]

        effective_family = str(state["inferred_family"]) if (resolved_family == "generic" and state.get("inferred_family") in VALID_FAMILIES) else resolved_family
        model_switched = effective_family != state.get("model_family")

        inject_lines: list[str] = []
        if (need_baseline or lang_switched) and (host in ("claude", "codex") or (host == "antigravity" and lang == "zh")) and not lean:
            inject_lines.append(STANDALONE_BASELINE[lang])
        if need_baseline or model_switched or config_changed or lang_switched:
            inject_lines.append(directive_for(cfg, effective_family, lang))
            if (need_baseline or config_changed or lang_switched) and not lean:
                inject_lines.append(TONE_ADDENDA[effective_tone][lang])
                if host == "antigravity" and lang == "zh":
                    inject_lines.append(ANTIGRAVITY_ZH_MIRROR)
            if need_baseline or config_changed or lang_switched:
                inject_lines.extend(_baseline_extras())
        if smell_remedy and not lean:
            inject_lines.append(smell_remedy)
            if overcorr_kind and effective_tone != active_tone and not (need_baseline or config_changed or lang_switched):
                inject_lines.append(TONE_ADDENDA[effective_tone][lang])
        elif tone_restored and not lean and not (need_baseline or config_changed or lang_switched):
            inject_lines.append(TONE_ADDENDA[effective_tone][lang])
        if is_new_turn and is_epistemic_challenge(raw_user_input):
            inject_lines.append(CHALLENGE_DIRECTIVES[lang])

        next_turn_count = int(state.get("turn_count", 0)) + (1 if is_new_turn else 0)
        if is_new_turn and not lean:
            _append_turn_mode_and_anchors(
                inject_lines,
                cfg=cfg,
                host=host,
                effective_family=effective_family,
                effective_tone=effective_tone,
                lang=lang,
                active_mode=active_mode,
                prev_mode=prev_mode,
                next_turn_count=next_turn_count,
                need_baseline=need_baseline,
                model_switched=model_switched,
                config_changed=config_changed,
                lang_switched=lang_switched,
                smell_remedy=smell_remedy,
                overcorrection_kind=overcorr_kind,
                raw_user_input=raw_user_input,
                policy=policy,
                state=state,
            )

        state.update(
            {
                "epoch": cfg["epoch"], "tone": cfg["tone"], "overlay_sig": overlay_sig, "lang": lang,
                "model_family": effective_family, "raw_model": raw_model, "session_initialized": True,
                "last_role_policy": policy, "last_transcript_size": cur_t_size,
            }
        )
        if is_new_turn:
            state.update(
                {
                    "last_input_sig": input_sig, "last_turn_id": turn_id, "last_mode": active_mode,
                    "allow_disk_edits": allows_disk_edits(raw_user_input, active_mode),
                    "turn_stop_count": 0, "turn_count": next_turn_count,
                }
            )
            if latest_step_idx >= 0:
                state["last_user_step_idx"] = latest_step_idx
        save_session_state(host, session_id, state)
        return _emit_inject(host, event_name, "\n".join(inject_lines)) if inject_lines else {}

    return {}


def _fail_open_bytes(raw_probe: bytes) -> bytes:
    import re

    if re.search(rb'"hookEventName"\s*:\s*"Stop"', raw_probe):
        return b'{"decision":"allow"}\n'
    return b"{}\n"


def main() -> int:
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        last_chunk = raw[-4096:]
        drained = 0
        while drained < 33_554_432:
            chunk = sys.stdin.buffer.read(65_536)
            if not chunk:
                break
            drained += len(chunk)
            last_chunk = (last_chunk + chunk)[-4096:]
        sys.stderr.write("unarmored_hook warning: stdin payload exceeds limit; failing open\n")
        sys.stdout.buffer.write(_fail_open_bytes(raw[:4096] + b" " + last_chunk))
        sys.stdout.buffer.flush()
        return 0

    if not raw.strip():
        sys.stdout.buffer.write(b"{}\n")
        sys.stdout.buffer.flush()
        return 0

    try:
        payload = json.loads(raw.decode("utf-8-sig"), parse_constant=_reject_json_constant)
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be a JSON object")
    except Exception as exc:
        sys.stderr.write(f"unarmored_hook: invalid JSON input ({exc})\n")
        return 1

    try:
        output = process_event(payload)
    except Exception as exc:
        sys.stderr.write(f"unarmored_hook warning: {exc}\n")
        if payload.get("hookEventName") == "Stop":
            output = {"decision": "allow"}
        else:
            output = {}

    if "__raw_text__" in output:
        encoded = (str(output["__raw_text__"]) + "\n").encode("utf-8")
    else:
        encoded = (json.dumps(output, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
