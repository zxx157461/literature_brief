"""
reader.py - PDF 文字与图片提取模块
S10 - 从 PDF 中提取文字和图片

支持：
- 全文提取（所有页，不只是前10页）
- 提取所有图片并保存到磁盘
- 识别哪些页面包含图片（用于 AI 筛选）
"""
import re
import json
import base64
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from papers import Paper
from config import PAPERS_DIR


# 尝试导入 PDF 库
_pdf_lib = None
try:
    import pdfplumber
    _pdf_lib = "pdfplumber"
except ImportError:
    try:
        import PyPDF2
        _pdf_lib = "PyPDF2"
    except ImportError:
        pass


@dataclass
class FigureInfo:
    """提取出的图片元信息"""
    figure_id: str       # 如 "p2_fig3"
    page_num: int        # 页码（从1开始）
    caption: str         # 图注（如果能识别到）
    image_path: str      # 保存路径
    width: int
    height: int
    size_kb: float


class ReadError(Exception):
    pass


class PaperReader:
    """论文 PDF 处理器"""

    def __init__(self, papers_dir: str = None, figures_dir: str = None):
        self.papers_dir = Path(papers_dir) if papers_dir else Path(PAPERS_DIR)
        self.figures_dir = Path(figures_dir) if figures_dir else (self.papers_dir.parent / "figures")
        self.figures_dir.mkdir(parents=True, exist_ok=True)

        if _pdf_lib is None:
            raise ImportError(
                "未安装 PDF 库。请运行:\n"
                "  pip install pdfplumber\n"
                "或\n"
                "  pip install pdfplumber -i https://pypi.tuna.tsinghua.edu.cn/simple"
            )

    # ── 文字提取 ──────────────────────────────────────

    def read_full_text(self, paper: Paper, pdf_path: str = None) -> str:
        """提取完整正文（所有页），返回纯文本"""
        if pdf_path:
            path = Path(pdf_path)
        else:
            path = self.papers_dir / f"{paper.arxiv_id}.pdf"

        if not path.exists():
            raise ReadError(f"PDF 不存在: {path}")

        try:
            if _pdf_lib == "pdfplumber":
                return self._read_plumber_full(path)
            elif _pdf_lib == "PyPDF2":
                return self._read_pypdf2(path)
        except Exception as e:
            raise ReadError(f"提取失败 [{paper.arxiv_id}]: {e}")

        return ""

    def _read_plumber_full(self, path: Path) -> str:
        """用 pdfplumber 提取全部文字"""
        import pdfplumber

        texts = []
        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                # 清洗
                page_text = self._clean_text(page_text)
                if page_text.strip():
                    texts.append(f"[第{page_num}页]\n{page_text}")

        return "\n\n".join(texts)

    def _read_pypdf2(self, path: Path) -> str:
        """用 PyPDF2 提取"""
        import PyPDF2

        texts = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page_num, page in enumerate(reader.pages, 1):
                text = page.extract_text() or ""
                text = self._clean_text(text)
                if text.strip():
                    texts.append(f"[第{page_num}页]\n{text}")

        return "\n\n".join(texts)

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"\S+@\S+\.\S+", "", text)
        return text.strip()

    # ── 图片提取 ──────────────────────────────────────

    def extract_all_figures(
        self,
        paper: Paper,
        pdf_path: str = None,
        min_size_kb: float = 10.0,
    ) -> list[FigureInfo]:
        """
        从 PDF 提取所有图片，返回元信息列表
        只保留尺寸大于 min_size_kb 的图（过滤掉小图标/水印）
        """
        if pdf_path:
            path = Path(pdf_path)
        else:
            path = self.papers_dir / f"{paper.arxiv_id}.pdf"

        if not path.exists():
            raise ReadError(f"PDF 不存在: {path}")

        figures = []
        figure_count = 0

        try:
            if _pdf_lib == "pdfplumber":
                figures = self._extract_figures_plumber(
                    path, paper.arxiv_id, min_size_kb
                )
        except Exception as e:
            print(f"# Warning: 图片提取失败 [{paper.arxiv_id}]: {e}")

        return figures

    def _extract_figures_plumber(
        self, path: Path, arxiv_id: str, min_size_kb: float
    ) -> list[FigureInfo]:
        """用 pdfplumber 提取图片"""
        import pdfplumber
        from PIL import Image
        import io

        figures = []
        figure_count = 0

        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                images = page.images
                if not images:
                    continue

                for img_info in images:
                    try:
                        # 从页面还原图片
                        x0 = int(img_info["x0"])
                        y0 = int(img_info["top"])
                        x1 = int(img_info["x1"])
                        y1 = int(img_info["bottom"])

                        width = x1 - x0
                        height = y1 - y0

                        if width < 100 or height < 100:
                            continue  # 太小的图跳过（水印等）

                        # 裁剪出这张图，使用高分辨率渲染（300 DPI）
                        pil_img = page.crop(
                            (x0, y0, x1, y1), strict=False
                        ).to_image(resolution=300)
                        img_bytes = pil_img.original.convert("RGB")

                        # 保存为 PNG（无损，避免 JPEG 压缩损失细节）
                        buf = io.BytesIO()
                        img_bytes.save(buf, format="PNG")
                        img_bytes_png = buf.getvalue()
                        size_kb = len(img_bytes_png) / 1024

                        if size_kb < min_size_kb:
                            continue  # 太小的跳过

                        figure_count += 1
                        filename = f"{arxiv_id}_p{page_num}_fig{figure_count}.png"
                        save_path = self.figures_dir / filename
                        with open(save_path, "wb") as f:
                            f.write(img_bytes_png)

                        # 尝试从周围文字提取图注
                        caption = self._extract_caption_around(
                            page.extract_text() or "", x0, y0, page.width, page.height
                        )

                        figures.append(FigureInfo(
                            figure_id=f"{arxiv_id}_p{page_num}_fig{figure_count}",
                            page_num=page_num,
                            caption=caption,
                            image_path=str(save_path),
                            width=width,
                            height=height,
                            size_kb=size_kb,
                        ))

                    except Exception as e:
                        print(f"# Warning: 第{page_num}页图片提取失败: {e}")
                        continue

        return figures

    def _extract_caption_around(
        self, page_text: str, img_x: int, img_y: int,
        page_width: float, page_height: float
    ) -> str:
        """
        简单heuristic：尝试从页面文字中找出图注
        如果图片在页面下方，图注通常在图片上方紧邻的文字中
        这里简化处理，返回空字符串，后续让 AI 根据图号自己判断
        """
        # 简化：直接返回空，让 AI 自己判断
        return ""

    # ── AI 辅助 ──────────────────────────────────────

    def build_figure_selection_prompt(
        self, paper: Paper, figures: list[FigureInfo], max_select: int = 4
    ) -> str:
        """
        生成让 AI 筛选重点图的提示词
        figures 里包含图片路径，AI 可以根据路径读取
        """
        figure_list = []
        for i, fig in enumerate(figures, 1):
            figure_list.append(
                f"图{i}: {fig.figure_id} (第{fig.page_num}页, "
                f"{fig.width}×{fig.height}px, {fig.size_kb:.0f}KB)"
            )

        prompt = f"""论文：{paper.title}
作者：{paper.display_authors}
arXiv: {paper.arxiv_id}

这篇论文中共有 {len(figures)} 张图片。以下是图片列表：
{chr(10).join(figure_list)}

请从中选出最多 {max_select} 张最能体现论文核心发现的图，用 JSON 格式返回：

{{
  "selected": [
    {{"figure_id": "arxiv_p1_fig1", "reason": "选这张的理由"}},
    ...
  ],
  "reasoning": "总体筛选思路"
}}

选图标准：
1. 能反映核心物理结论的图（如相图、统计曲线）
2. 实验/模拟的关键结果图
3. 图注信息丰富的图
4. 排除纯示意图、流程图、作者头像等
"""
        return prompt

    def image_to_base64(self, image_path: str) -> str:
        """图片转 base64（用于 API 传输）"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")


# ============================================================
# 快速测试
# ============================================================
if __name__ == "__main__":
    print(f"PDF 库: {_pdf_lib or 'none'}")
    if _pdf_lib is None:
        print("\n警告: 未安装 PDF 库，请先 pip install pdfplumber")

    from pathlib import Path
    papers_dir = Path(PAPERS_DIR)
    figures_dir = papers_dir.parent / "figures"
    print(f"PDF 目录: {papers_dir}")
    print(f"图片目录: {figures_dir}")
