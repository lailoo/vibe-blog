# 素材预分配 + 核心问题驱动写作 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let Planner assign materials to specific sections and set a core_question per section, so Writer writes focused answers instead of expanding bullet points.

**Architecture:** Planner prompt gets new guidance sections for `core_question` and `assigned_materials`. Writer prompt gets a new `assigned_materials` display block. Assembler gets `{source_NNN}` replacement. All new fields have defaults for backward compatibility.

**Tech Stack:** Jinja2 templates, Python (planner.py, writer.py, assembler.py, prompt_manager.py)

---

## Task 1: Add `core_question` guidance to planner.j2

**Files:**
- Modify: `backend/infrastructure/prompts/blog/planner.j2`

**Step 1: Add core_question design guidance after the narrative_role table**

Insert the following block after the `narrative_role` table (after the line `| catalog_item | 清单条目 | catalog 模式 |`) and before `## 字数分配规则`:

```jinja2
### 第四步：为每个章节设置核心问题（core_question）

每个章节必须有一个 `core_question`，它决定了 Writer 的写作目标。Writer 将围绕这个问题组织论述，而不是逐个展开 content_outline 中的要点。

**core_question 设计规则：**
1. **具体**，不能是标题的疑问句形式
   - ❌ "什么是 Skill？"（太泛）
   - ✅ "Skill 到底是什么？它和普通 Prompt 有什么本质区别？"（具体、有对比）
2. **可回答**，Writer 能用 content_outline 中的要点来回答
3. **暗示写作方向**，引导 Writer 用特定角度组织内容
   - ❌ "介绍 LangGraph"（没有方向）
   - ✅ "LangGraph 的四个核心概念是怎么协作的？一个请求从进入到输出经历了什么？"
4. **相邻章节的 core_question 要形成逻辑递进**

**narrative_role → core_question 推荐模板：**

| narrative_role | 推荐的 core_question 模板 |
|---------------|-------------------------|
| hook | "读者为什么应该关心这个话题？这和他的日常有什么关系？" |
| what | "X 到底是什么？它和 Y 有什么本质区别？" |
| why | "没有 X 会怎样？有了 X 能改善多少？有数据吗？" |
| how | "具体怎么做？最少需要哪些步骤？读者能跟着做吗？" |
| compare | "A 和 B 在哪些维度上有差异？什么场景该选哪个？" |
| deep_dive | "底层到底是怎么工作的？为什么要这样设计而不是那样？" |
| verify | "怎么证明这个方案有效？有没有测试数据或真实案例？" |
| summary | "读者读完整篇文章后，应该记住哪 3 个核心要点？" |
| catalog_item | "这个问题的本质是什么？Naive 方案为什么失败？怎么修复？" |
```

**Step 2: Add `core_question` to the JSON output schema**

In the `## 输出要求` section, add `core_question` field to each section object:

```json
"core_question": "本章核心问题（具体、可回答、暗示写作方向）",
```

Insert it after `"narrative_role"` and before `"target_words"`.

**Step 3: Verify template renders**

Run: `cd /Users/coyote-ll/Documents/git/AiSlide/vibe-blog/backend && python -c "from infrastructure.prompts import get_prompt_manager; pm = get_prompt_manager(); print(len(pm.render_planner(topic='test', article_type='tutorial')))"`

Expected: A number (no errors).

---

## Task 2: Add `assigned_materials` guidance to planner.j2

**Files:**
- Modify: `backend/infrastructure/prompts/blog/planner.j2`

**Step 1: Add material assignment guidance block**

Insert the following block before `## 输出要求`, after the core_question guidance:

```jinja2
{% if search_results %}
## 素材预分配

在设计大纲时，请同时将以下搜索素材分配到具体章节。

### 可用素材清单

{% for result in search_results %}
**素材 {{ loop.index }}**
> {{ result.get('title', '未知标题') }}
> {{ result.get('content', '')[:200] }}...
来源：{{ result.get('source', '未知') }}

{% endfor %}

### 分配规则

1. 每条素材至少分配到一个章节（不要遗漏）
2. 每个章节分配 1-3 条素材
3. 为每条分配的素材指定用途：`data_support`（数据支撑）/ `case_study`（案例引用）/ `concept_explain`（概念解释）/ `comparison`（对比分析）/ `best_practice`（最佳实践）/ `tutorial_step`（教程步骤）
4. 标记优先级：`must_use`（必须使用）/ `recommended`（推荐）/ `optional`（可选）
5. 用一句话告诉 Writer 怎么使用这条素材

### 输出格式

在每个 section 中添加 `assigned_materials` 数组：
```json
{
  "source_index": 1,
  "use_as": "data_support",
  "priority": "must_use",
  "instruction": "用这个数据证明 X 的价值"
}
```
{% endif %}
```

**Step 2: Add `assigned_materials` to JSON output schema**

In the `## 输出要求` section, add to each section object:

```json
"assigned_materials": [{"source_index": 1, "use_as": "data_support", "priority": "must_use", "instruction": "使用指导"}],
```

Insert it after `"content_outline"` and before `"verbatim_data_refs"`.

**Step 3: Update prompt_manager.py to pass search_results to planner**

In `render_planner()`, add `search_results` parameter and pass it through.

**Step 4: Update planner.py to pass search_results**

In `generate_outline()` and `run()`, pass `search_results` from state to prompt_manager.

---

## Task 3: Update prompt_manager.py

**Files:**
- Modify: `backend/infrastructure/prompts/prompt_manager.py:140-172`

**Step 1: Add `search_results` parameter to `render_planner`**

```python
def render_planner(
    self,
    topic: str,
    article_type: str = "tutorial",
    target_audience: str = "intermediate",
    audience_adaptation: str = "technical-beginner",
    target_length: str = "medium",
    background_knowledge: str = None,
    key_concepts: list = None,
    target_sections_count: int = None,
    target_images_count: int = None,
    target_code_blocks_count: int = None,
    target_word_count: int = None,
    instructional_analysis: dict = None,
    verbatim_data: list = None,
    search_results: list = None  # NEW
) -> str:
    """渲染 Planner Prompt"""
    return self.render(
        'blog/planner',
        topic=topic,
        article_type=article_type,
        target_audience=target_audience,
        audience_adaptation=audience_adaptation,
        target_length=target_length,
        background_knowledge=background_knowledge,
        key_concepts=key_concepts or [],
        target_sections_count=target_sections_count,
        target_images_count=target_images_count,
        target_code_blocks_count=target_code_blocks_count,
        target_word_count=target_word_count,
        instructional_analysis=instructional_analysis,
        verbatim_data=verbatim_data or [],
        search_results=search_results or []  # NEW
    )
```

**Step 2: Add `assigned_materials` parameter to `render_writer`**

```python
def render_writer(
    self,
    section_outline: dict,
    previous_section_summary: str = None,
    next_section_preview: str = None,
    background_knowledge: str = None,
    audience_adaptation: str = "technical-beginner",
    search_results: list = None,
    verbatim_data: list = None,
    learning_objectives: list = None,
    narrative_mode: str = "",
    narrative_flow: dict = None,
    assigned_materials: list = None  # NEW
) -> str:
    """渲染 Writer Prompt"""
    return self.render(
        'blog/writer',
        section_outline=section_outline,
        previous_section_summary=previous_section_summary,
        next_section_preview=next_section_preview,
        background_knowledge=background_knowledge,
        audience_adaptation=audience_adaptation,
        search_results=search_results or [],
        verbatim_data=verbatim_data or [],
        learning_objectives=learning_objectives or [],
        narrative_mode=narrative_mode,
        narrative_flow=narrative_flow or {},
        assigned_materials=assigned_materials or []  # NEW
    )
```

---

## Task 4: Update planner.py to pass search_results and setdefault new fields

**Files:**
- Modify: `backend/services/blog_generator/agents/planner.py`

**Step 1: Add `search_results` parameter to `generate_outline()`**

Add `search_results: list = None` to the method signature, and pass it to `pm.render_planner()`:

```python
search_results=search_results or []
```

**Step 2: Add setdefault for new fields after JSON parsing**

After `outline = json.loads(response_text)` and the ID assignment loop, add:

```python
# Ensure new fields have defaults
for section in outline.get('sections', []):
    section.setdefault('core_question', '')
    section.setdefault('assigned_materials', [])
```

**Step 3: Pass search_results in `run()` method**

In the `run()` method, extract `search_results` from state and pass to `generate_outline()`:

```python
search_results=state.get('search_results', [])
```

---

## Task 5: Update writer.py to enrich and pass assigned_materials

**Files:**
- Modify: `backend/services/blog_generator/agents/writer.py`

**Step 1: Add material enrichment in `write_section()`**

Before calling `pm.render_writer()`, extract and enrich `assigned_materials`:

```python
# Enrich assigned_materials with actual source data
assigned_materials = []
raw_materials = section_outline.get('assigned_materials', [])
for mat in raw_materials:
    source_idx = mat.get('source_index', 0)
    enriched = dict(mat)
    # Attach source data if available (1-indexed)
    if search_results and 0 < source_idx <= len(search_results):
        source = search_results[source_idx - 1]
        enriched['title'] = source.get('title', '')
        enriched['url'] = source.get('source', source.get('url', ''))
        enriched['core_insight'] = source.get('content', '')[:300]
    assigned_materials.append(enriched)
```

**Step 2: Pass `assigned_materials` to `pm.render_writer()`**

Add `assigned_materials=assigned_materials` to the render call.

**Step 3: Update the `run()` method task construction**

In the task dict construction inside `run()`, the `search_results` is already passed. No change needed since `write_section` already receives it.

---

## Task 6: Add assigned_materials display to writer.j2

**Files:**
- Modify: `backend/infrastructure/prompts/blog/writer.j2`

**Step 1: Add assigned_materials block**

Insert after the existing `core_question` block (after `{% endif %}` for core_question) and before `## 🎭 叙事策略指导`:

```jinja2
{% if assigned_materials %}
### 本章节预分配素材

以下素材已由 Planner 分配给本章节，请按指示使用：

{% for mat in assigned_materials %}
**素材 {{ mat.source_index }}**（{{ mat.use_as }}{% if mat.priority == "must_use" %} ⚠️ 必须使用{% endif %}）
{% if mat.core_insight is defined and mat.core_insight %}
> {{ mat.core_insight[:200] }}
{% endif %}
📝 使用指导：{{ mat.instruction }}
{% if mat.url is defined and mat.url %}
🔗 来源：[{{ mat.title | default('来源') }}]({{ mat.url }})
{% endif %}

{% endfor %}

**使用要求：**
- `must_use` 素材必须在本章节中引用，不能忽略
- 引用时请自然融入行文，不要生硬堆砌
- 引用数据时标注来源，使用 `{source_NNN}` 占位符（NNN 为素材编号），如：`根据实测数据，效率提升了 40% {source_002}`
{% endif %}
```

---

## Task 7: Add {source_NNN} replacement to assembler.py

**Files:**
- Modify: `backend/services/blog_generator/agents/assembler.py`

**Step 1: Add source replacement method**

Add a new method to `AssemblerAgent`:

```python
def replace_source_references(self, content: str, search_results: List[Dict]) -> str:
    """
    Replace {source_NNN} placeholders with actual source links.

    Args:
        content: Markdown content with {source_NNN} placeholders
        search_results: List of search results (1-indexed in placeholders)

    Returns:
        Content with placeholders replaced by markdown links
    """
    import re

    def replace_match(match):
        idx = int(match.group(1))
        if 0 < idx <= len(search_results):
            source = search_results[idx - 1]
            title = source.get('title', '来源')
            url = source.get('source', source.get('url', ''))
            if url:
                return f"（[{title}]({url})）"
            return f"（{title}）"
        return match.group(0)  # Keep original if index out of range

    return re.sub(r'\{source_(\d{1,3})\}', replace_match, content)
```

**Step 2: Call it in `assemble()` method**

In the `assemble()` method, after `replace_placeholders()` and before `body_parts.append(content)`, add:

```python
# Replace {source_NNN} with actual source links
content = self.replace_source_references(content, search_results)
```

**Step 3: Update `assemble()` signature to accept `search_results`**

Add `search_results: List[Dict] = None` parameter.

**Step 4: Update `run()` to pass search_results**

```python
search_results = state.get('search_results', [])
```

Pass it to `self.assemble(..., search_results=search_results)`.

---

## Task 8: Save baseline and run A/B evaluation

**Step 1: Start backend**

```bash
cd /Users/coyote-ll/Documents/git/AiSlide/vibe-blog/backend
# Start the backend server (if not already running)
```

**Step 2: Save baseline (before changes)**

```bash
cd /Users/coyote-ll/Documents/git/AiSlide/vibe-blog/backend
python tests/test_54_55_ab_quality_eval.py --save-baseline
```

**Step 3: Run comparison (after changes)**

```bash
python tests/test_54_55_ab_quality_eval.py --compare
```

Expected: New version scores higher on coherence (维度1) and progression (维度2) dimensions.

---

## Summary

| Task | File | Change |
|------|------|--------|
| 1 | planner.j2 | core_question guidance + JSON schema |
| 2 | planner.j2 | assigned_materials guidance + JSON schema |
| 3 | prompt_manager.py | Add search_results to render_planner, assigned_materials to render_writer |
| 4 | planner.py | Pass search_results, setdefault new fields |
| 5 | writer.py | Enrich assigned_materials with source data |
| 6 | writer.j2 | Display assigned_materials block |
| 7 | assembler.py | {source_NNN} replacement |
| 8 | — | A/B evaluation |
