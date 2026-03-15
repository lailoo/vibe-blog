# 搜索结果提炼与缺口分析 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `distill()` and `analyze_gaps()` methods to ResearcherAgent so search results are deeply extracted into structured materials and gap analysis before reaching Planner/Writer.

**Architecture:** Two new Jinja2 prompt templates (`distill_sources.j2`, `analyze_gaps.j2`) drive two new LLM calls in ResearcherAgent. The structured output flows into state as new fields (`distilled_sources`, `content_gaps`, `writing_recommendations`, etc.), which Planner and Writer templates conditionally render. All new fields have defaults for backward compatibility.

**Tech Stack:** Jinja2 templates, Python (researcher.py, planner.py, prompt_manager.py, planner.j2, writer.j2, state.py)

---

## Task 1: Create `distill_sources.j2` prompt template

**Files:**
- Create: `backend/infrastructure/prompts/blog/distill_sources.j2`

**Step 1: Create the template file**

```jinja2
你是一个专业的技术内容分析师。请对以下搜索结果进行深度提炼。

## 主题
{{ topic }}

## 搜索结果
{% for result in search_results %}
### 来源 {{ loop.index }}: {{ result.get('title', '未知标题') }}
URL: {{ result.get('url', result.get('source', '')) }}
内容摘要: {{ result.get('content', '')[:500] }}

{% endfor %}

## 分析任务

### 1. 逐条提炼
对每条搜索结果，提取：
- **核心观点**：这条结果最重要的 1-2 个观点
- **关键数据**：任何具体的数字、统计、性能指标（必须原样保留）
- **独特视角**：这条结果有什么别的来源没有的信息
- **内容分类**：concept（概念解释）/ case（实践案例）/ data（数据统计）/ comparison（对比分析）/ tutorial（教程步骤）
- **可信度**：high（官方文档/权威博客）/ medium（技术博客）/ low（论坛/问答）

### 2. 语义级去重与合并
- **完全重复**：多条结果讲的是同一件事 → 合并为一条，保留最权威来源的 URL
- **部分重叠**：核心观点相同但各有补充 → 合并观点，保留所有独特数据点
- **观点冲突**：内容相似但结论不同 → 不合并，标记为矛盾点

### 3. 跨源分析
- **共同主题**：多个来源都提到的关键点（说明这是共识）
- **矛盾点**：不同来源的观点冲突（说明这是争议点，可以深入讨论）
- **素材分类汇总**：按 concept/case/data/comparison 分类整理所有素材

## 输出格式
严格返回以下 JSON 格式（不要输出其他内容）：
```json
{
  "sources": [
    {
      "title": "原标题",
      "url": "原链接",
      "core_insight": "核心观点（1-2句话）",
      "key_data": ["数据1", "数据2"],
      "unique_perspective": "独特视角",
      "content_type": "concept|case|data|comparison|tutorial",
      "credibility": "high|medium|low",
      "relevance_score": 1
    }
  ],
  "common_themes": ["主题1", "主题2"],
  "contradictions": [
    {"point": "争议点", "side_a": "观点A", "side_b": "观点B"}
  ],
  "material_by_type": {
    "concepts": ["概念1", "概念2"],
    "cases": ["案例1"],
    "data": ["数据点1"],
    "comparisons": ["对比1"]
  }
}
```
```

**Step 2: Verify template renders**

Run: `cd /Users/coyote-ll/Documents/git/AiSlide/vibe-blog/backend && python -c "from infrastructure.prompts import get_prompt_manager; pm = get_prompt_manager(); print(len(pm.render('blog/distill_sources', topic='test', search_results=[])))"`

Expected: A number (no errors).

---

## Task 2: Create `analyze_gaps.j2` prompt template

**Files:**
- Create: `backend/infrastructure/prompts/blog/analyze_gaps.j2`

**Step 1: Create the template file**

<!-- PLACEHOLDER_TASK2 -->
```jinja2
你是一个资深技术内容策略师。基于以下素材分析，找出内容缺口和独特写作角度。

## 主题
{{ topic }}

## 文章类型
{{ article_type }}

## 已有素材分析
### 共同主题（多个来源都覆盖了的）
{% for theme in common_themes %}
- {{ theme }}
{% endfor %}

### 素材分类
- 概念解释类素材: {{ material_by_type.get('concepts', []) | length }} 条
- 实践案例类素材: {{ material_by_type.get('cases', []) | length }} 条
- 数据统计类素材: {{ material_by_type.get('data', []) | length }} 条
- 对比分析类素材: {{ material_by_type.get('comparisons', []) | length }} 条

{% if contradictions %}
### 矛盾点
{% for c in contradictions %}
- {{ c.point }}: {{ c.side_a }} vs {{ c.side_b }}
{% endfor %}
{% endif %}

## 分析任务

### 1. 内容缺口
搜索结果没有覆盖但对读者很重要的方面是什么？
考虑：
- 入门读者需要但搜索结果假设已知的前置知识
- 实际使用中会遇到但文档没提到的问题
- 最新的变化或更新（搜索结果可能过时）

### 2. 独特角度
如何让这篇文章与已有内容不同？
考虑：
- 搜索结果中哪类素材最少？（那就是机会）
- 矛盾点可以深入讨论吗？
- 能否提供搜索结果中没有的实战经验？

### 3. 写作建议
基于素材分析，推荐：
- 最适合的文章结构
- 必须覆盖的内容（因为是核心）
- 可以跳过的内容（因为已有大量文章覆盖，读者容易找到）
- 差异化策略（这篇文章的独特价值是什么）

## 输出格式
严格返回以下 JSON 格式（不要输出其他内容）：
```json
{
  "content_gaps": ["缺口1", "缺口2"],
  "unique_angles": [
    {"angle": "角度描述", "reason": "为什么这个角度好"}
  ],
  "writing_recommendations": {
    "recommended_structure": "tutorial|problem-solving|comparison",
    "must_cover": ["必须覆盖的内容1"],
    "can_skip": ["可以跳过的内容1"],
    "differentiation": "差异化策略描述"
  }
}
```
```

**Step 2: Verify template renders**

Run: `cd /Users/coyote-ll/Documents/git/AiSlide/vibe-blog/backend && python -c "from infrastructure.prompts import get_prompt_manager; pm = get_prompt_manager(); print(len(pm.render('blog/analyze_gaps', topic='test', article_type='tutorial', common_themes=[], material_by_type={}, contradictions=[])))"`

Expected: A number (no errors).

---

## Task 3: Add render methods to prompt_manager.py

**Files:**
- Modify: `backend/infrastructure/prompts/prompt_manager.py:140-172`

**Step 1: Add `render_distill_sources` method**

After `render_search_query` (line 138), add:

```python
def render_distill_sources(
    self,
    topic: str,
    search_results: list = None
) -> str:
    """渲染搜索结果深度提炼 Prompt"""
    return self.render(
        'blog/distill_sources',
        topic=topic,
        search_results=search_results or []
    )
```

**Step 2: Add `render_analyze_gaps` method**

After `render_distill_sources`, add:

```python
def render_analyze_gaps(
    self,
    topic: str,
    article_type: str = "tutorial",
    common_themes: list = None,
    material_by_type: dict = None,
    contradictions: list = None
) -> str:
    """渲染缺口分析 Prompt"""
    return self.render(
        'blog/analyze_gaps',
        topic=topic,
        article_type=article_type,
        common_themes=common_themes or [],
        material_by_type=material_by_type or {},
        contradictions=contradictions or []
    )
```

**Step 3: Add new parameters to `render_planner`**

Add these parameters to `render_planner()` signature and pass-through:

```python
distilled_sources: list = None,
content_gaps: list = None,
writing_recommendations: dict = None,
material_by_type: dict = None,
common_themes: list = None,
contradictions: list = None,
```

And in the `self.render()` call:

```python
distilled_sources=distilled_sources or [],
content_gaps=content_gaps or [],
writing_recommendations=writing_recommendations or {},
material_by_type=material_by_type or {},
common_themes=common_themes or [],
contradictions=contradictions or [],
```

**Step 4: Verify**

Run: `cd /Users/coyote-ll/Documents/git/AiSlide/vibe-blog/backend && python -c "from infrastructure.prompts import get_prompt_manager; pm = get_prompt_manager(); print('render_distill_sources' in dir(pm)); print('render_analyze_gaps' in dir(pm))"`

Expected: `True` twice.

---

## Task 4: Implement `distill()` and `analyze_gaps()` in researcher.py

**Files:**
- Modify: `backend/services/blog_generator/agents/researcher.py`

**Step 1: Add `distill()` method after `summarize()`**

```python
def distill(self, topic: str, search_results: List[Dict]) -> Dict[str, Any]:
    """
    深度提炼搜索结果（类 OpenDraft Scribe）

    Args:
        topic: 技术主题
        search_results: 原始搜索结果

    Returns:
        提炼后的结构化素材
    """
    if not search_results:
        return {
            "sources": [],
            "common_themes": [],
            "contradictions": [],
            "material_by_type": {"concepts": [], "cases": [], "data": [], "comparisons": []}
        }

    # 尝试从缓存获取
    if self.cache:
        result_urls = [r.get('url', '') for r in search_results[:15]]
        cached_result = self.cache.get(
            'distill',
            topic=topic,
            result_urls=result_urls
        )
        if cached_result is not None:
            return cached_result

    pm = get_prompt_manager()
    prompt = pm.render_distill_sources(
        topic=topic,
        search_results=search_results[:15]
    )

    try:
        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        # 提取 JSON
        json_str = response.strip()
        if '```json' in json_str:
            json_str = json_str.split('```json')[1].split('```')[0].strip()
        elif '```' in json_str:
            json_str = json_str.split('```')[1].split('```')[0].strip()

        result = json.loads(json_str)

        # 确保必要字段存在
        result.setdefault('sources', [])
        result.setdefault('common_themes', [])
        result.setdefault('contradictions', [])
        result.setdefault('material_by_type', {"concepts": [], "cases": [], "data": [], "comparisons": []})

        logger.info(f"🔬 深度提炼完成: {len(result['sources'])} 条素材, "
                    f"{len(result['common_themes'])} 个共同主题, "
                    f"{len(result['contradictions'])} 个矛盾点")

        # 保存到缓存
        if self.cache:
            result_urls = [r.get('url', '') for r in search_results[:15]]
            self.cache.set(
                'distill',
                result,
                topic=topic,
                result_urls=result_urls
            )

        return result

    except Exception as e:
        logger.error(f"深度提炼失败: {e}")
        return {
            "sources": [],
            "common_themes": [],
            "contradictions": [],
            "material_by_type": {"concepts": [], "cases": [], "data": [], "comparisons": []}
        }
```

**Step 2: Add `analyze_gaps()` method after `distill()`**

```python
def analyze_gaps(self, topic: str, article_type: str, distilled: Dict[str, Any]) -> Dict[str, Any]:
    """
    缺口分析（类 OpenDraft Signal）

    Args:
        topic: 技术主题
        article_type: 文章类型
        distilled: distill() 的输出

    Returns:
        缺口分析结果
    """
    if not distilled or not distilled.get('sources'):
        return {
            "content_gaps": [],
            "unique_angles": [],
            "writing_recommendations": {}
        }

    # 尝试从缓存获取
    if self.cache:
        cached_result = self.cache.get(
            'analyze_gaps',
            topic=topic,
            article_type=article_type,
            themes_count=len(distilled.get('common_themes', []))
        )
        if cached_result is not None:
            return cached_result

    pm = get_prompt_manager()
    prompt = pm.render_analyze_gaps(
        topic=topic,
        article_type=article_type,
        common_themes=distilled.get('common_themes', []),
        material_by_type=distilled.get('material_by_type', {}),
        contradictions=distilled.get('contradictions', [])
    )

    try:
        response = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )

        # 提取 JSON
        json_str = response.strip()
        if '```json' in json_str:
            json_str = json_str.split('```json')[1].split('```')[0].strip()
        elif '```' in json_str:
            json_str = json_str.split('```')[1].split('```')[0].strip()

        result = json.loads(json_str)

        # 确保必要字段存在
        result.setdefault('content_gaps', [])
        result.setdefault('unique_angles', [])
        result.setdefault('writing_recommendations', {})

        logger.info(f"🔍 缺口分析完成: {len(result['content_gaps'])} 个缺口, "
                    f"{len(result['unique_angles'])} 个独特角度")

        # 保存到缓存
        if self.cache:
            self.cache.set(
                'analyze_gaps',
                result,
                topic=topic,
                article_type=article_type,
                themes_count=len(distilled.get('common_themes', []))
            )

        return result

    except Exception as e:
        logger.error(f"缺口分析失败: {e}")
        return {
            "content_gaps": [],
            "unique_angles": [],
            "writing_recommendations": {}
        }
```

---

## Task 5: Update `researcher.py` `run()` to call distill + analyze_gaps

**Files:**
- Modify: `backend/services/blog_generator/agents/researcher.py:340-470` (the `run()` method)

**Step 1: Add distill + analyze_gaps calls after summarize**

After the existing `summary = self.summarize(...)` block (around line 418-422) and before `# 3. 更新状态` (line 430), insert:

```python
        # 2.5 深度提炼 + 缺口分析（52号方案）
        distilled = {}
        gap_analysis = {}
        if search_results:
            logger.info("🔬 开始深度提炼搜索结果...")
            distilled = self.distill(topic, search_results)

            logger.info("🔍 开始缺口分析...")
            article_type = state.get('article_type', 'tutorial')
            gap_analysis = self.analyze_gaps(topic, article_type, distilled)
```

**Step 2: Write new state fields after existing state updates**

After `state['verbatim_data'] = ...` (around line 447), add:

```python
        # 5. 更新 52号方案相关状态
        state['distilled_sources'] = distilled.get('sources', [])
        state['material_by_type'] = distilled.get('material_by_type', {})
        state['common_themes'] = distilled.get('common_themes', [])
        state['contradictions'] = distilled.get('contradictions', [])
        state['content_gaps'] = gap_analysis.get('content_gaps', [])
        state['unique_angles'] = gap_analysis.get('unique_angles', [])
        state['writing_recommendations'] = gap_analysis.get('writing_recommendations', {})
```

**Step 3: Update the researcher_output JSON log**

Add the new fields to the `researcher_output` dict (around line 460):

```python
            'distilled_sources': state.get('distilled_sources', []),
            'content_gaps': state.get('content_gaps', []),
            'writing_recommendations': state.get('writing_recommendations', {}),
```

---

## Task 6: Update planner.j2 to display distilled materials and gaps

**Files:**
- Modify: `backend/infrastructure/prompts/blog/planner.j2`

**Step 1: Add distilled materials block**

Insert after `{% endif %}` for `verbatim_data` (after line 47) and before `## 受众适配要求`:

```jinja2
{% if distilled_sources %}
## 📚 深度素材分析（基于搜索结果提炼）

### 按类型分类的素材
{% if material_by_type.get('concepts') %}
**概念解释类**：
{% for item in material_by_type.concepts %}
- {{ item }}
{% endfor %}
{% endif %}

{% if material_by_type.get('cases') %}
**实践案例类**：
{% for item in material_by_type.cases %}
- {{ item }}
{% endfor %}
{% endif %}

{% if material_by_type.get('data') %}
**数据统计类**（必须原样引用）：
{% for item in material_by_type.data %}
- {{ item }}
{% endfor %}
{% endif %}

{% if material_by_type.get('comparisons') %}
**对比分析类**：
{% for item in material_by_type.comparisons %}
- {{ item }}
{% endfor %}
{% endif %}

### 多源共识
{% for theme in common_themes %}
- {{ theme }}
{% endfor %}

{% if contradictions %}
### ⚡ 争议点（建议在文章中讨论）
{% for c in contradictions %}
- **{{ c.point }}**：{{ c.side_a }} vs {{ c.side_b }}
{% endfor %}
{% endif %}
{% endif %}

{% if content_gaps %}
## 🔍 内容缺口（搜索结果未覆盖的重要方面）
{% for gap in content_gaps %}
- {{ gap }}
{% endfor %}

**请在大纲中安排章节覆盖这些缺口，这是让文章有深度的关键。**
{% endif %}

{% if writing_recommendations %}
## 💡 写作策略建议
- **推荐结构**：{{ writing_recommendations.get('recommended_structure', '') }}
- **必须覆盖**：{{ writing_recommendations.get('must_cover', []) | join('、') }}
{% if writing_recommendations.get('can_skip') %}
- **可以精简**：{{ writing_recommendations.get('can_skip', []) | join('、') }}（已有大量文章覆盖）
{% endif %}
- **差异化**：{{ writing_recommendations.get('differentiation', '') }}
{% endif %}
```

---

## Task 7: Update planner.py to pass new fields

**Files:**
- Modify: `backend/services/blog_generator/agents/planner.py`

**Step 1: Add new parameters to `generate_outline()` signature**

Add after `verbatim_data: list = None` (line 43):

```python
        distilled_sources: list = None,
        content_gaps: list = None,
        writing_recommendations: dict = None,
        material_by_type: dict = None,
        common_themes: list = None,
        contradictions: list = None,
```

**Step 2: Pass new parameters to `pm.render_planner()`**

Add to the `pm.render_planner()` call (after `verbatim_data=verbatim_data`, line 84):

```python
            distilled_sources=distilled_sources or [],
            content_gaps=content_gaps or [],
            writing_recommendations=writing_recommendations or {},
            material_by_type=material_by_type or {},
            common_themes=common_themes or [],
            contradictions=contradictions or [],
```

**Step 3: Pass new fields in `run()` method**

In the `self.generate_outline()` call inside `run()` (after `verbatim_data=state.get('verbatim_data', [])`, line 170), add:

```python
                distilled_sources=state.get('distilled_sources', []),
                content_gaps=state.get('content_gaps', []),
                writing_recommendations=state.get('writing_recommendations', {}),
                material_by_type=state.get('material_by_type', {}),
                common_themes=state.get('common_themes', []),
                contradictions=state.get('contradictions', []),
```

---

## Task 8: Update state.py with new fields

**Files:**
- Modify: `backend/services/blog_generator/schemas/state.py`

**Step 1: Add new fields to SharedState**

After `verbatim_data: List[dict]` (line 182), add:

```python
    # 52号方案: 搜索结果提炼与缺口分析 (Researcher 输出)
    distilled_sources: List[dict]  # 逐条提炼的结构化素材
    material_by_type: dict  # 按类型分类的素材
    common_themes: List[str]  # 多源共同主题
    contradictions: List[dict]  # 矛盾点
    content_gaps: List[str]  # 内容缺口
    unique_angles: List[dict]  # 独特角度
    writing_recommendations: dict  # 写作建议
```

**Step 2: Add defaults in `create_initial_state()`**

After `verbatim_data=[],` (line 295), add:

```python
        # 52号方案
        distilled_sources=[],
        material_by_type={},
        common_themes=[],
        contradictions=[],
        content_gaps=[],
        unique_angles=[],
        writing_recommendations={},
```

---

## Task 9: Verify end-to-end with template rendering

**Step 1: Run a full template render test**

Run:
```bash
cd /Users/coyote-ll/Documents/git/AiSlide/vibe-blog/backend && python -c "
from infrastructure.prompts import get_prompt_manager
pm = get_prompt_manager()

# Test distill_sources template
p1 = pm.render_distill_sources(topic='LangGraph', search_results=[{'title': 'test', 'url': 'http://test.com', 'content': 'test content'}])
print(f'distill_sources: {len(p1)} chars')

# Test analyze_gaps template
p2 = pm.render_analyze_gaps(topic='LangGraph', article_type='tutorial', common_themes=['theme1'], material_by_type={'concepts': ['c1'], 'cases': [], 'data': [], 'comparisons': []}, contradictions=[])
print(f'analyze_gaps: {len(p2)} chars')

# Test planner with new fields
p3 = pm.render_planner(topic='LangGraph', distilled_sources=[{'title': 'test'}], content_gaps=['gap1'], writing_recommendations={'recommended_structure': 'tutorial', 'must_cover': ['core'], 'differentiation': 'unique'}, material_by_type={'concepts': ['c1'], 'cases': [], 'data': ['d1'], 'comparisons': []}, common_themes=['theme1'], contradictions=[{'point': 'p', 'side_a': 'a', 'side_b': 'b'}])
print(f'planner with 52: {len(p3)} chars')
assert '深度素材分析' in p3
assert '内容缺口' in p3
assert '写作策略建议' in p3
print('All assertions passed!')
"
```

Expected: Three char counts and "All assertions passed!".

---

## Summary

| Task | File | Change |
|------|------|--------|
| 1 | `distill_sources.j2` | **Create** — deep extraction prompt template |
| 2 | `analyze_gaps.j2` | **Create** — gap analysis prompt template |
| 3 | `prompt_manager.py` | **Modify** — add render_distill_sources, render_analyze_gaps, extend render_planner |
| 4 | `researcher.py` | **Modify** — add distill() and analyze_gaps() methods |
| 5 | `researcher.py` | **Modify** — update run() to call distill + analyze_gaps, write new state fields |
| 6 | `planner.j2` | **Modify** — add distilled materials, gaps, writing recommendations display |
| 7 | `planner.py` | **Modify** — pass new fields to render_planner |
| 8 | `state.py` | **Modify** — add new SharedState fields and defaults |
| 9 | — | **Verify** — end-to-end template rendering test |
