"""
agent.py - 文献简报 Agent
S12 - AI 自主调度工具链生成图文简报

Agent 读取 TOOL_REGISTRY 中的工具列表，
根据系统提示词自主决定何时调用哪个工具，
最终生成完整 Word 简报。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from papers import Paper
from config import cfg
from tools import (
    TOOL_REGISTRY,
    search_papers,
    score_papers,
    download_paper,
    extract_images,
    extract_text,
    read_paper,
    generate_text,
    generate_caption,
    save_to_doc,
    generate_poster_script,
    generate_poster_image,
)


# ============================================================
# Agent 系统提示词
# ============================================================

AGENT_SYSTEM_PROMPT = """你是一个专业的文献简报生成 Agent。你的任务是为一篇或多篇学术论文生成完整、图文并茂的 Word 简报。

## 你的工具

你有以下工具可以使用：

{tool_descriptions}

## 工作流程

请严格按照以下顺序执行（必要时循环）：

0. **搜索论文**（如果用户给了主题/关键词但没有提供论文列表）— 调用 search_papers
1. **筛选论文**（如果论文数量较多或用户提供了筛选要求）— 调用 score_papers 对论文评分并过滤，只保留相关性高的论文
2. **下载 PDF** — 如果本地没有这篇论文的 PDF，先调用 download_paper
3. **提取全文** — 调用 extract_text 获取论文完整文字内容
4. **深度阅读** — 调用 read_paper 让 AI 消化论文，输出摘要/关键发现/判断是否值得收录/决定重点图
5. **提取图片**（如果 read_paper 推荐了图片）— 调用 extract_images 提取 PDF 中的图片
6. **生成图注** — 对每张选中的图调用 generate_caption
7. **保存文档** — 调用 save_to_doc 组装最终 Word 文档

## 重要原则

- 筛选优先：如果论文列表超过 5 篇，或用户提供了筛选要求，必须先调用 score_papers 筛选，再处理剩余论文
- 每篇论文都需要：下载 → 提取全文 → 生成解读 → 保存
- 图片是可选的：如果论文 PDF 没有可提取的图片（纯文本 PDF），可以跳过图相关步骤
- 图注：优先用多模态模型看图生成描述，如果模型不支持则用上下文推断
- 保存路径：默认保存到 reports/ 目录，文件名格式 "{{arxiv_id}}_{{标题前20字}}.docx"
- 输出：最终返回生成的 Word 文档路径列表

## 你的输出格式

请按以下 JSON 格式返回你的执行结果：
{{
  "status": "success" 或 "partial",
  "papers_processed": N,
  "reports": ["path/to/report1.docx", ...],
  "errors": ["错误描述"]  // 可选
}}

现在开始为论文生成简报。"""


def _build_tool_descriptions() -> str:
    lines = []
    for name, info in TOOL_REGISTRY.items():
        lines.append(
            f"- **{name}**({info['input']})\n"
            f"  {info['description']}\n"
            f"  返回: {info['returns']}"
        )
    return "\n".join(lines)


OPENCLAW_SYSTEM_PROMPT = """你是 openclaw，一个专注于学术文献筛选的 AI 助手。你的任务是从给定的论文列表中筛选出与研究主题最相关的论文。

## 你的工具

你有以下工具可以使用：

{tool_descriptions}

## 工作流程

1. **评分筛选** — 调用 score_papers 工具，传入论文列表和研究主题，对所有论文进行相关性评分并过滤
2. **返回结果** — 将筛选结果以 JSON 格式返回

## 重要原则

- 必须调用 score_papers 工具完成筛选，不要自行判断
- score_papers 会返回通过阈值的论文列表（filtered 字段）
- 筛选完成后直接返回结果，不要做其他操作

## 输出格式

{{
  "status": "success",
  "filtered_ids": ["arxiv_id_1", "arxiv_id_2", ...],
  "total": N,
  "passed": M
}}"""


class OpenclawFilter:
    """openclaw 筛选器：用 brief LLM + score_papers 工具筛选论文"""

    def __init__(self, topic: str, sift_requirement: str = ""):
        self.topic = topic
        self.sift_requirement = sift_requirement.strip()
        from reporter import LLMCaller
        brief_cfg = cfg.get("brief") or {}
        fallback = {
            "provider": "custom",
            "api_key": cfg.get("api_key", ""),
            "base_url": cfg.get("base_url", "https://api.deepseek.com"),
            "model": cfg.get("model", "deepseek-chat"),
            "max_tokens": 1000,
            "temperature": 0.3,
        }
        llm_cfg = brief_cfg if brief_cfg else fallback
        self.llm = LLMCaller(llm_cfg)

    def filter(self, papers: list, on_progress=None) -> list:
        """调用 LLM + score_papers 工具筛选论文，返回通过的 Paper 列表"""
        tool_desc_lines = []
        for name in ("score_papers",):
            info = TOOL_REGISTRY[name]
            tool_desc_lines.append(
                f"- **{name}**({info['input']})\n  {info['description']}\n  返回: {info['returns']}"
            )

        system_msg = OPENCLAW_SYSTEM_PROMPT.format(tool_descriptions="\n".join(tool_desc_lines))

        paper_list = "\n".join(
            f"- {p.arxiv_id}: {p.title}" for p in papers
        )
        req_part = f"\n\n额外筛选要求：{self.sift_requirement}\n请在筛选时严格参考上述要求。" if self.sift_requirement else ""
        user_msg = (
            f"请筛选以下 {len(papers)} 篇论文，研究主题：{self.topic}"
            f"{req_part}\n\n"
            f"{paper_list}\n\n"
            f"请调用 score_papers 工具完成筛选。"
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        tool_schema = [{
            "type": "function",
            "function": {
                "name": "score_papers",
                "description": TOOL_REGISTRY["score_papers"]["description"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "threshold": {"type": "number"},
                    },
                    "required": ["topic"],
                },
            },
        }]

        # 最多 3 轮，等待 LLM 调用 score_papers
        for _ in range(3):
            try:
                result = self.llm.chat_with_tools(messages, tool_schema, max_tokens=1000, temperature=0.3)
            except Exception as e:
                raise Exception(f"openclaw LLM 调用失败: {e}")

            msg = result.get("choices", [{}])[0].get("message", {})
            messages.append(msg)

            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                break

            for call in tool_calls:
                func = call.get("function", {})
                if func.get("name") == "score_papers":
                    args = json.loads(func.get("arguments", "{}"))
                    if on_progress:
                        on_progress("openclaw 正在评分筛选...")
                    tool_result = score_papers(
                        papers=papers,
                        topic=args.get("topic", self.topic),
                        sift_requirement=self.sift_requirement,
                        threshold=args.get("threshold"),
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps(
                            {"total": tool_result["total"], "passed": tool_result["passed"],
                             "filtered_ids": [p.arxiv_id for p in tool_result["filtered"]]},
                            ensure_ascii=False,
                        ),
                    })
                    # 直接返回筛选结果，不等 LLM 再回复
                    return tool_result["filtered"]

        # LLM 没有调用工具，回退到简单阈值筛选
        return [p for p in papers if p.relevance_score >= 0.5]




class BriefingAgent:
    """文献简报生成 Agent"""

    def __init__(self, topic: str = ""):
        self.topic = topic
        self._setup_llm()

    def _setup_llm(self):
        from reporter import LLMCaller
        brief_cfg = cfg.get("brief") or {}
        fallback = {
            "provider": "custom",
            "api_key": cfg.get("api_key", ""),
            "base_url": cfg.get("base_url", "https://api.deepseek.com"),
            "model": cfg.get("model", "deepseek-chat"),
            "max_tokens": 2000,
            "temperature": 0.5,
        }
        llm_cfg = brief_cfg if brief_cfg else fallback
        self.llm = LLMCaller(llm_cfg)

    def _chat(self, messages: list[dict]) -> str:
        """发送对话，返回回复"""
        return self.llm.chat(messages)

    def _chat_with_tools(self, messages: list[dict], tool_schemas: list) -> dict:
        """
        发送带工具调用指令的对话
        返回 LLM 的回复（可能包含 tool_calls）
        """
        return self.llm.chat_with_tools(messages, tool_schemas)

    def _execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """执行单个工具"""
        if tool_name == "search_papers":
            return search_papers(**arguments)
        elif tool_name == "score_papers":
            return score_papers(**arguments)
        elif tool_name == "download_paper":
            return download_paper(**arguments)
        elif tool_name == "extract_images":
            return extract_images(**arguments)
        elif tool_name == "extract_text":
            return extract_text(**arguments)
        elif tool_name == "read_paper":
            return read_paper(**arguments)
        elif tool_name == "generate_text":
            return generate_text(**arguments)
        elif tool_name == "generate_caption":
            return generate_caption(**arguments)
        elif tool_name == "save_to_doc":
            return save_to_doc(**arguments)
        elif tool_name == "generate_poster_script":
            return generate_poster_script(**arguments)
        elif tool_name == "generate_poster_image":
            return generate_poster_image(**arguments)
        else:
            raise Exception(f"未知工具: {tool_name}")

    def run(self, papers: list[Paper], on_progress: Optional[callable] = None) -> dict:
        """
        运行 Agent 处理论文列表
        返回处理结果
        """
        tool_descriptions = _build_tool_descriptions()
        system_msg = AGENT_SYSTEM_PROMPT.format(
            tool_descriptions=tool_descriptions
        )

        # 构建论文信息摘要（供 Agent 理解任务）
        paper_summary = "\n".join(
            f"- {p.arxiv_id}: {p.title} ({p.display_authors}, {p.submitted_date})"
            for p in papers
        )

        user_msg = f"""【任务】请为以下 {len(papers)} 篇论文生成文献简报。如果论文列表为空，请先用 search_papers 搜索相关论文。

论文列表：
{paper_summary}

搜索主题：{self.topic}

请按工作流程执行，每步调用对应工具。"""

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ]

        tool_schemas = self._get_tool_schemas()
        results = {"status": "success", "papers_processed": 0, "reports": [], "errors": []}
        max_turns = 20
        turn = 0

        while turn < max_turns:
            turn += 1
            if on_progress:
                on_progress(f"Agent 第 {turn} 步...")

            # 调用 LLM（带工具能力）
            try:
                response = self._chat_with_tools(messages, tool_schemas)
            except Exception as e:
                err_str = str(e)
                results["errors"].append(f"LLM 调用失败: {err_str}")
                results["status"] = "partial"
                break

            choices = response.get("choices", [])
            if not choices:
                break

            msg = choices[0].get("message", {})
            messages.append(msg)  # 追加 assistant 消息

            # 检查是否有工具调用
            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                # 没有更多工具调用，检查最终回复
                final_text = msg.get("content", "")
                if final_text:
                    try:
                        result_data = json.loads(final_text)
                        results.update(result_data)
                    except json.JSONDecodeError:
                        results["errors"].append(f"Agent 最终回复解析失败: {final_text[:200]}")
                break

            # 执行工具调用
            for call in tool_calls:
                func = call.get("function", {})
                tool_name = func.get("name", "")
                raw_args = func.get("arguments", "{}")
                try:
                    arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except json.JSONDecodeError:
                    arguments = {}

                if on_progress:
                    on_progress(f"  执行: {tool_name}({list(arguments.keys())})")

                try:
                    result = self._execute_tool(tool_name, arguments)
                    # 追加工具结果到消息
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                except Exception as e:
                    err_msg = f"{tool_name} 执行失败: {e}"
                    if on_progress:
                        on_progress(f"  错误: {err_msg}")
                    results["errors"].append(err_msg)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps({"error": err_msg}),
                    })

        results["papers_processed"] = len(papers)
        return results

    def _get_tool_schemas(self) -> list:
        """返回 OpenAI function calling 格式的工具 schema"""
        schemas = []
        for name, info in TOOL_REGISTRY.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"{info['description']}\n输入: {info['input']}\n返回: {info['returns']}",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            })
        return schemas


# ============================================================
# AI 驱动的搜索+筛选 Agent（激进方案：AI 自主多轮搜索）
# ============================================================

class AIResearcher:
    """
    AI 接管搜索（激进方案）：
    LLM 通过 function calling 自主调用搜索工具，可执行多轮搜索，
    根据结果自行调整策略，最终评分筛选返回论文列表。
    如果模型不支持工具调用，自动回退到简单方案。
    """

    def __init__(self, topic: str, sift_requirement: str = ""):
        self.topic = topic
        self.sift_requirement = sift_requirement.strip()
        from reporter import LLMCaller
        sift_cfg = cfg.get("sift") or {}
        fallback = {
            "provider": cfg.get("llm_provider", "openai"),
            "api_key": cfg.get("api_key", ""),
            "base_url": cfg.get("base_url", "https://api.openai.com/v1"),
            "model": cfg.get("model", "gpt-4o-mini"),
            "max_tokens": 2000,
            "temperature": 0.3,
        }
        llm_cfg = sift_cfg if sift_cfg else fallback
        if not llm_cfg.get("api_key"):
            raise Exception("筛选模型未配置 API Key，请在设置 > 其他AI筛选 > 筛选模型中配置")
        self.llm = LLMCaller(llm_cfg)

    def search(self, max_results: int = 20, sort_by: str = "relevance", on_progress=None) -> "SearchResult":
        """执行 AI 搜索+筛选，返回 SearchResult"""
        # 先尝试激进方案（AI 自主多轮搜索）
        try:
            if on_progress:
                on_progress("AI 正在制定搜索策略...")
            result = self._agent_search(max_results, sort_by, on_progress)
            if result.papers:
                return result
            # 激进方案没搜到，回退简单方案兜底
            if on_progress:
                on_progress("Agent 搜索未找到结果，尝试直接搜索...")
            return self._simple_search(max_results, sort_by, on_progress)
        except Exception as e:
            print(f"# AIResearcher 激进搜索失败，回退到简单方案: {e}")
            if on_progress:
                on_progress(f"Agent 模式失败，回退搜索: {e}")
            return self._simple_search(max_results, sort_by, on_progress)

    def _agent_search(self, max_results: int, sort_by: str, on_progress) -> "SearchResult":
        """激进方案：LLM 通过 function calling 自主多轮搜索。
        每轮搜索后立即评分筛选，把结果反馈给 AI，不满足就继续搜，最多 max_turns 轮。"""
        from searcher import SearchParams, ArxivSearcher
        from scorer import PaperScorer
        from papers import SearchResult

        MAX_TURNS_RAW = cfg.get("ai_search_max_turns", 5)
        # 填 0 表示不限，程序内部用 999 作为实际上限
        MAX_TURNS = 999 if MAX_TURNS_RAW <= 0 else max(1, MAX_TURNS_RAW)
        CONSECUTIVE_EMPTY_STOP = cfg.get("ai_search_consecutive_empty_stop", 5)
        TARGET_COUNT = max_results
        THRESHOLD = cfg.get("auto_score_threshold", 0.6)

        all_passed = []
        passed_ids = set()
        consecutive_empty = 0  # 连续几轮没有新论文通过

        tool_schemas = [{
            "type": "function",
            "function": {
                "name": "search_papers",
                "description": "搜索 arXiv 论文数据库。支持关键词、作者、分类、年份范围等条件。善用 arXiv 高级语法：ti:标题 abs:摘要 au:作者 cat:分类 AND OR ANDNOT。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keywords": {"type": "string", "description": "搜索关键词，支持 arXiv 高级语法"},
                        "author": {"type": "string", "description": "作者名（可选）"},
                        "categories": {"type": "array", "items": {"type": "string"}, "description": "arXiv 分类代码列表"},
                        "year_from": {"type": "integer", "description": "起始年份（可选）"},
                        "year_to": {"type": "integer", "description": "截止年份（可选）"},
                        "max_results": {"type": "integer", "description": f"本轮最多返回多少篇论文，建议不超过 {max_results}"},
                    },
                    "required": ["keywords"],
                },
            },
        }]

        req_text = f"\n筛选要求：{self.sift_requirement}" if self.sift_requirement else ""

        from prompts_manager import prompts
        system_prompt = prompts.get("search_ai").format(
            TARGET_COUNT=TARGET_COUNT,
            CONSECUTIVE_EMPTY_STOP=CONSECUTIVE_EMPTY_STOP if CONSECUTIVE_EMPTY_STOP > 0 else 'N',
            MAX_TURNS=MAX_TURNS if MAX_TURNS < 999 else '（不设限）',
            max_results=max_results,
        )

        user_prompt = f"""请帮我搜索关于「{self.topic}」的学术论文。{req_text}

请调用 search_papers 工具开始搜索。目标是累计找到足够多通过筛选的论文。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for turn in range(MAX_TURNS):
            turn_label = f"{turn + 1}" if MAX_TURNS_RAW <= 0 else f"{turn + 1}/{MAX_TURNS}"
            if on_progress:
                on_progress(f"AI 搜索第 {turn_label} 轮...")

            response = self.llm.chat_with_tools(messages, tool_schemas, max_tokens=1500, temperature=0.3)
            msg = response.get("choices", [{}])[0].get("message", {})
            messages.append(msg)

            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                # AI 主动停止
                break

            for call in tool_calls:
                func = call.get("function", {})
                if func.get("name") != "search_papers":
                    continue
                args = json.loads(func.get("arguments", "{}"))
                params = SearchParams(
                    keywords=args.get("keywords", self.topic),
                    author=args.get("author", ""),
                    categories=args.get("categories") or [],
                    year_from=args.get("year_from"),
                    year_to=args.get("year_to"),
                    max_results=args.get("max_results", max_results),
                    sort_by=sort_by,
                )

                result = ArxivSearcher().search(params)

                # 每轮搜完立即评分筛选
                new_papers = [p for p in result.papers if p.arxiv_id not in passed_ids]
                passed_this_round = 0
                if new_papers and self.sift_requirement:
                    if on_progress:
                        on_progress(f"第 {turn_label} 轮评分中...")
                    scorer = PaperScorer(topic=self.topic, sift_requirement=self.sift_requirement)
                    scored = scorer.score_batch(new_papers, on_progress=lambda cur, tot: on_progress and on_progress(f"第 {turn_label} 轮评分 {cur}/{tot}"))
                    for p in scored:
                        if p.relevance_score >= THRESHOLD and p.arxiv_id not in passed_ids:
                            passed_ids.add(p.arxiv_id)
                            all_passed.append(p)
                            passed_this_round += 1
                elif new_papers:
                    for p in new_papers:
                        if p.arxiv_id not in passed_ids:
                            passed_ids.add(p.arxiv_id)
                            all_passed.append(p)
                            passed_this_round += 1

                # 更新连续空轮计数
                if passed_this_round == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0

                # 构建反馈给 AI
                low_score_samples = [
                    {"title": p.title[:60], "reason": getattr(p, "score_reason", "")[:80]}
                    for p in scored[:5] if p.relevance_score < THRESHOLD
                ] if 'scored' in dir() else []

                feedback = {
                    "round": turn + 1,
                    "found_this_round": len(result.papers),
                    "new_papers": len(new_papers),
                    "passed_this_round": passed_this_round,
                    "total_passed": len(all_passed),
                    "target": TARGET_COUNT,
                    "low_score_examples": low_score_samples,
                }

                # 判断停止条件
                should_stop = False
                stop_reasons = []

                if CONSECUTIVE_EMPTY_STOP > 0 and consecutive_empty >= CONSECUTIVE_EMPTY_STOP:
                    stop_reasons.append(f"连续 {consecutive_empty} 轮没有新论文通过")
                if len(all_passed) >= TARGET_COUNT:
                    stop_reasons.append(f"累计通过数已达标（{len(all_passed)} >= {TARGET_COUNT}）")
                if turn >= MAX_TURNS - 1:
                    stop_reasons.append(f"达到最大搜索轮数（{MAX_TURNS} 轮）")

                if stop_reasons:
                    feedback["instruction"] = "；".join(stop_reasons) + "，请停止搜索。"
                    should_stop = True
                else:
                    feedback["instruction"] = f"累计通过 {len(all_passed)} 篇，请分析原因并调整策略继续搜索。"

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.get("id", ""),
                    "content": json.dumps(feedback, ensure_ascii=False),
                })

                if should_stop:
                    break

            if should_stop:
                break

        return SearchResult(
            query=self.topic,
            total_found=len(all_passed),
            papers=all_passed,
            mode="ai_agent_search",
        )

    def _simple_search(self, max_results: int, sort_by: str, on_progress) -> "SearchResult":
        """简单方案（回退）：LLM 一次性生成搜索参数，程序执行搜索"""
        from searcher import SearchParams, ArxivSearcher
        from scorer import PaperScorer
        from papers import SearchResult

        if on_progress:
            on_progress("正在执行搜索...")

        search_params = self._generate_search_params(max_results, sort_by)
        raw_result = ArxivSearcher().search(search_params)
        papers = raw_result.papers

        if papers and self.sift_requirement:
            if on_progress:
                on_progress("AI 正在评分筛选...")
            scorer = PaperScorer(topic=self.topic, sift_requirement=self.sift_requirement)
            scored = scorer.score_batch(papers, on_progress=lambda cur, tot: on_progress and on_progress(f"AI 评分筛选... {cur}/{tot}"))
            threshold = cfg.get("auto_score_threshold", 0.6)
            papers = [p for p in scored if p.relevance_score >= threshold]

        return SearchResult(
            query=raw_result.query,
            total_found=len(papers),
            papers=papers,
            mode="ai_search",
        )

    def _generate_search_params(self, max_results: int, sort_by: str) -> "SearchParams":
        """让 LLM 根据主题+筛选要求生成搜索参数"""
        from searcher import SearchParams

        req_text = f"\n筛选要求：{self.sift_requirement}\n请在生成搜索参数时充分考虑上述筛选要求。" if self.sift_requirement else ""

        prompt = f"""你是 arXiv 搜索专家。请根据用户的研究主题生成最优的搜索参数。

研究主题：{self.topic}{req_text}

请严格返回以下 JSON（不要包含 markdown 代码块或其他说明文字）：
{{
  "keywords": "优化后的搜索关键词（支持 arXiv 语法 AND/OR/ti:/abs:）",
  "author": "",
  "categories": [],
  "year_from": null,
  "year_to": null,
  "explanation": "简要说明搜索策略"
}}

注意：
- keywords 可以直接用 arXiv 支持的语法，如 "active matter AND abs:experiment"
- categories 是 arXiv 分类代码列表，如 ["cond-mat.soft", "cs.LG"]
- year_from/year_to 是整数年份或 null"""

        messages = [
            {"role": "system", "content": "你是一位精通 arXiv 搜索语法的学术助手，始终只返回纯 JSON，不要有任何额外文字。"},
            {"role": "user", "content": prompt},
        ]

        response = self.llm.chat(messages, temperature=0.3)
        params_dict = self._parse_json(response)

        return SearchParams(
            keywords=params_dict.get("keywords", self.topic),
            author=params_dict.get("author", ""),
            categories=params_dict.get("categories") or [],
            year_from=params_dict.get("year_from"),
            year_to=params_dict.get("year_to"),
            max_results=max_results,
            sort_by=sort_by,
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:] if lines[0].strip() == "```" else lines)
            text = text.rstrip("`").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            print(f"# AIResearcher JSON 解析失败，原始回复: {text[:200]}")
            return {}


# ============================================================
# 快速测试
# ============================================================
if __name__ == "__main__":
    from papers import Paper

    mock_papers = [
        Paper(
            arxiv_id="2301.09550",
            title="Planktonic Active Matter",
            authors=["Anupam Sengupta"],
            abstract="This paper presents a comprehensive study of planktonic active matter...",
            categories=["cond-mat.soft"],
            submitted_date="2023-01-01",
            updated_date="2023-01-01",
            pdf_url="https://arxiv.org/pdf/2301.09550.pdf",
        ),
    ]

    print("Agent 初始化测试...")
    agent = BriefingAgent(topic="active matter")
    print("OK - 请先下载 PDF 再运行 Agent")
    print(f"工具数量: {len(TOOL_REGISTRY)}")
