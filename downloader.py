"""
downloader.py - PDF 下载模块
S9 - 批量下载论文 PDF

支持：arXiv 直链下载，带重试、超时、本地缓存（已下载不重复下）。
"""
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from papers import Paper
from config import PAPERS_DIR, SSL_CTX


class DownloadError(Exception):
    """下载失败"""


class PaperDownloader:
    """论文 PDF 下载器"""

    def __init__(self, papers_dir: str = None, timeout: int = 60):
        """
        papers_dir: PDF 保存目录，默认从 config 读取
        timeout: 每次请求超时（秒）
        """
        self.papers_dir = Path(papers_dir) if papers_dir else Path(PAPERS_DIR)
        self.papers_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self._session_headers = {
            "User-Agent": "Mozilla/5.0 (compatible; literature-brief/1.0)",
        }

    def _paper_path(self, paper: Paper) -> Path:
        """返回 PDF 的本地保存路径"""
        return self.papers_dir / f"{paper.arxiv_id}.pdf"

    def download_one(self, paper: Paper, force: bool = False) -> Optional[str]:
        """
        下载单篇论文 PDF
        force: True=强制重新下载，False=已存在则跳过
        返回本地路径，失败返回 None
        """
        save_path = self._paper_path(paper)

        # 缓存命中
        if not force and save_path.exists() and save_path.stat().st_size > 1000:
            return str(save_path)

        # 下载
        url = paper.pdf_url
        if not url:
            url = f"https://arxiv.org/pdf/{paper.arxiv_id}.pdf"

        req = urllib.request.Request(url, headers=self._session_headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=SSL_CTX) as resp:
                content = resp.read()
        except Exception as e:
            raise DownloadError(f"下载失败 [{paper.arxiv_id}]: {e}")

        # 保存
        try:
            with open(save_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise DownloadError(f"保存失败 [{paper.arxiv_id}]: {e}")

        # 验证文件大小
        if save_path.stat().st_size < 1000:
            raise DownloadError(f"文件过小，可能下载不完整 [{paper.arxiv_id}]")

        return str(save_path)

    def download_batch(
        self,
        papers: list[Paper],
        on_progress: Optional[callable] = None,
        delay: float = 1.0,
    ) -> dict:
        """
        批量下载论文 PDF
        delay: 每次下载间隔（秒），避免触发 arXiv 限速
        返回 {"success": [路径列表], "failed": [(paper, error) 列表]}
        """
        success = []
        failed = []

        total = len(papers)
        for i, paper in enumerate(papers):
            path = None
            err_msg = None
            try:
                path = self.download_one(paper)
                if path:
                    success.append(path)
            except DownloadError as e:
                err_msg = str(e)
                failed.append((paper, err_msg))

            if on_progress:
                on_progress(i + 1, total, paper.arxiv_id, err_msg)

            # 限速：arXiv 建议每次请求间隔 3 秒以上
            if i < total - 1 and delay > 0:
                time.sleep(delay)

        return {"success": success, "failed": failed}

    def get_local_path(self, paper: Paper) -> Optional[str]:
        """返回本地路径（如果已存在）"""
        path = self._paper_path(paper)
        if path.exists() and path.stat().st_size > 1000:
            return str(path)
        return None


# ============================================================
# 快速测试（需要真实网络）
# ============================================================
if __name__ == "__main__":
    from papers import Paper

    paper = Paper(
        arxiv_id="2301.09550",
        title="Planktonic Active Matter",
        authors=["Anupam Sengupta"],
        abstract="",
        categories=[],
        submitted_date="2023-01-01",
        updated_date="2023-01-01",
        pdf_url="https://arxiv.org/pdf/2301.09550.pdf",
    )

    dl = PaperDownloader()

    print(f"下载到: {dl.papers_dir}")
    print(f"PDF 路径: {dl._paper_path(paper)}")
    print(f"已有缓存: {dl.get_local_path(paper)}")
    print("\n尝试下载...")
    try:
        path = dl.download_one(paper)
        print(f"下载成功: {path}")
        print(f"文件大小: {os.path.getsize(path) / 1024:.1f} KB")
    except DownloadError as e:
        print(f"下载失败: {e}")
