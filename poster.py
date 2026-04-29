"""
poster.py - 学术海报生成模块（并发流水线版）

流水线架构：
  文本大模型（精炼论文 → 海报脚本）──> 图片大模型（脚本 + 参考图 → 海报图片）
  在图片模型生成 Paper N 时，文本模型同时处理 Paper N+1

文本大模型职责：
  - 接收系统提示词（规范精炼内容格式）
  - 提炼论文核心内容为海报脚本 JSON
  - 可通过 function calling 调用 generate_poster_image 工具

图片大模型职责：
  - 接收系统提示词（规范图片格式）
  - 接收精炼文字 + 参考图片
  - 生成竖版学术海报

支持：OpenAI (DALL-E 3 / gpt-image-1) / 豆包(火山引擎)
"""
import json
import base64
import urllib.request
import urllib.error
import os
import time
import threading
import queue
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
from papers import Paper
from reader import PaperReader
from config import cfg, SSL_CTX

# 图片生成超时（秒）：图片模型通常较慢，设 5 分钟容忍延迟
IMAGE_GEN_TIMEOUT = 300
IMAGE_DOWNLOAD_TIMEOUT = 120
MAX_RETRIES = 1

# ============================================================
# 系统提示词（从 prompts_manager 读取，支持用户自定义）
# ============================================================

def _get_poster_text_prompt() -> str:
    from prompts_manager import prompts
    return prompts.get("poster_script")

def _get_poster_image_prompt() -> str:
    from prompts_manager import prompts
    return prompts.get("poster_image")

# 提示词通过 _get_poster_text_prompt() / _get_poster_image_prompt() 懒加载

# ============================================================
# 工具定义（供文本大模型 function calling）
# ============================================================

POSTER_IMAGE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_poster_image",
            "description": "调用图片生成模型创建学术海报。传入提炼后的结构化内容（标题、核心发现、视觉内容描述等），图片模型将自行决定配色和字体风格。",
            "parameters": {
                "type": "object",
                "properties": {
                    "poster_title": {
                        "type": "string",
                        "description": "海报主标题"
                    },
                    "subtitle": {
                        "type": "string",
                        "description": "副标题"
                    },
                    "core_findings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "核心发现列表（3条，含具体数据）"
                    },
                    "visual_description": {
                        "type": "string",
                        "description": "需要展示的视觉内容描述（英文），聚焦画什么而非怎么配色"
                    },
                    "figure_hints": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "参考图在海报中的使用建议（中文）"
                    },
                    "reference_image_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "需要使用的参考图索引列表（0-based）"
                    }
                },
                "required": ["poster_title", "visual_description"]
            }
        }
    }
]


# ============================================================
# 文本精炼器
# ============================================================

class PosterTextRefiner:
    """文本大模型封装：将论文提炼为海报脚本"""

    def __init__(self, topic: str):
        self.topic = topic
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
        self.llm = LLMCaller(brief_cfg if brief_cfg else fallback)

    def refine(self, paper: Paper, reader: PaperReader) -> dict:
        """
        提炼单篇论文为海报脚本
        返回海报脚本 dict，包含 _paper 和 _reference_images 内部字段
        """
        # Step 1: 提取全文
        full_text = ""
        try:
            full_text = reader.read_full_text(paper)
        except Exception:
            full_text = paper.abstract

        # Step 2: 提取图片
        figures = []
        try:
            figures = reader.extract_all_figures(paper)
        except Exception:
            pass

        # Step 3: 构建参考图描述
        figures_info = ""
        if figures:
            lines = []
            for i, f in enumerate(figures[:6]):
                lines.append(
                    f"- 图{i}: {f.figure_id}, 第{f.page_num}页, "
                    f"尺寸{f.width}x{f.height}px, 大小{f.size_kb:.0f}KB"
                )
            figures_info = "\n".join(lines)
        else:
            figures_info = "无提取到的图片"

        # Step 4: 调用文本大模型
        user_prompt = f"""请为以下论文设计学术海报方案。

论文标题：{paper.title}
作者：{paper.display_authors}
摘要：{paper.abstract[:800]}

论文核心内容（部分）：
{full_text[:4000]}

论文中的图片：
{figures_info}

请按系统提示词要求的 JSON 格式返回海报脚本。"""

        messages = [
            {"role": "system", "content": _get_poster_text_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        response = self.llm.chat(messages, temperature=0.4)

        # Step 5: 解析 JSON
        script = self._parse_script(response, paper)

        # 附加内部字段
        script["_paper"] = paper
        script["_reference_images"] = [f.image_path for f in figures[:3]
                                        if hasattr(f, 'image_path') and f.image_path]
        return script

    def refine_with_tools(self, paper: Paper, reader: PaperReader,
                          image_gen=None) -> dict:
        """
        使用 function calling 模式提炼论文并生成海报。
        文本大模型可以主动调用 generate_poster_image 工具来生成海报图片。
        当工具被调用时，会实际调用图片大模型并返回真实结果。

        参数:
          paper: 论文对象
          reader: PaperReader 实例
          image_gen: PosterImageGenerator 实例（可选，不传则自动创建）

        返回海报脚本 dict，包含 _result 字段（图片生成结果）。
        """
        if image_gen is None:
            image_gen = PosterImageGenerator()
        # 先获取基础内容
        full_text = ""
        try:
            full_text = reader.read_full_text(paper)
        except Exception:
            full_text = paper.abstract

        figures = []
        try:
            figures = reader.extract_all_figures(paper)
        except Exception:
            pass

        reference_images = [f.image_path for f in figures[:3]
                            if hasattr(f, 'image_path') and f.image_path]

        figures_info = ""
        if figures:
            lines = []
            for i, f in enumerate(figures[:6]):
                lines.append(
                    f"- 图{i}: {f.figure_id}, 第{f.page_num}页, "
                    f"尺寸{f.width}x{f.height}px"
                )
            figures_info = "\n".join(lines)

        user_prompt = f"""请为以下论文提炼海报脚本。

论文标题：{paper.title}
作者：{paper.display_authors}
摘要：{paper.abstract[:800]}
核心内容：{full_text[:4000]}
图片列表：{figures_info}

提炼完成后，请调用 generate_poster_image 工具来生成海报。"""

        messages = [
            {"role": "system", "content": _get_poster_text_prompt()},
            {"role": "user", "content": user_prompt},
        ]

        script = None

        # 最多 3 轮对话
        for _ in range(3):
            try:
                result = self.llm.chat_with_tools(
                    messages, POSTER_IMAGE_TOOLS,
                    max_tokens=2000, temperature=0.4,
                )
            except Exception as e:
                print(f"# TextRefiner LLM 调用失败: {e}")
                break

            msg = result.get("choices", [{}])[0].get("message", {})
            messages.append(msg)

            # 提取文本内容中的脚本
            content = msg.get("content", "")
            if content:
                parsed = self._try_parse_json(content)
                if parsed:
                    script = parsed

            tool_calls = msg.get("tool_calls", [])
            if not tool_calls:
                break

            # 处理工具调用 — 实际调用图片大模型
            for call in tool_calls:
                func = call.get("function", {})
                if func.get("name") == "generate_poster_image":
                    args = json.loads(func.get("arguments", "{}"))
                    script = {
                        "poster_title": args.get("poster_title", paper.title[:30]),
                        "subtitle": args.get("subtitle", ""),
                        "core_findings": args.get("core_findings", []),
                        "visual_description": args.get("visual_description", ""),
                        "figure_hints": args.get("figure_hints", []),
                        "figure_selections": args.get("reference_image_indices", []),
                        "_paper": paper,
                        "_reference_images": reference_images,
                    }
                    # 实际调用图片大模型生成海报
                    img_result = image_gen.generate(script)
                    script["_result"] = img_result
                    # 把真实结果返回给文本大模型
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps({
                            "success": img_result.get("success"),
                            "path": img_result.get("path", ""),
                            "error": img_result.get("error", ""),
                            "message": "海报已生成并保存" if img_result.get("success")
                                       else f"生成失败: {img_result.get('error', '')}",
                        }, ensure_ascii=False),
                    })
                    break

        if script is None:
            # 回退：直接用基础提炼
            script = self.refine(paper, reader)

        script["_paper"] = paper
        script["_reference_images"] = reference_images
        return script

    @staticmethod
    def _parse_script(response: str, paper: Paper) -> dict:
        """解析 LLM 返回的 JSON 脚本"""
        response = response.strip()
        parsed = PosterTextRefiner._try_parse_json(response)
        if parsed:
            return parsed
        # 回退默认值
        print(f"# 海报脚本 JSON 解析失败，使用默认值。原始回复: {response[:200]}")
        return {
            "poster_title": paper.title[:30],
            "subtitle": "",
            "core_findings": [paper.abstract[:100]],
            "visual_description": "Academic research poster showing key findings and data visualizations from the paper",
            "figure_hints": [],
            "figure_selections": [],
        }

    @staticmethod
    def _try_parse_json(text: str) -> Optional[dict]:
        """尝试从文本中提取 JSON"""
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:] if lines[0].strip().startswith("```") else lines)
            text = text.rstrip("`").strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None


# ============================================================
# 图片生成器
# ============================================================

class PosterImageGenerator:
    """图片大模型封装：根据脚本 + 参考图生成海报"""

    def __init__(self):
        self.cfg = cfg.get("poster") or {}
        if not self.cfg.get("api_key"):
            raise Exception("海报生成模型未配置 API Key，请在设置中配置")
        self.output_dir = Path(cfg.get("poster_dir", os.path.join(
            os.environ.get("USERPROFILE", os.path.expanduser("~")),
            "literature_brief", "posters"
        )))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.style_template_path = self._find_style_template()

    def _find_style_template(self) -> Optional[str]:
        """在工作区目录查找名为'示例图片'的风格模板"""
        workspace = Path(__file__).parent
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            candidate = workspace / f"示例图片{ext}"
            if candidate.exists():
                return str(candidate)
        return None

    def generate(self, script: dict) -> dict:
        """
        生成单张海报图片（含超时和重试）。
        如果工作区存在风格模板图，会将其传递给图片模型作为参考。
        """
        paper = script.get("_paper")
        ref_images = script.get("_reference_images", [])
        image_prompt = self._build_image_prompt(script)
        provider = self.cfg.get("provider", "openai")

        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                if attempt > 0:
                    print(f"# 图片生成重试 ({attempt}/{MAX_RETRIES}): {paper.arxiv_id if paper else 'unknown'}")
                if provider in ("doubao", "volcengine"):
                    img_data = self._call_doubao(image_prompt, ref_images)
                else:
                    img_data = self._call_openai(image_prompt, ref_images)

                safe_title = "".join(
                    c for c in (paper.title[:15] if paper else "poster")
                    if c.isalnum() or c in " -_"
                ).strip().replace(" ", "_")
                fname = f"poster_{paper.arxiv_id if paper else 'unknown'}_{safe_title}_{datetime.now().strftime('%H%M%S')}.png"
                path = self.output_dir / fname
                with open(path, "wb") as f:
                    f.write(img_data)

                return {
                    "arxiv_id": paper.arxiv_id if paper else "",
                    "title": paper.title if paper else "",
                    "path": str(path),
                    "success": True,
                }

            except Exception as e:
                last_error = str(e)
                err_lower = last_error.lower()
                is_timeout = any(kw in err_lower for kw in
                    ("timeout", "timed out", "connection", "reset", "broken pipe"))
                if is_timeout and attempt < MAX_RETRIES:
                    wait = 15 * (attempt + 1)
                    print(f"# 图片生成超时/连接错误，{wait}s 后重试: {last_error[:100]}")
                    time.sleep(wait)
                    continue
                break

        # 生成可读的错误消息
        readable_error = last_error
        if "ModelNotOpen" in last_error:
            readable_error = "模型未开通，请在火山方舟控制台 (console.volcengine.com/ark) 开通 Seedream 图片生成服务"
        elif "Unauthorized" in last_error or "401" in last_error:
            readable_error = "API Key 无效，请检查海报模型的 API Key 配置"
        elif "insufficient" in last_error.lower() or "quota" in last_error.lower():
            readable_error = "API 配额不足，请检查火山方舟账户余额和配额"

        return {
            "arxiv_id": paper.arxiv_id if paper else "",
            "title": paper.title if paper else "",
            "success": False,
            "error": readable_error,
        }

    def _build_image_prompt(self, script: dict) -> str:
        """组装完整图片生成 prompt = 系统提示词 + 结构化内容"""
        findings = "\n".join(f"- {f}" for f in script.get("core_findings", []))
        visual = script.get("visual_description", "")
        title = script.get("poster_title", "Research Poster")
        subtitle = script.get("subtitle", "")
        hints = "\n".join(f"- {h}" for h in script.get("figure_hints", []))

        prompt = f"""{_get_poster_image_prompt()}

---

## Poster Content

Title: {title}
Subtitle: {subtitle}

Key Findings:
{findings}

Visual Content to Include:
{visual}

Figure Usage Hints:
{hints if hints else 'Use reference images as core visual elements'}

Requirements:
- Portrait layout, suitable for academic conference display
- Determine your own professional color palette and typography
- Data visualizations and diagrams integrated naturally
- High contrast for readability
- No cluttered text, focus on visual impact
"""
        return prompt.strip()

    # ── OpenAI 兼容接口 ──────────────────────────────

    def _call_openai(self, prompt: str, ref_images: list) -> bytes:
        """OpenAI / DALL-E / gpt-image-1"""
        api_key = self.cfg["api_key"]
        base_url = self.cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
        model = self.cfg.get("model", "dall-e-3")

        url = f"{base_url}/images/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # 论文参考图用文字描述（OpenAI 标准接口不支持图片参考）
        if ref_images:
            prompt += f"\n\nReference figures from the paper for content inspiration: {len(ref_images)} figure(s)."

        # 如果有风格模板，在 prompt 中要求遵循该风格
        if self.style_template_path:
            prompt += ("\n\nStyle requirement: Follow a clean, professional academic poster style "
                       "with modern layout, clear visual hierarchy, and balanced composition. "
                       "Use a cohesive color palette suitable for scientific conferences.")

        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1792",
            "response_format": "b64_json",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=IMAGE_GEN_TIMEOUT, context=SSL_CTX) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        b64_data = result["data"][0]["b64_json"]
        return base64.b64decode(b64_data)

    # ── 豆包 / 火山引擎 ──────────────────────────────

    def _call_doubao(self, prompt: str, ref_images: list) -> bytes:
        """豆包/火山引擎图像生成，支持参考图（风格模板优先）"""
        api_key = self.cfg["api_key"]
        base_url = self.cfg.get("base_url", "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
        model = self.cfg.get("model", "doubao-seedream-5-0-260128")

        url = f"{base_url}/images/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # 在 prompt 中描述论文参考图的内容
        if ref_images:
            prompt += f"\n\nPaper reference figures for content inspiration: {len(ref_images)} scientific figure(s) from the original paper. Incorporate their key data or concepts visually."

        # Seedream 5.0 要求最低 3,686,400 像素，竖版海报用 2048x3072
        payload = {
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": "2048x3072",
            "response_format": "url",
            "watermark": False,
        }

        # 优先使用风格模板图作为 image_url（影响整体风格）
        image_to_send = self.style_template_path or (ref_images[0] if ref_images else None)
        if image_to_send:
            with open(image_to_send, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            payload["image_url"] = f"data:image/png;base64,{b64}"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=IMAGE_GEN_TIMEOUT, context=SSL_CTX) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
            raise Exception(f"HTTP {e.code}: {err_body[:500]}")

        if "error" in result:
            raise Exception(f"API error: {result['error']}")

        img_url = result["data"][0]["url"]
        img_req = urllib.request.Request(img_url, headers={"User-Agent": "literature-brief/1.0"})
        with urllib.request.urlopen(img_req, timeout=IMAGE_DOWNLOAD_TIMEOUT, context=SSL_CTX) as resp:
            return resp.read()


# ============================================================
# 并发流水线编排器
# ============================================================

class PosterPipeline:
    """
    并发海报生成流水线。

    生产者（文本线程）：逐篇提炼论文 → 推入脚本队列
    消费者（图片线程）：从队列取脚本 → 生成图片 → 保存

    在图片模型生成 Paper N 时，文本模型同时处理 Paper N+1。
    """

    def __init__(self, topic: str):
        self.topic = topic
        self.refiner = PosterTextRefiner(topic)
        self.image_gen = PosterImageGenerator()

    def generate(self, papers: list[Paper], reader: PaperReader,
                 on_progress: Optional[Callable] = None) -> list[dict]:
        """
        并发处理所有论文，生成海报。
        返回 [{arxiv_id, title, path, success, error?}, ...]
        """
        if not papers:
            return []

        total = len(papers)

        # 脚本队列：maxsize=1 实现背压（文本只领先图片 1 篇）
        script_queue = queue.Queue(maxsize=1)
        results_lock = threading.Lock()
        results = []
        errors = []

        def producer():
            """文本线程：逐篇提炼论文脚本"""
            for i, paper in enumerate(papers):
                if on_progress:
                    on_progress(f"海报 [{i + 1}/{total}]：提炼脚本 — {paper.title[:30]}...")

                try:
                    script = self.refiner.refine(paper, reader)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    with results_lock:
                        errors.append({
                            "arxiv_id": paper.arxiv_id,
                            "title": paper.title,
                            "success": False,
                            "error": f"脚本提炼失败: {e}",
                        })
                    continue

                # 推入队列（若队列满则阻塞，等待图片线程消费）
                script_queue.put(script)

            # 发送结束信号
            script_queue.put(None)

        def consumer():
            """图片线程：从队列取脚本生成图片"""
            while True:
                script = script_queue.get()
                if script is None:
                    break

                paper = script.get("_paper")
                idx = len(results) + len(errors) + 1

                if on_progress:
                    title_snippet = paper.title[:30] if paper else "..."
                    on_progress(f"海报 [{idx}/{total}]：生成图片 — {title_snippet}...")

                result = self.image_gen.generate(script)

                with results_lock:
                    if result.get("success"):
                        results.append(result)
                        if on_progress:
                            on_progress(f"海报 [{idx}/{total}]：完成 — {result.get('title', '')[:30]}")
                    else:
                        errors.append(result)
                        if on_progress:
                            on_progress(f"海报 [{idx}/{total}]：失败 X — {result.get('error', '')[:50]}")

        # 启动双线程
        text_thread = threading.Thread(target=producer, daemon=True)
        image_thread = threading.Thread(target=consumer, daemon=True)

        text_thread.start()
        image_thread.start()

        # 等待完成
        text_thread.join()
        image_thread.join()

        # 合并结果（保持原始顺序）
        all_results = results + errors

        # 保存 session
        self._save_session(all_results)

        return all_results

    def generate_with_tools(self, papers: list[Paper], reader: PaperReader,
                            on_progress: Optional[Callable] = None) -> list[dict]:
        """
        使用 function calling 模式生成海报。
        文本大模型可主动调用 generate_poster_image 工具。
        """
        if not papers:
            return []

        total = len(papers)
        script_queue = queue.Queue(maxsize=1)
        results_lock = threading.Lock()
        results = []
        errors = []

        def producer():
            for i, paper in enumerate(papers):
                if on_progress:
                    on_progress(f"海报 [{i + 1}/{total}]：Agent 提炼脚本 — {paper.title[:30]}...")

                try:
                    script = self.refiner.refine_with_tools(paper, reader)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    with results_lock:
                        errors.append({
                            "arxiv_id": paper.arxiv_id,
                            "title": paper.title,
                            "success": False,
                            "error": f"脚本提炼失败: {e}",
                        })
                    continue

                script_queue.put(script)

            script_queue.put(None)

        def consumer():
            while True:
                script = script_queue.get()
                if script is None:
                    break

                paper = script.get("_paper")
                idx = len(results) + len(errors) + 1

                if on_progress:
                    title_snippet = paper.title[:30] if paper else "..."
                    on_progress(f"海报 [{idx}/{total}]：生成图片 — {title_snippet}...")

                result = self.image_gen.generate(script)

                with results_lock:
                    if result.get("success"):
                        results.append(result)
                    else:
                        errors.append(result)

        text_thread = threading.Thread(target=producer, daemon=True)
        image_thread = threading.Thread(target=consumer, daemon=True)

        text_thread.start()
        image_thread.start()
        text_thread.join()
        image_thread.join()

        all_results = results + errors
        self._save_session(all_results)
        return all_results

    # ── Session 记录 ─────────────────────────────────

    def _save_session(self, results: list):
        """保存本次生成记录，供 PosterGallery 读取"""
        output_dir = Path(cfg.get("poster_dir", os.path.join(
            os.environ.get("USERPROFILE", os.path.expanduser("~")),
            "literature_brief", "posters"
        )))
        output_dir.mkdir(parents=True, exist_ok=True)

        session = {
            "topic": self.topic,
            "date": datetime.now().isoformat(),
            "results": results,
        }
        fname = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_dir / fname, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)


# ============================================================
# 兼容旧 API 的包装类
# ============================================================

class PosterGenerator:
    """
    兼容旧 API 的包装类。
    内部使用 PosterPipeline 实现并发流水线。
    """

    def __init__(self, topic: str):
        self.pipeline = PosterPipeline(topic)

    def generate(self, papers: list[Paper], reader: PaperReader,
                 on_progress: Optional[Callable] = None) -> list[dict]:
        return self.pipeline.generate(papers, reader, on_progress)


# ============================================================
# 快速测试
# ============================================================
if __name__ == "__main__":
    print("PosterPipeline 模块加载完成")
    print(f"海报输出目录: {cfg.get('poster_dir', '默认')}")
    print(f"文本模型系统提示词: {_get_poster_text_prompt()[:80]}...")
    print(f"图片模型系统提示词: {_get_poster_image_prompt()[:80]}...")
    print(f"文本模型可用工具: {len(POSTER_IMAGE_TOOLS)} 个")
