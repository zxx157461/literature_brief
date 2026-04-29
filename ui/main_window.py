"""
main_window.py - 主界面
S2 - 白色主题版
"""
import os
import glob as _glob_mod
import customtkinter as ctk
from typing import Callable, Optional
from config import cfg

# 白色主题配色
COLORS = {
    "bg": "#F5F6FA",
    "surface": "#FFFFFF",
    "border": "#E2E4E8",
    "primary": "#3B82F6",
    "primary_light": "#EFF6FF",
    "accent": "#E94560",
    "text": "#1F2937",
    "text_secondary": "#6B7280",
    "text_light": "#9CA3AF",
    "success": "#10B981",
    "warning": "#F59E0B",
    "error": "#EF4444",
}

ARXIV_CATEGORIES = [
    "cond-mat.soft", "cond-mat.stat-mech", "cond-mat.mes-hall",
    "physics.data-an", "physics.comp-ph", "quant-ph",
    "nlin.AO", "nlin.PS", "nlin.CG",
    "cs.LG", "cs.AI", "math-ph",
    "hep-th", "gr-qc", "astro-ph.CO",
]


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("文献简报生成器")
        self.geometry("960x620")
        self.configure(fg_color=COLORS["bg"])
        self.resizable(True, True)
        ctk.set_appearance_mode("light")

        self.on_search_clicked: Optional[Callable] = None
        self.on_open_settings: Optional[Callable] = None
        self.on_open_review: Optional[Callable] = None
        self.on_send_to_ai: Optional[Callable] = None
        self.on_upload_to_pi: Optional[Callable] = None
        self.on_download_from_pi: Optional[Callable] = None
        self.on_open_reports: Optional[Callable] = None
        self.on_open_poster_gallery: Optional[Callable] = None

        self.grid_columnconfigure(0, weight=1)

        # 顶部标题栏
        self._build_header()
        # 搜索面板
        self._build_search_panel()
        # 状态栏
        self._build_status_bar()
        # 结果列表
        self.result_outer = ctk.CTkFrame(self, fg_color="transparent")
        self.result_outer.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 0))
        self.result_frame = ctk.CTkScrollableFrame(
            self.result_outer, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=COLORS["border"],
            scrollbar_fg_color=COLORS["border"],
        )
        self.result_frame.pack(fill="x")
        self._build_empty_state()
        # 底部操作栏
        self._build_action_bar()
        # 启动时检测简报库
        self._refresh_report_btn_state()

    def _refresh_report_btn_state(self):
        """根据简报库文件存在性刷新查看最新简报按钮"""
        path = self._find_latest_report()
        self.open_report_btn.configure(
            state="normal" if path else "disabled",
            fg_color=COLORS["success"] if path else COLORS["border"],
            text_color="white" if path else COLORS["text"],
        )

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=48)
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="📚 文献简报生成器",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLORS["text"],
            padx=16,
        ).grid(row=0, column=0, sticky="w")

        reports_btn = ctk.CTkButton(
            header,
            text="📄 简报管理",
            width=90, height=28,
            fg_color=COLORS["primary_light"],
            hover_color=COLORS["border"],
            text_color=COLORS["primary"],
            font=ctk.CTkFont(size=12),
            command=lambda: self.on_open_reports and self.on_open_reports(),
        )
        reports_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))

        gallery_btn = ctk.CTkButton(
            header,
            text="🖼️ 海报画廊",
            width=90, height=28,
            fg_color=COLORS["primary_light"],
            hover_color=COLORS["border"],
            text_color=COLORS["primary"],
            font=ctk.CTkFont(size=12),
            command=lambda: self.on_open_poster_gallery and self.on_open_poster_gallery(),
        )
        gallery_btn.grid(row=0, column=2, sticky="e", padx=(0, 8))

        settings_btn = ctk.CTkButton(
            header,
            text="⚙️ 设置",
            width=76, height=28,
            fg_color=COLORS["bg"],
            border_color=COLORS["border"],
            border_width=1,
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=12),
            command=lambda: self.on_open_settings and self.on_open_settings(),
        )
        settings_btn.grid(row=0, column=3, sticky="e", padx=16)

    def _build_search_panel(self):
        panel = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=10)
        panel.grid(row=1, column=0, sticky="ew", padx=12, pady=(8, 4))
        panel.grid_columnconfigure(0, weight=0)
        panel.grid_columnconfigure(1, weight=1)

        # ===== 第0行：模式/篇数/排序 + 搜索按钮（顶行）=====
        self.mode_menu = ctk.CTkOptionMenu(
            panel,
            values=["🤖 AI自动化", "👨‍💻 协作研究"],
            width=120, height=30,
            fg_color=COLORS["bg"],
            dropdown_fg_color=COLORS["surface"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(11),
        )
        self.mode_menu.grid(row=0, column=0, sticky="w", padx=16, pady=(10, 4))
        self.mode_menu.set("🤖 AI自动化")

        self.max_results_entry = ctk.CTkEntry(
            panel, width=48, height=28,
            fg_color=COLORS["bg"], border_color=COLORS["border"],
            font=ctk.CTkFont(11), justify="center", corner_radius=5,
        )
        self.max_results_entry.grid(row=0, column=0, sticky="w", padx=(150, 4), pady=(10, 4))
        self.max_results_entry.insert(0, "20")
        ctk.CTkLabel(panel, text="篇", text_color=COLORS["text_secondary"], font=ctk.CTkFont(10)
        ).grid(row=0, column=0, sticky="w", padx=(200, 4), pady=(10, 4))

        self.sort_menu = ctk.CTkOptionMenu(
            panel,
            values=["相关性", "最新更新", "最新提交"],
            width=90, height=28,
            fg_color=COLORS["bg"],
            dropdown_fg_color=COLORS["surface"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(10),
        )
        self.sort_menu.grid(row=0, column=0, sticky="w", padx=(230, 4), pady=(10, 4))
        self.sort_menu.set("相关性")

        self.search_btn = ctk.CTkButton(
            panel,
            text="🔍 搜索",
            width=80, height=32,
            fg_color=COLORS["primary"],
            hover_color="#2563EB",
            text_color="white",
            font=ctk.CTkFont(12, weight="bold"),
            corner_radius=6,
            command=self._trigger_search,
        )
        self.search_btn.grid(row=0, column=1, sticky="e", padx=14, pady=(10, 4))

        # ===== 第1行：关键词 =====
        self.keyword_entry = ctk.CTkEntry(
            panel,
            placeholder_text="关键词，例如: active matter phase transition  /  ti:neural network AND abs:machine learning",
            height=34,
            fg_color=COLORS["bg"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(12),
            corner_radius=6,
        )
        self.keyword_entry.grid(
            row=1, column=0, columnspan=2,
            sticky="ew", padx=16, pady=(6, 0)
        )
        self.keyword_entry.bind("<Return>", lambda e: self._trigger_search())

        # ===== 第2行：作者 + 年份 =====
        author_frame = ctk.CTkFrame(panel, fg_color="transparent")
        author_frame.grid(row=2, column=0, columnspan=2, sticky="w", padx=16, pady=(6, 0))

        ctk.CTkLabel(author_frame, text="作者", text_color=COLORS["text_secondary"], font=ctk.CTkFont(11)
        ).grid(row=0, column=0, padx=(0, 4), pady=0, sticky="w")

        self.author_entry = ctk.CTkEntry(
            author_frame, width=130, height=28,
            placeholder_text="作者姓名（可选）",
            fg_color=COLORS["bg"], border_color=COLORS["border"],
            font=ctk.CTkFont(11), corner_radius=5,
        )
        self.author_entry.grid(row=0, column=1, padx=(0, 14), pady=0)

        ctk.CTkLabel(author_frame, text="日期", text_color=COLORS["text_secondary"], font=ctk.CTkFont(11)
        ).grid(row=0, column=2, padx=(0, 4), pady=0, sticky="w")

        self.year_from = ctk.CTkEntry(
            author_frame, width=86, height=28,
            placeholder_text="YYYY-MM-DD",
            fg_color=COLORS["bg"], border_color=COLORS["border"],
            font=ctk.CTkFont(10), justify="center", corner_radius=5,
        )
        self.year_from.grid(row=0, column=3, padx=(0, 2), pady=0)

        ctk.CTkLabel(author_frame, text="—", text_color=COLORS["text_secondary"], font=ctk.CTkFont(11)
        ).grid(row=0, column=4, padx=(0, 2), pady=0)

        self.year_to = ctk.CTkEntry(
            author_frame, width=86, height=28,
            placeholder_text="YYYY-MM-DD",
            fg_color=COLORS["bg"], border_color=COLORS["border"],
            font=ctk.CTkFont(10), justify="center", corner_radius=5,
        )
        self.year_to.grid(row=0, column=5, padx=(0, 4), pady=0)

        # ===== 第3行：分类标签（底部）=====
        cat_section = ctk.CTkFrame(panel, fg_color=COLORS["primary_light"], corner_radius=6)
        cat_section.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(6, 8))
        cat_section.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cat_section,
            text="  分类：",
            text_color=COLORS["primary"],
            font=ctk.CTkFont(11, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=0, pady=6)

        self.cat_vars = {}
        for i, cat in enumerate(ARXIV_CATEGORIES):
            var = ctk.BooleanVar(value=False)
            self.cat_vars[cat] = var
            if i % 4 == 0:
                row_frame = ctk.CTkFrame(cat_section, fg_color="transparent")
                row_frame.grid(row=1 + i // 4, column=0, sticky="w", padx=0, pady=(0, 2))
            ctk.CTkCheckBox(
                row_frame,
                text=cat,
                variable=var,
                height=20,
                fg_color=COLORS["primary"],
                text_color=COLORS["primary"],
                font=ctk.CTkFont(9),
                checkbox_width=14, checkbox_height=14,
                command=self._on_cat_toggle,
            ).pack(side="left", padx=(0, 5))

        self.cat_count_label = ctk.CTkLabel(
            cat_section, text="已选 0 个",
            text_color=COLORS["primary"], font=ctk.CTkFont(10),
        )
        self.cat_count_label.grid(row=0, column=1, sticky="e", padx=(0, 8), pady=6)

        # ===== 第4行：AI筛选要求（仅其他AI筛选模式时显示）=====
        self._sift_req_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self._sift_req_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8))
        ctk.CTkLabel(
            self._sift_req_frame,
            text="筛选要求：",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(11),
        ).pack(side="left")
        self.sift_requirement_entry = ctk.CTkEntry(
            self._sift_req_frame,
            placeholder_text="描述筛选标准，例如：只保留实验性研究，排除纯综述，关注软物质体系",
            height=30,
            fg_color=COLORS["bg"],
            border_color=COLORS["border"],
            font=ctk.CTkFont(11),
            corner_radius=6,
        )
        self.sift_requirement_entry.pack(side="left", fill="x", expand=True)
        self._update_sift_req_visibility()

    def _on_cat_toggle(self):
        count = sum(v.get() for v in self.cat_vars.values())
        self.cat_count_label.configure(text=f"已选 {count} 个")

    def _update_sift_req_visibility(self):
        """根据当前筛选模式决定是否显示筛选要求输入框"""
        mode = cfg.get("screen_mode", "人工筛选")
        if mode in ("其他AI筛选", "openclaw筛选"):
            self._sift_req_frame.grid()
        else:
            self._sift_req_frame.grid_remove()

    def refresh_mode_ui(self):
        """设置保存后由外部调用，刷新模式相关UI"""
        self._update_sift_req_visibility()

    def _build_status_bar(self):
        sf = ctk.CTkFrame(self, fg_color="transparent", height=32)
        sf.grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 0))
        sf.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            sf, text="就绪",
            text_color=COLORS["text_light"],
            font=ctk.CTkFont(11), anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="w")

        self.progress_bar = ctk.CTkProgressBar(
            sf, width=200, height=5,
            progress_color=COLORS["primary"],
            fg_color=COLORS["border"],
            corner_radius=3,
        )
        self.progress_bar.grid(row=0, column=1, padx=(10, 0), sticky="e")
        self.progress_bar.set(0)

    def _build_empty_state(self):
        for widget in self.result_frame.winfo_children():
            widget.destroy()

        inner = ctk.CTkFrame(self.result_frame, fg_color="transparent")
        inner.pack(pady=(20, 0))

        ctk.CTkLabel(
            inner, text="🔍",
            font=ctk.CTkFont(size=36),
            text_color=COLORS["text_light"],
        ).pack()

        ctk.CTkLabel(
            inner, text="输入条件开始搜索",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
        ).pack(pady=(8, 4))

        ctk.CTkLabel(
            inner,
            text="支持 arXiv 语法: AND/OR/ANDNOT, ti:/abs:/au:/cat:",
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        ).pack()

    def _build_action_bar(self):
        af = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=60)
        af.grid(row=4, column=0, sticky="ew", pady=0)
        af.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(af, fg_color=COLORS["border"], height=1).grid(
            row=0, column=0, columnspan=3, sticky="nw", padx=0
        )

        self.selected_count_label = ctk.CTkLabel(
            af, text="已选: 0 篇",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(12),
        )
        self.selected_count_label.grid(row=0, column=0, padx=20, pady=12, sticky="w")

        self.ai_review_btn = ctk.CTkButton(
            af,
            text="✨  生成简报",
            width=140, height=36,
            fg_color=COLORS["primary"],
            hover_color="#2563EB",
            text_color="white",
            state="disabled",
            font=ctk.CTkFont(12, weight="bold"),
            corner_radius=8,
            command=lambda: self.on_send_to_ai and self.on_send_to_ai(),
        )
        self.ai_review_btn.grid(row=0, column=1, padx=8, pady=10, sticky="e")

        self.open_report_btn = ctk.CTkButton(
            af,
            text="📄 查看最新简报",
            width=130, height=36,
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
            hover_color=COLORS["border"],
            state="disabled",
            font=ctk.CTkFont(12),
            corner_radius=8,
            command=self._open_latest_report,
        )
        self.open_report_btn.grid(row=0, column=2, padx=(8, 20), pady=10, sticky="e")

    def _trigger_search(self):
        keyword = self.keyword_entry.get().strip()
        if not keyword:
            self.keyword_entry.configure(border_color=COLORS["error"])
            return
        self.keyword_entry.configure(border_color=COLORS["border"])

        try:
            max_results = int(self.max_results_entry.get())
        except ValueError:
            max_results = 20

        date_from = self.year_from.get().strip() or None
        date_to = self.year_to.get().strip() or None
        author = self.author_entry.get().strip() or None
        categories = [k for k, v in self.cat_vars.items() if v.get()]

        sort_map = {
            "相关性": "relevance",
            "最新更新": "lastUpdatedDate",
            "最新提交": "submittedDate",
        }

        if self.on_search_clicked:
            self.on_search_clicked(
                keyword=keyword,
                mode="manual" if "协作" in self.mode_menu.get() else "auto",
                sort_by=sort_map[self.sort_menu.get()],
                max_results=max_results,
                date_from=date_from,
                date_to=date_to,
                author=author,
                categories=categories,
                sift_requirement=self.sift_requirement_entry.get().strip(),
            )

    def set_status(self, text: str, progress: float = None):
        self.status_label.configure(text=text)
        if progress is not None:
            self.progress_bar.set(progress)
            if progress >= 1.0:
                self.after(2000, lambda: self.progress_bar.set(0))

    def set_searching(self, active: bool):
        """搜索状态切换：禁用/启用搜索按钮，防止重复点击"""
        state = "disabled" if active else "normal"
        self.search_btn.configure(state=state)

    def show_results(self, papers: list):
        self.progress_bar.set(0)
        for widget in self.result_frame.winfo_children():
            widget.destroy()
        if not papers:
            ctk.CTkLabel(
                self.result_frame,
                text="😕  未找到相关论文，请尝试调整条件",
                text_color=COLORS["text_secondary"],
                font=ctk.CTkFont(13),
            ).pack(pady=80)
            self._update_selected_count()
            return
        for i, paper in enumerate(papers):
            PaperCard(self.result_frame, paper, i, on_toggle=self._update_selected_count).pack(fill="x", pady=4)
        self._update_selected_count()

    def _update_selected_count(self):
        cards = [w for w in self.result_frame.winfo_children() if isinstance(w, PaperCard)]
        count = sum(1 for c in cards if c.var.get())
        self.selected_count_label.configure(text=f"已选: {count} 篇")

    def set_buttons_state(self, review_enabled: bool, ai_review_enabled: bool):
        self.ai_review_btn.configure(
            state="normal" if ai_review_enabled else "disabled",
        )

    def get_selected_papers(self) -> list:
        cards = [w for w in self.result_frame.winfo_children() if isinstance(w, PaperCard)]
        return [c.paper for c in cards if c.var.get()]

    def select_all_papers(self):
        """全选所有论文"""
        cards = [w for w in self.result_frame.winfo_children() if isinstance(w, PaperCard)]
        for c in cards:
            c.var.set(True)
            c.paper.selected = True
        self._update_selected_count()

    def set_upload_btn_state(self, enabled: bool):
        """启用/禁用查看简报按钮（生成简报后调用）"""
        self._refresh_report_btn_state()

    def _find_latest_report(self) -> str:
        """查找最新的简报文件"""
        from config import REPORTS_DIR
        files = _glob_mod.glob(os.path.join(REPORTS_DIR, "*.docx"))
        if not files:
            return ""
        return max(files, key=os.path.getmtime)

    def _open_latest_report(self):
        """用默认程序打开最新简报"""
        path = self._find_latest_report()
        if not path:
            self.set_status("未找到简报文件")
            return
        try:
            os.startfile(path)
            self.set_status(f"正在打开: {os.path.basename(path)}")
        except Exception as e:
            self.set_status(f"打开失败: {e}")

    def show_pi_download_dialog(self, file_list: list[str], on_download):
        """弹出Pi文件浏览下载对话框"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("⬇ 从Pi下载简报")
        dialog.geometry("480x400")
        dialog.configure(fg_color=COLORS["bg"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="选择要下载的简报:",
            text_color=COLORS["text"], font=ctk.CTkFont(13, weight="bold"),
        ).pack(pady=(16, 8))

        if not file_list:
            ctk.CTkLabel(
                dialog, text="Pi 上暂无简报",
                text_color=COLORS["text_secondary"],
            ).pack(pady=40)
        else:
            scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=280)
            scroll.pack(fill="both", expand=True, padx=16, pady=8)
            for fname in file_list:
                row = ctk.CTkFrame(scroll, fg_color=COLORS["surface"], corner_radius=8)
                row.pack(fill="x", pady=3, ipady=6)
                ctk.CTkLabel(
                    row, text=fname, text_color=COLORS["text"],
                    font=ctk.CTkFont(12), anchor="w",
                ).pack(side="left", padx=12, fill="x", expand=True)
                ctk.CTkButton(
                    row, text="下载", width=60, height=28,
                    fg_color=COLORS["primary"], hover_color="#2563EB",
                    text_color="white", font=ctk.CTkFont(11),
                    corner_radius=6,
                    command=lambda f=fname: [dialog.destroy(), on_download(f)],
                ).pack(side="right", padx=8)

        ctk.CTkButton(
            dialog, text="关闭", width=100, height=32,
            fg_color=COLORS["bg"], text_color=COLORS["text"],
            font=ctk.CTkFont(12), command=dialog.destroy,
        ).pack(pady=12)


class PaperCard(ctk.CTkFrame):
    def __init__(self, parent, paper, index: int, on_toggle=None):
        super().__init__(
            parent,
            fg_color=COLORS["surface"],
            corner_radius=10,
        )
        self.paper = paper
        self.on_toggle = on_toggle
        self.var = ctk.BooleanVar(value=paper.selected)

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkCheckBox(
            self, variable=self.var, text="",
            width=32,
            fg_color=COLORS["primary"],
            border_color=COLORS["border"],
            checkbox_width=18, checkbox_height=18,
            command=self._on_check,
        ).grid(row=0, column=0, rowspan=2, padx=(12, 0), pady=14, sticky="n")

        ctk.CTkLabel(
            self,
            text=f"{index + 1:02d}.",
            text_color=COLORS["text_light"],
            font=ctk.CTkFont(11),
            width=28,
        ).grid(row=0, column=1, padx=(4, 8), pady=(12, 0), sticky="nw")

        ctk.CTkLabel(
            self,
            text=paper.title,
            text_color=COLORS["text"],
            font=ctk.CTkFont(12, weight="bold"),
            anchor="w",
            wraplength=680,
        ).grid(row=0, column=1, padx=(32, 8), pady=(10, 0), sticky="nw")

        info = f"{paper.display_authors}  ·  {paper.submitted_date}  ·  [{', '.join(paper.categories[:3])}]"
        ctk.CTkLabel(
            self, text=info,
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(10),
            anchor="w",
        ).grid(row=1, column=1, padx=(32, 8), pady=(0, 10), sticky="nw")

        if paper.relevance_score > 0:
            color = COLORS["success"] if paper.relevance_score >= 0.7 else COLORS["warning"]
            ctk.CTkLabel(
                self,
                text=f"★ {paper.relevance_score:.0%}",
                text_color="white",
                font=ctk.CTkFont(11, weight="bold"),
                width=64, height=24,
                fg_color=color,
                corner_radius=12,
            ).grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=12, sticky="n")

    def _on_check(self):
        self.paper.selected = self.var.get()
        if self.on_toggle:
            self.on_toggle()
