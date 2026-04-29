"""
searcher.py - arXiv 搜索模块
S7 - 搜索论文
"""
import calendar
import re
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from papers import Paper, SearchResult
from config import SSL_CTX


# arXiv API 基础地址
ARXIV_API = "https://export.arxiv.org/api/query"


def _q(s: str) -> str:
    """对单个词做 URL 编码，空格转 %20"""
    return urllib.parse.quote(str(s), safe="")


def _parse_date_input(raw: str, is_end: bool = False) -> str:
    """把用户输入解析成 YYYY-MM-DD，支持 2024 / 2024-03 / 2024-03-15"""
    raw = raw.strip()
    if not raw:
        return None
    # 完整日期 2024-03-15
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", raw)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    # 年月 2024-03
    m = re.match(r"^(\d{4})-(\d{1,2})$", raw)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if is_end:
            last_day = calendar.monthrange(year, month)[1]
            return f"{year:04d}-{month:02d}-{last_day:02d}"
        return f"{year:04d}-{month:02d}-01"
    # 纯年份 2024
    if raw.isdigit() and len(raw) == 4:
        if is_end:
            return f"{raw}-12-31"
        return f"{raw}-01-01"
    return None


class SearchParams:
    """搜索参数"""
    def __init__(
        self,
        keywords: str = "",
        author: str = "",
        categories: list[str] = None,
        year_from: int = None,
        year_to: int = None,
        date_from: str = None,   # YYYY-MM-DD
        date_to: str = None,     # YYYY-MM-DD
        max_results: int = 20,
        sort_by: str = "relevance",     # relevance / lastUpdatedDate / submittedDate
        sort_order: str = "descending",  # descending / ascending
    ):
        self.keywords = keywords
        self.author = author
        self.categories = categories or []
        # 兼容旧版 year 参数
        self.date_from = date_from or (_parse_date_input(str(year_from)) if year_from else None)
        self.date_to = date_to or (_parse_date_input(str(year_to), is_end=True) if year_to else None)
        self.max_results = max_results
        self.sort_by = sort_by
        self.sort_order = sort_order


class ArxivSearcher:
    """arXiv 搜索器"""

    def search(self, params: SearchParams) -> SearchResult:
        """
        执行搜索，返回 SearchResult
        """
        query_parts = []

        # 关键词
        if params.keywords:
            kw_list = [kw.strip() for kw in params.keywords.split() if kw.strip()]
            if len(kw_list) == 1:
                query_parts.append(f"all:{_q(kw_list[0])}")
            else:
                # 多词：all:"active+matter"（arXiv 接受的短语格式）
                phrase = "+".join(_q(kw) for kw in kw_list)
                query_parts.append(f'all:%22{phrase}%22')

        # 作者
        if params.author:
            query_parts.append(f"au:{_q(params.author.strip())}")

        # 分类
        for cat in params.categories:
            cat = cat.strip()
            if cat:
                query_parts.append(f"cat:{_q(cat)}")

        # 日期范围（精确到天）
        if params.date_from or params.date_to:
            df = params.date_from or "1991-01-01"
            dt = params.date_to or datetime.now().strftime("%Y-%m-%d")
            query_parts.append(f"submittedDate:[{_q(df)}+TO+{_q(dt)}]")

        if not query_parts:
            raise ValueError("至少需要一个搜索条件（关键词/作者/分类/日期）")

        query = " AND ".join(query_parts)
        # 手动对 query string 做 URL 编码，保持 + 和 : 不动
        # 只编码其他特殊字符（空格、引号等）
        encoded_query = urllib.parse.quote(query, safe=":+-%_")

        url = (
            f"{ARXIV_API}"
            f"?search_query={encoded_query}"
            f"&start=0"
            f"&max_results={params.max_results}"
            f"&sortBy={params.sort_by}"
            f"&sortOrder={params.sort_order}"
        )

        papers = self._fetch(url)

        return SearchResult(
            query=params.keywords or params.author or ",".join(params.categories),
            total_found=len(papers),
            papers=papers,
            mode="auto",
        )

    def _fetch(self, url: str) -> list[Paper]:
        """从 arXiv API 获取并解析论文"""
        req = urllib.request.Request(url, headers={"User-Agent": "literature-brief/1.0"})
        with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
            xml_data = resp.read().decode("utf-8")
        return self._parse(xml_data)

    def _parse(self, xml_data: str) -> list[Paper]:
        """解析 arXiv Atom XML，返回 Paper 列表"""
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        root = ET.fromstring(xml_data)

        papers = []
        for entry in root.findall("atom:entry", ns):
            try:
                arxiv_id = entry.find("atom:id", ns).text.split("/")[-1]

                title = entry.find("atom:title", ns).text or ""
                title = " ".join(title.split())

                authors = [
                    a.find("atom:name", ns).text or ""
                    for a in entry.findall("atom:author", ns)
                    if a.find("atom:name", ns) is not None
                ]

                abstract = entry.find("atom:summary", ns).text or ""
                abstract = " ".join(abstract.split())

                categories = [c.get("term", "") for c in entry.findall("atom:category", ns)]

                submitted = self._get_text(entry, "atom:published", ns)
                updated = self._get_text(entry, "atom:updated", ns)

                # PDF 链接
                pdf_url = ""
                for link in entry.findall("atom:link", ns):
                    if link.get("title") == "pdf":
                        pdf_url = link.get("href", "")
                        break
                if not pdf_url:
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                papers.append(Paper(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    categories=categories,
                    submitted_date=submitted[:10] if submitted else "",
                    updated_date=updated[:10] if updated else "",
                    pdf_url=pdf_url,
                ))
            except Exception as e:
                print(f"# Warning: 跳过一条论文（解析失败）: {e}")
                continue

        return papers

    def _get_text(self, elem, tag: str, ns: dict) -> str:
        child = elem.find(tag, ns)
        return child.text.strip() if child is not None and child.text else ""


# ========== 快速测试 ==========
if __name__ == "__main__":
    sr = ArxivSearcher()

    print("=== 测试1：关键词搜索 ===")
    params = SearchParams(keywords="active matter", max_results=5, sort_by="relevance")
    result = sr.search(params)
    print(f"找到 {result.total_found} 篇\n")
    for p in result.papers:
        print(f"[{p.short_id}] {p.title[:70]}")
        print(f"  作者: {p.display_authors}")
        print(f"  分类: {', '.join(p.categories[:3])}")
        print(f"  摘要: {p.short_abstract[:80]}...")
        print()

    print("=== 测试2：作者+分类 ===")
    params2 = SearchParams(author="Marchetti", categories=["cond-mat.soft"], max_results=3)
    result2 = sr.search(params2)
    print(f"找到 {result2.total_found} 篇\n")
    for p in result2.papers:
        print(f"[{p.short_id}] {p.title[:70]}")
        print(f"  日期: {p.submitted_date}")
        print()
