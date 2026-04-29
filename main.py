"""
main.py - 程序入口
串联 UI + 各筛选模式 + agent
"""
import threading
import os

from ui import MainWindow, ReviewWindow, SettingsWindow, ReportsWindow, PosterGalleryWindow
from searcher import ArxivSearcher, SearchParams
from agent import BriefingAgent, OpenclawFilter
from scorer import PaperScorer
from config import cfg, REPORTS_DIR
from pi_client import PiClient
from reporter import PaperReporter
from reader import PaperReader


class App:
    def __init__(self):
        self.main_win = MainWindow()
        self.main_win.geometry("960x620+50+50")
        self.main_win.on_search_clicked = self._on_search
        self.main_win.on_send_to_ai = self._on_send_to_ai
        self.main_win.on_open_review = self._on_open_review
        self.main_win.on_open_settings = self._on_open_settings
        self.main_win.on_upload_to_pi = self._on_upload_to_pi
        self.main_win.on_download_from_pi = self._on_download_from_pi
        self.main_win.on_open_reports = self._on_open_reports
        self.main_win.on_open_poster_gallery = self._on_open_poster_gallery

        self.review_win = None
        self.reports_win = None
        self._last_sift_requirement = ""
        self.main_win.mainloop()

    def _set_status(self, target, msg: str):
        """线程安全地更新状态栏"""
        self.main_win.after(0, lambda: target.set_status(msg))

    # ── 搜索 ──────────────────────────────────────

    def _on_search(self, **kwargs):
        self._last_sift_requirement = kwargs.get("sift_requirement", "")
        mode = cfg.get("screen_mode", "人工筛选")

        self.main_win.set_searching(True)

        def run():
            try:
                if mode == "其他AI筛选":
                    self.main_win.after(0, lambda: self.main_win.set_status("AI 正在分析搜索意图..."))
                    from agent import AIResearcher
                    researcher = AIResearcher(
                        topic=kwargs.get("keyword", ""),
                        sift_requirement=self._last_sift_requirement,
                    )
                    result = researcher.search(
                        max_results=kwargs.get("max_results", 20),
                        sort_by=kwargs.get("sort_by", "relevance"),
                        on_progress=lambda msg: self.main_win.after(0, lambda: self.main_win.set_status(msg)),
                    )
                    papers = result.papers
                    status_msg = f"AI 搜索完成：找到 {len(papers)} 篇相关论文"
                else:
                    self.main_win.after(0, lambda: self.main_win.set_status("正在搜索 arXiv..."))
                    sr = ArxivSearcher()
                    params = SearchParams(
                        keywords=kwargs.get("keyword", ""),
                        author=kwargs.get("author") or "",
                        categories=kwargs.get("categories") or [],
                        date_from=kwargs.get("date_from") or None,
                        date_to=kwargs.get("date_to") or None,
                        max_results=kwargs.get("max_results", 20),
                        sort_by=kwargs.get("sort_by", "relevance"),
                    )
                    result = sr.search(params)
                    papers = result.papers
                    status_msg = f"找到 {len(papers)} 篇论文"

                self.main_win.after(0, lambda: self.main_win.set_status(status_msg, progress=1.0))
                self.main_win.after(0, lambda: self.main_win.show_results(papers))
                self.main_win.after(0, lambda: self.main_win.set_searching(False))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.main_win.after(0, lambda: self.main_win.set_status(f"搜索失败: {e}", progress=0))
                self.main_win.after(0, lambda: self.main_win.show_results([]))
                self.main_win.after(0, lambda: self.main_win.set_searching(False))

        threading.Thread(target=run, daemon=True).start()

    # ── 发送给 AI 助手（模式路由）─────────────────

    def _on_send_to_ai(self):
        selected = self.main_win.get_selected_papers()
        if not selected:
            return

        topic = self.main_win.keyword_entry.get().strip()
        mode = cfg.get("screen_mode", "纯手动（无需LLM）")
        review_needed = cfg.get("brief_review_needed", False)
        sift_requirement = self.main_win.sift_requirement_entry.get().strip()

        # 路由分发
        if mode == "人工筛选":
            self._generate_briefing(selected, topic, from_ui=True)

        elif mode == "openclaw筛选":
            self._openclaw_filter_and_continue(selected, topic, review_needed, from_ui=True)

        elif mode == "其他AI筛选":
            self._ai_filter_and_continue(selected, topic, sift_requirement, review_needed, from_ui=True)

    # ── 进入审核 ──────────────────────────────────

    def _on_open_review(self):
        selected = self.main_win.get_selected_papers()
        if not selected:
            return
        self._open_review_win(selected)

    def _auto_select_and_review(self, papers: list):
        """搜索完成后自动全选并打开审核窗口"""
        self.main_win.select_all_papers()
        self._open_review_win(papers)

    def _open_review_win(self, papers: list):
        if self.review_win and self.review_win.winfo_exists():
            self.review_win.lift()
            return
        self.review_win = ReviewWindow(self.main_win, papers)
        self.review_win.geometry("1000x750+200+30")
        self.review_win.on_confirm_text = self._on_review_confirm_text
        self.review_win.on_confirm_image = self._on_review_confirm_image

    def _on_review_confirm_text(self, selected: list):
        """审核框：生成文本简报"""
        if not selected:
            return
        topic = self.main_win.keyword_entry.get().strip()
        self._generate_briefing(selected, topic, from_ui=False)

    def _on_review_confirm_image(self, selected: list):
        """审核框：生成图片简报（海报）"""
        if not selected:
            return
        topic = self.main_win.keyword_entry.get().strip()
        self._generate_posters_from_review(selected, topic)

    # ── openclaw筛选 ──────────────────────────────

    def _openclaw_filter_and_continue(self, papers: list, topic: str, review_needed: bool, from_ui: bool):
        """openclaw 用 brief LLM + score_papers 工具筛选"""

        def run():
            status_target = self.main_win if from_ui else (self.review_win or self.main_win)
            self._set_status(status_target, "openclaw 正在筛选论文...")

            try:
                oc = OpenclawFilter(topic=topic, sift_requirement=self._last_sift_requirement)
                filtered = oc.filter(papers, on_progress=lambda msg: self._set_status(status_target, msg))
            except Exception as e:
                self._set_status(status_target, f"openclaw 调用失败，使用简单筛选: {e}")
                filtered = [p for p in papers if p.relevance_score >= 0.5]

            if not filtered:
                self._set_status(status_target, "没有通过筛选的论文，请调整条件后重试。")
                return

            self._set_status(status_target, f"openclaw 筛选完成：{len(filtered)}/{len(papers)} 篇通过。")

            if review_needed:
                self.main_win.after(100, lambda: self._open_review_win_and_replace(filtered))
            else:
                self._generate_briefing(filtered, topic, from_ui=False)

        threading.Thread(target=run, daemon=True).start()

    def _open_review_win_and_replace(self, papers: list):
        """用筛选后的论文替换审核框内容"""
        if self.review_win and self.review_win.winfo_exists():
            self.review_win.destroy()
        self._open_review_win(papers)

    # ── 其他AI筛选 ────────────────────────────────

    def _ai_filter_and_continue(self, papers: list, topic: str, sift_requirement: str, review_needed: bool, from_ui: bool):
        """AI 评分 + 阈值筛选"""

        def run():
            status_target = self.main_win if from_ui else (self.review_win or self.main_win)
            self._set_status(status_target, "AI 正在评分筛选论文...")

            try:
                scorer = PaperScorer(topic=topic, sift_requirement=sift_requirement)
                threshold = cfg.get("auto_score_threshold", 0.6)
                scored = scorer.score_batch(papers, on_progress=lambda cur, tot: self._set_status(status_target, f"AI 评分中... {cur}/{tot}"))

                # 调试输出：打印每篇论文的评分结果到控制台
                for p in scored:
                    print(f"  [{p.arxiv_id}] score={p.relevance_score:.2f} | {p.score_reason}")

                filtered = [p for p in scored if p.relevance_score >= threshold]

                if not filtered:
                    self._set_status(status_target, f"AI 筛选后没有论文通过阈值 {threshold}，请调整阈值后重试。")
                    return

                self._set_status(status_target, f"AI 筛选完成：{len(filtered)}/{len(papers)} 篇通过（阈值={threshold}）。")

                if review_needed:
                    self.main_win.after(100, lambda: self._open_review_win_and_replace(filtered))
                else:
                    self._generate_briefing(filtered, topic, from_ui=False)

            except Exception as e:
                import traceback
                traceback.print_exc()
                self._set_status(status_target, f"AI 筛选失败: {e}")

        threading.Thread(target=run, daemon=True).start()

    # ── 生成简报 ──────────────────────────────────

    def _generate_briefing(self, papers: list, topic: str, from_ui: bool):
        """调用 PaperReporter 生成 Word 简报"""

        use_review = not from_ui and self.review_win and self.review_win.winfo_exists()

        def run():
            if use_review:
                progress_shown = False
                def progress_cb(step, detail=""):
                    nonlocal progress_shown
                    if not progress_shown:
                        progress_shown = True
                        self.main_win.after(0, lambda: self.review_win.start_progress())
                    self.main_win.after(0, lambda s=step, d=detail: self.review_win.set_progress(-1, s, d))
            else:
                def progress_cb(step, detail=""):
                    self.main_win.after(0, lambda s=step, d=detail: self.main_win.set_status(f"{s} {d}".strip()))

            try:
                progress_cb("初始化简报生成器...")
                reporter = PaperReporter(topic=topic)
                reader = PaperReader()

                result = reporter.generate_full_report(
                    papers,
                    reader,
                    on_progress=lambda msg: progress_cb(msg),
                )

                if result.get("success"):
                    report_path = result.get("report_path", "")
                    n_generated = result.get("papers_generated", 0)
                    errors = result.get("errors", [])

                    self.main_win.after(0, lambda: self.main_win.set_upload_btn_state(True))

                    if errors:
                        progress_cb("简报生成完成（部分失败）", f"已处理 {n_generated} 篇，{len(errors)} 个错误")
                    else:
                        progress_cb("简报生成完成！", f"已处理 {n_generated} 篇论文")

                    if use_review:
                        self.main_win.after(1500, lambda: self.review_win.close())
                else:
                    progress_cb("生成失败", "未知错误")

            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_cb("生成失败", str(e))

        threading.Thread(target=run, daemon=True).start()

    # ── Pi 上传/下载 ──────────────────────────────

    def _get_pi_client(self) -> PiClient:
        ip = cfg.get("pi_ip", "10.106.147.220")
        port = cfg.get("pi_port", 5000)
        return PiClient(ip=ip, port=port)

    def _on_upload_to_pi(self):
        """上传最新生成的简报到 Pi"""
        # 找 reports 目录下最新的 docx 文件
        import glob, os
        reports = glob.glob(os.path.join(REPORTS_DIR, "*.docx"))
        if not reports:
            self.main_win.set_status("没有找到已生成的简报文件")
            return
        latest = max(reports, key=os.path.getmtime)
        fname = os.path.basename(latest)

        def run():
            self.main_win.after(0, lambda: self.main_win.set_status(f"正在上传 {fname} 到 Pi..."))
            try:
                client = self._get_pi_client()
                client.upload_report(latest)
                self.main_win.after(0, lambda: self.main_win.set_status(f"✅ 上传成功: {fname}"))
            except Exception as e:
                self.main_win.after(0, lambda: self.main_win.set_status(f"❌ 上传失败: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def _on_download_from_pi(self):
        """从 Pi 下载简报列表，让用户选择下载"""
        def run():
            try:
                client = self._get_pi_client()
                files = client.list_reports()
                self.main_win.after(0, lambda: self.main_win.show_pi_download_dialog(
                    files,
                    on_download=lambda fname: self._do_download(client, fname),
                ))
            except Exception as e:
                self.main_win.after(0, lambda: self.main_win.set_status(f"❌ 连接Pi失败: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def _do_download(self, client: PiClient, filename: str):
        def run():
            self.main_win.after(0, lambda: self.main_win.set_status(f"正在下载 {filename}..."))
            try:
                path = client.download_report(filename, REPORTS_DIR)
                self.main_win.after(0, lambda: self.main_win.set_status(f"✅ 下载完成: {os.path.basename(path)}"))
            except Exception as e:
                self.main_win.after(0, lambda: self.main_win.set_status(f"❌ 下载失败: {e}"))

        threading.Thread(target=run, daemon=True).start()

    # ── 设置界面 ─────────────────────────────────

    def _generate_posters(self, papers: list, topic: str, progress_cb):
        """在简报生成完成后，自动为每篇论文生成海报"""
        def run():
            try:
                progress_cb("正在初始化海报生成器...")
                from poster import PosterGenerator
                generator = PosterGenerator(topic=topic)

                def poster_progress(msg):
                    progress_cb(msg)

                results = generator.generate(papers, PaperReader(), on_progress=poster_progress)

                success_count = sum(1 for r in results if r.get("success"))
                if success_count > 0:
                    progress_cb(f"海报生成完成！", f"成功 {success_count}/{len(results)} 篇")
                else:
                    progress_cb("海报生成失败", "没有成功生成任何海报")

            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_cb(f"海报生成失败: {e}")

        threading.Thread(target=run, daemon=True).start()

    def _generate_posters_from_review(self, papers: list, topic: str):
        """从审核窗口触发：仅生成海报图片"""
        def run():
            self.main_win.after(0, lambda: self.review_win.start_progress())

            def progress_cb(step, detail=""):
                self.main_win.after(0, lambda s=step, d=detail: self.review_win.set_progress(-1, s, d))

            try:
                progress_cb("正在初始化海报生成器...")
                from poster import PosterGenerator
                generator = PosterGenerator(topic=topic)
                results = generator.generate(papers, PaperReader(), on_progress=progress_cb)

                success_count = sum(1 for r in results if r.get("success"))
                if success_count > 0:
                    progress_cb("海报生成完成！", f"成功 {success_count}/{len(results)} 篇")
                else:
                    progress_cb("海报生成失败", "没有成功生成任何海报")
            except Exception as e:
                import traceback
                traceback.print_exc()
                progress_cb("海报生成失败", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _on_open_settings(self):
        win = SettingsWindow(self.main_win)
        win.geometry("580x620+500+200")
        win.on_saved = lambda _: (self.main_win.set_status("设置已保存"), self.main_win.refresh_mode_ui())

    # ── 简报管理界面 ─────────────────────────────

    def _on_open_reports(self):
        if self.reports_win and self.reports_win.winfo_exists():
            self.reports_win.lift()
            return
        self.reports_win = ReportsWindow(self.main_win)
        self.reports_win.geometry("700x500+300+150")
        self.reports_win.on_refresh_main = lambda: self.main_win.set_upload_btn_state(
            bool(self._find_latest_report())
        )

    def _on_open_poster_gallery(self):
        PosterGalleryWindow(self.main_win)

    def _find_latest_report(self) -> str:
        """查找最新的简报文件"""
        import glob
        files = glob.glob(os.path.join(REPORTS_DIR, "*.docx"))
        if not files:
            return ""
        return max(files, key=os.path.getmtime)


if __name__ == "__main__":
    App()
