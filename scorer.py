"""
scorer.py - AI 评分模块
S8 - 给论文打相关性分数

调用 sift LLM（从 config 读取），逐篇分析摘要，返回分数 + 理由 + 关键发现。
支持 OpenAI / MiniMax / 自定义 API。
"""
import json
import urllib.request
import urllib.parse
from typing import Optional, Callable
from papers import Paper
from config import cfg, SSL_CTX


# ============================================================
# LLM 调用层
# ============================================================

class LLMCallError(Exception):
    """LLM 调用失败"""


class LLMCaller:
    """通用 LLM API 调用器（OpenAI 兼容格式）"""

    def __init__(self, llm_cfg: dict):
        self.cfg = llm_cfg
        self.base_url = llm_cfg["base_url"].rstrip("/")
        self.model = llm_cfg["model"]
        self.api_key = llm_cfg["api_key"]
        self.max_tokens = llm_cfg.get("max_tokens", 2000)
        self.temperature = llm_cfg.get("temperature", 0.3)
        self.timeout = 60

    def _do_request(self, payload: dict) -> dict:
        """发 HTTP 请求到 LLM API"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=SSL_CTX) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise LLMCallError(f"HTTP {e.code}: {body[:200]}")
        except Exception as e:
            raise LLMCallError(str(e))

    def chat(self, messages: list[dict], **kwargs) -> str:
        """
        发送对话，返回 assistant 的文字回复
        messages: [{"role": "user"/"assistant"/"system", "content": "..."}]
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            **kwargs,
        }
        # MiniMax 不支持 temperature=0
        if self.cfg.get("provider") == "minimax" and payload["temperature"] == 0:
            payload["temperature"] = 0.01

        result = self._do_request(payload)

        if "error" in result:
            raise LLMCallError(f"API error: {result['error']}")

        return result["choices"][0]["message"]["content"]


# ============================================================
# 评分器
# ============================================================

# 评分 Prompt（注入：论文标题、摘要、作者、搜索主题）
SCORE_PROMPT = """你是一位活跃在 {topic} 领域的研究助理。请评估以下论文与该研究主题的相关性。
{sift_requirement_section}
论文信息：
标题：{title}
作者：{authors}
摘要：{abstract}

请以 JSON 格式返回评估结果，不要包含任何其他内容：
{{
  "score": 0.0~1.0 的浮点数，表示论文与研究主题的相关程度，
  "reason": 一句话说明评分理由，
  "key_findings": ["发现1", "发现2"]，最多3个与主题最相关的关键发现
}}
评分标准：
- score >= 0.8：该论文核心内容与主题高度相关，值得深入阅读
- score 0.5~0.8：论文涉及主题的某个方面，可以参考
- score 0.2~0.5：主题相关但非核心，仅供泛读
- score < 0.2：与主题基本无关，可忽略

只返回 JSON，不要有其他文字。"""


class PaperScorer:
    """论文评分器"""

    def __init__(self, topic: str, sift_requirement: str = ""):
        self.topic = topic
        self.sift_requirement = sift_requirement.strip()
        sift_cfg = cfg.get("sift") or {}
        fallback = {
            "provider": cfg.get("llm_provider", "openai"),
            "api_key": cfg.get("api_key", ""),
            "base_url": cfg.get("base_url", "https://api.openai.com/v1"),
            "model": cfg.get("model", "gpt-4o-mini"),
            "max_tokens": cfg.get("max_tokens", 2000),
            "temperature": cfg.get("temperature", 0.3),
        }
        llm_cfg = sift_cfg if sift_cfg else fallback
        if not llm_cfg.get("api_key"):
            raise LLMCallError(
                "筛选模型未配置 API Key，请在设置 > 其他AI筛选 > 筛选模型中配置"
            )
        self.llm = LLMCaller(llm_cfg)

    def score_one(self, paper: Paper) -> dict:
        """对单篇论文评分，返回 {"score", "reason", "key_findings"}"""
        authors_str = ", ".join(paper.authors[:5])
        if len(paper.authors) > 5:
            authors_str += " et al."

        req_section = (
            f"\n额外筛选要求：{self.sift_requirement}\n请在评分时严格参考上述筛选要求。\n"
            if self.sift_requirement else ""
        )

        prompt = SCORE_PROMPT.format(
            topic=self.topic,
            sift_requirement_section=req_section,
            title=paper.title,
            authors=authors_str,
            abstract=paper.abstract[:1500],
        )

        messages = [
            {"role": "system", "content": "你是一个严谨的学术论文评审助手，始终以 JSON 格式回答。"},
            {"role": "user", "content": prompt},
        ]

        try:
            text = self.llm.chat(messages)
        except LLMCallError as e:
            print(f"# LLM 调用失败 [{paper.arxiv_id}]: {e}")
            return {"score": 0.0, "reason": f"评分失败: {e}", "key_findings": []}

        return self._parse(text, paper.arxiv_id)

    def score_batch(self, papers: list[Paper], on_progress: Optional[Callable] = None) -> list[Paper]:
        """
        批量评分，进度回调 on_progress(current, total)
        直接修改传入的 Paper 对象
        """
        total = len(papers)
        for i, paper in enumerate(papers):
            result = self.score_one(paper)
            paper.relevance_score = float(result["score"])
            paper.score_reason = result["reason"]
            paper.key_findings = result.get("key_findings", [])

            if on_progress:
                on_progress(i + 1, total)

        return papers

    def _parse(self, text: str, arxiv_id: str) -> dict:
        """从 LLM 回复中提取 JSON"""
        # 尝试直接解析
        text = text.strip()
        # 去掉可能的 markdown 代码块
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:] if lines[0] == "```" else lines)
            text = text.rstrip("`").strip()

        try:
            data = json.loads(text)
            # 验证必要字段
            if "score" not in data or "reason" not in data:
                raise ValueError("缺少 score 或 reason 字段")
            data["score"] = max(0.0, min(1.0, float(data["score"])))
            data["key_findings"] = data.get("key_findings", [])
            return data
        except Exception as e:
            print(f"# JSON 解析失败 [{arxiv_id}]: {e}")
            print(f"#  原始回复: {text[:200]}")
            return {"score": 0.0, "reason": f"解析失败: {text[:100]}", "key_findings": []}


# ============================================================
# 快速测试
# ============================================================
if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from searcher import ArxivSearcher, SearchParams

    sr = ArxivSearcher()
    params = SearchParams(keywords="active matter", max_results=3, sort_by="relevance")
    result = sr.search(params)

    scorer = PaperScorer(topic="active matter in soft condensed matter physics")
    scored = scorer.score_batch(result.papers, on_progress=lambda cur, tot: print(f"\r评分中... {cur}/{tot}", end="", flush=True))

    print("\n\n=== 评分结果 ===")
    for p in scored:
        print(f"[{p.short_id}] score={p.relevance_score:.2f}  {p.score_reason}")
        if p.key_findings:
            print(f"  关键发现: {'; '.join(p.key_findings)}")
        print()
