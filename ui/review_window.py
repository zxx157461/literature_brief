"""
review_window.py - 审核界面
S3 - 白色主题版
"""
import customtkinter as ctk
from papers import Paper

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
}


class ReviewWindow(ctk.CTkToplevel):
    def __init__(self, parent, papers: list[Paper]):
        super().__init__(parent)
        self.papers = papers
        self.title("📋 论文审核")
        self.geometry("1000x750")
        self.configure(fg_color=COLORS["bg"])
        self.transient(parent)
        self.grab_set()

        self.on_confirm_text = None
        self.on_confirm_image = None

        self._build_widgets()
        self._populate_papers()

    def _build_widgets(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ====== 顶部工具栏 ======
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=50)
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        toolbar.grid_columnconfigure(2, weight=1)

        self.select_all_btn = ctk.CTkButton(
            toolbar,
            text="☑️ 全选",
            width=80, height=30,
            fg_color=COLORS["primary"],
            hover_color="#2563EB",
            command=self._select_all,
        )
        self.select_all_btn.grid(row=0, column=0, padx=(12, 4), pady=10, sticky="w")

        self.select_inv_btn = ctk.CTkButton(
            toolbar,
            text="🔄 反选",
            width=80, height=30,
            fg_color=COLORS["bg"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            command=self._select_inv,
        )
        self.select_inv_btn.grid(row=0, column=1, padx=4, pady=10, sticky="w")

        self.stats_label = ctk.CTkLabel(
            toolbar,
            text=f"共 {len(self.papers)} 篇，已选 0 篇",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(12),
        )
        self.stats_label.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        self.ai_suggest_btn = ctk.CTkButton(
            toolbar,
            text="🤖 AI 一键推荐",
            width=130, height=30,
            fg_color=COLORS["accent"],
            hover_color="#c73e54",
            command=self._on_ai_suggest,
        )
        self.ai_suggest_btn.grid(row=0, column=3, padx=4, pady=10, sticky="e")

        # ====== 主区域 ======
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=16, pady=6)
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=0)
        main.grid_rowconfigure(0, weight=1)

        # 左：论文列表
        list_frame = ctk.CTkScrollableFrame(
            main,
            fg_color=COLORS["surface"],
            corner_radius=10,
        )
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # 右：AI 建议面板
        ai_panel = ctk.CTkFrame(main, fg_color=COLORS["surface"], width=280, corner_radius=10)
        ai_panel.grid(row=0, column=1, sticky="nsew", padx=0)
        ai_panel.grid_propagate(False)

        ctk.CTkLabel(
            ai_panel,
            text="💬 AI 助手建议",
            text_color=COLORS["text"],
            font=ctk.CTkFont(14, weight="bold"),
        ).pack(anchor="w", padx=15, pady=(15, 5))

        self.ai_content = ctk.CTkTextbox(
            ai_panel,
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(12),
            wrap="word",
            state="disabled",
        )
        self.ai_content.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        ai_input_frame = ctk.CTkFrame(ai_panel, fg_color="transparent", height=80)
        ai_input_frame.pack(fill="x", padx=10, pady=(0, 10))
        ai_input_frame.pack_propagate(False)

        self.ai_input = ctk.CTkTextbox(
            ai_input_frame,
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(11),
            height=60,
            wrap="word",
        )
        self.ai_input.pack(fill="x")
        self.ai_input.insert("0.0", "有什么需要我帮你分析这篇论文的？")

        ctk.CTkButton(
            ai_input_frame,
            text="发送 ➤",
            height=28,
            fg_color=COLORS["primary"],
            hover_color="#2563EB",
            command=self._on_ai_send,
        ).pack(anchor="e", pady=(5, 0))

        # 底部
        bottom = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=55)
        bottom.grid(row=2, column=0, sticky="ew", pady=0)
        bottom.grid_columnconfigure(1, weight=1)

        ctk.CTkFrame(bottom, fg_color=COLORS["border"], height=1).grid(
            row=0, column=0, columnspan=3, sticky="nw", padx=0
        )

        self.confirm_label = ctk.CTkLabel(
            bottom,
            text="已选 0 篇",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(12),
        )
        self.confirm_label.grid(row=0, column=0, padx=20, pady=12, sticky="w")

        self.status_label = ctk.CTkLabel(
            bottom,
            text="",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(11),
        )
        self.status_label.grid(row=0, column=1, padx=10, pady=12, sticky="w")

        self.text_btn = ctk.CTkButton(
            bottom,
            text="📄 生成文本简报",
            width=150, height=36,
            fg_color=COLORS["success"],
            hover_color="#0ea569",
            command=self._on_confirm_text,
        )
        self.text_btn.grid(row=0, column=2, padx=(0, 8), pady=8, sticky="e")

        self.image_btn = ctk.CTkButton(
            bottom,
            text="🖼️ 生成图片简报",
            width=150, height=36,
            fg_color=COLORS["primary"],
            hover_color="#2563EB",
            command=self._on_confirm_image,
        )
        self.image_btn.grid(row=0, column=3, padx=(0, 20), pady=8, sticky="e")

        self.list_frame = list_frame
        self.paper_cards = []

        # ====== 进度覆盖层（默认隐藏） ======
        self.overlay = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=12)

        self.progress_title = ctk.CTkLabel(
            self.overlay,
            text="正在生成简报",
            text_color=COLORS["text"],
            font=ctk.CTkFont(16, weight="bold"),
        )
        self.progress_title.pack(pady=(30, 10))

        self.progress_step = ctk.CTkLabel(
            self.overlay,
            text="",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(13),
        )
        self.progress_step.pack(pady=(0, 20))

        self.progress_bar = ctk.CTkProgressBar(
            self.overlay,
            width=400,
            height=8,
            progress_color=COLORS["primary"],
            fg_color=COLORS["border"],
            corner_radius=4,
        )
        self.progress_bar.pack(pady=(0, 10))
        self.progress_bar.set(0)

        self.progress_detail = ctk.CTkLabel(
            self.overlay,
            text="",
            text_color=COLORS["text_light"],
            font=ctk.CTkFont(11),
        )
        self.progress_detail.pack(pady=(0, 20))

    def _populate_papers(self):
        for i, paper in enumerate(self.papers):
            card = ReviewPaperCard(self.list_frame, paper, i, on_toggle=self._update_stats)
            card.pack(fill="x", pady=3)
            self.paper_cards.append(card)

    def _update_stats(self):
        selected = sum(1 for c in self.paper_cards if c.var.get())
        self.stats_label.configure(text=f"共 {len(self.papers)} 篇，已选 {selected} 篇")
        self.confirm_label.configure(text=f"已选 {selected} 篇")

    def _select_all(self):
        for c in self.paper_cards:
            c.var.set(True)
        self._update_stats()

    def _select_inv(self):
        for c in self.paper_cards:
            c.var.set(not c.var.get())
        self._update_stats()

    def _get_selected(self) -> list:
        return [c.paper for c in self.paper_cards if c.var.get()]

    def _disable_buttons(self):
        self.text_btn.configure(state="disabled")
        self.image_btn.configure(state="disabled")
        self.select_all_btn.configure(state="disabled")
        self.select_inv_btn.configure(state="disabled")
        self.ai_suggest_btn.configure(state="disabled")

    def _on_confirm_text(self):
        selected = self._get_selected()
        if not selected:
            return
        self._disable_buttons()
        if self.on_confirm_text:
            self.on_confirm_text(selected)

    def _on_confirm_image(self):
        selected = self._get_selected()
        if not selected:
            return
        self._disable_buttons()
        if self.on_confirm_image:
            self.on_confirm_image(selected)

    def set_progress(self, value: float, step: str, detail: str):
        """更新进度：value 0~1（-1表示不更新进度条）, step 当前步骤文字, detail 补充信息"""
        if self.winfo_exists():
            if value >= 0:
                self.progress_bar.set(value)
            self.progress_step.configure(text=step)
            if detail:
                self.progress_detail.configure(text=detail)
            self.update_idletasks()

    def start_progress(self):
        """开始生成简报时调用，显示进度覆盖层"""
        if self.winfo_exists():
            self.overlay.place(relx=0.05, rely=0.15, relwidth=0.9, relheight=0.7)
            self.update_idletasks()

    def close(self):        self.destroy()

    def _on_ai_suggest(self):
        self._set_ai_content("AI 一键推荐功能暂未实现，请手动选择论文。")

    def _on_ai_send(self):
        self._set_ai_content("AI 对话功能暂未实现。")

    def _set_ai_content(self, text: str):
        self.ai_content.configure(state="normal")
        self.ai_content.delete("0.0", "end")
        self.ai_content.insert("0.0", text)
        self.ai_content.configure(state="disabled")

    def set_status(self, text: str):
        if self.winfo_exists():
            self.status_label.configure(text=text)
            self.update_idletasks()


class ReviewPaperCard(ctk.CTkFrame):
    def __init__(self, parent, paper: Paper, index: int, on_toggle=None):
        super().__init__(
            parent,
            fg_color=COLORS["bg"],
            corner_radius=8,
        )
        self.paper = paper
        self.on_toggle = on_toggle
        self.var = ctk.BooleanVar(value=paper.selected)

        self.grid_columnconfigure(1, weight=1)

        ctk.CTkCheckBox(
            self,
            variable=self.var,
            text="",
            width=30,
            fg_color=COLORS["primary"],
            command=self._on_check,
        ).grid(row=0, column=0, rowspan=2, padx=10, pady=12, sticky="n")

        ctk.CTkLabel(
            self,
            text=f"{index + 1:02d}. {paper.title}",
            text_color=COLORS["text"],
            font=ctk.CTkFont(12, weight="bold"),
            anchor="w",
            wraplength=500,
        ).grid(row=0, column=1, padx=(0, 5), pady=(10, 0), sticky="nw")

        info = f"{paper.display_authors}  ·  {paper.submitted_date}"
        ctk.CTkLabel(
            self,
            text=info,
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(10),
            anchor="w",
        ).grid(row=1, column=1, padx=(0, 5), pady=(0, 8), sticky="nw")

        score_color = (
            COLORS["success"] if paper.relevance_score >= 0.7
            else COLORS["warning"] if paper.relevance_score >= 0.5
            else COLORS["text_light"]
        )
        ctk.CTkLabel(
            self,
            text=f"★ {paper.relevance_score:.0%}",
            text_color=score_color,
            font=ctk.CTkFont(12, weight="bold"),
            width=60,
        ).grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=10, sticky="ne")

    def _on_check(self):
        self.paper.selected = self.var.get()
        if self.on_toggle:
            self.on_toggle()


if __name__ == "__main__":
    # 测试：直接运行此文件查看效果
    ctk.set_appearance_mode("light")

    root = ctk.CTk()
    root.withdraw()

    mock_papers = [
        Paper(
            arxiv_id=f"2401.{i:05d}",
            title=f"Example Paper Title {i}: A Deep Learning Approach for Scientific Research",
            authors=["Zhang Wei", "Li Ming"] if i % 2 == 0 else ["Chen Hui"],
            abstract="This paper presents...",
            categories=["cond-mat.soft", "physics.data-an"],
            submitted_date="2024-01-15",
            updated_date="2024-02-20",
            pdf_url=f"https://arxiv.org/pdf/2401.{i:05d}.pdf",
            relevance_score=0.9 - i * 0.05,
        )
        for i in range(1, 11)
    ]

    win = ReviewWindow(root, mock_papers)
    root.wait_window()
