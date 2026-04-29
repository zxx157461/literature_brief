"""
papers.py - 论文数据模型
S1 - 数据结构定义
"""
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Paper:
    """
    论文数据结构
    包含界面展示所需的所有字段
    """
    # arxiv 元数据
    arxiv_id: str          # arXiv ID，如 "2401.12345"
    title: str             # 标题
    authors: list[str]     # 作者列表
    abstract: str           # 摘要
    categories: list[str]  # 分类标签
    submitted_date: str     # 提交日期
    updated_date: str      # 更新日期
    pdf_url: str           # PDF 下载地址

    # AI 评分相关（由 scorer.py 填充）
    relevance_score: float = 0.0    # 相关性分数 0~1
    score_reason: str = ""          # 评分理由
    key_findings: list[str] = field(default_factory=list)  # 关键发现

    # 用户交互相关（由 UI 填充）
    selected: bool = False   # 用户是否选中
    manual_override: bool = False  # 是否手动调整过分数
    notes: str = ""          # 用户备注

    # 下载/解读状态
    pdf_path: Optional[str] = None   # 本地 PDF 路径
    extracted_text: Optional[str] = None  # 提取的文字
    ai_summary: Optional[str] = None  # AI 生成的摘要
    processing_status: str = "pending"  # pending / downloading / extracting / summarizing / done / error

    @property
    def short_id(self) -> str:
        """缩短的 arxiv ID 用于显示"""
        # 2401.12345 -> 2401.12345
        return self.arxiv_id

    @property
    def display_authors(self) -> str:
        """格式化作者列表用于显示"""
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        else:
            return f"{self.authors[0]} et al."

    @property
    def score_stars(self) -> str:
        """分数转星号显示"""
        stars = int(self.relevance_score * 5)
        return "★" * stars + "☆" * (5 - stars)

    @property
    def short_abstract(self) -> str:
        """截断的摘要用于显示"""
        if len(self.abstract) > 200:
            return self.abstract[:200] + "..."
        return self.abstract

    def to_summary_dict(self) -> dict:
        """转换为摘要字典，用于发送给 AI 或导出"""
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.display_authors,
            "submitted_date": self.submitted_date,
            "categories": ", ".join(self.categories),
            "relevance_score": f"{self.relevance_score:.2f}",
            "score_reason": self.score_reason,
            "key_findings": "; ".join(self.key_findings),
            "abstract": self.abstract,
        }


@dataclass
class SearchResult:
    """
    一次搜索的结果集合
    """
    query: str
    total_found: int
    papers: list[Paper]
    search_time: datetime = field(default_factory=datetime.now)
    mode: str = "auto"  # auto / manual
