"""
poster_gallery.py - 海报画廊查看界面

左侧：按检索主题（session）分组的目录树
右侧：选中主题下的所有海报缩略图，支持滑动查看
点击缩略图可放大
"""
import os
import json
import glob
from pathlib import Path
from PIL import Image
import customtkinter as ctk

COLORS = {
    "bg": "#F5F6FA",
    "surface": "#FFFFFF",
    "border": "#E2E4E8",
    "primary": "#3B82F6",
    "primary_light": "#EFF6FF",
    "text": "#1F2937",
    "text_secondary": "#6B7280",
    "text_light": "#9CA3AF",
    "success": "#10B981",
}


class PosterGalleryWindow(ctk.CTkToplevel):
    """海报画廊窗口"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("🖼️ 海报画廊")
        self.geometry("1100x700")
        self.configure(fg_color=COLORS["bg"])
        self.transient(parent)
        self.grab_set()

        self.poster_dir = Path(
            os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")),
                         "literature_brief", "posters")
        )

        self._build_ui()
        self._load_sessions()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── 左侧目录树 ──
        left = ctk.CTkFrame(self, fg_color=COLORS["surface"], width=260, corner_radius=10)
        left.grid(row=0, column=0, sticky="nsw", padx=12, pady=12)
        left.grid_rowconfigure(1, weight=1)
        left.grid_propagate(False)

        ctk.CTkLabel(
            left, text="📂 检索记录",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(12, 8), sticky="w")

        self.session_list = ctk.CTkScrollableFrame(
            left, fg_color="transparent", width=230,
            scrollbar_button_color=COLORS["border"],
        )
        self.session_list.grid(row=1, column=0, padx=8, pady=(0, 12), sticky="nsew")

        # ── 右侧内容区 ──
        right = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 12), pady=12)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self.header_label = ctk.CTkLabel(
            right, text="选择一个检索主题查看海报",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(size=13),
        )
        self.header_label.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="w")

        # 海报网格滚动区
        self.poster_grid = ctk.CTkScrollableFrame(
            right, fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
        )
        self.poster_grid.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")

    def _load_sessions(self):
        """加载所有 session 记录"""
        session_files = sorted(
            glob.glob(str(self.poster_dir / "session_*.json")),
            key=os.path.getmtime,
            reverse=True,
        )

        if not session_files:
            ctk.CTkLabel(
                self.session_list,
                text="暂无海报记录",
                text_color=COLORS["text_light"],
                font=ctk.CTkFont(12),
            ).pack(pady=40)
            return

        for sf in session_files:
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            topic = data.get("topic", "未知主题")[:20]
            date = data.get("date", "")[:10]
            success_count = sum(1 for r in data.get("results", []) if r.get("success"))

            btn = ctk.CTkButton(
                self.session_list,
                text=f"{topic}\n{date}  ({success_count}张)",
                anchor="w",
                height=50,
                fg_color=COLORS["bg"],
                hover_color=COLORS["border"],
                text_color=COLORS["text"],
                font=ctk.CTkFont(11),
                command=lambda d=data, t=topic: self._show_session(d, t),
            )
            btn.pack(fill="x", pady=3, padx=4)

    def _show_session(self, data: dict, topic: str):
        """在右侧展示某个 session 下的所有海报"""
        for w in self.poster_grid.winfo_children():
            w.destroy()

        self.header_label.configure(
            text=f"🖼️ {topic}  —  {data.get('date', '')[:10]}",
            text_color=COLORS["text"],
            font=ctk.CTkFont(size=14, weight="bold"),
        )

        results = [r for r in data.get("results", []) if r.get("success") and os.path.exists(r.get("path", ""))]

        if not results:
            ctk.CTkLabel(
                self.poster_grid,
                text="该主题下没有成功生成的海报",
                text_color=COLORS["text_light"],
                font=ctk.CTkFont(13),
            ).pack(pady=80)
            return

        # 每行 3 张图
        for i, r in enumerate(results):
            row = i // 3
            col = i % 3

            card = PosterCard(self.poster_grid, r)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nw")


class PosterCard(ctk.CTkFrame):
    """单张海报缩略图卡片"""

    THUMB_W = 280
    THUMB_H = 500

    def __init__(self, parent, result: dict):
        super().__init__(parent, fg_color=COLORS["bg"], corner_radius=10, width=self.THUMB_W, height=self.THUMB_H + 40)
        self.result = result
        self.grid_propagate(False)

        path = result.get("path", "")
        title = result.get("title", "")[:30]

        # 缩略图
        try:
            img = Image.open(path)
            img.thumbnail((self.THUMB_W, self.THUMB_H))
            ctk_img = ctk.CTkImage(light_image=img, size=(img.width, img.height))
            self.img_label = ctk.CTkLabel(self, image=ctk_img, text="")
            self.img_label.image = ctk_img
        except Exception:
            self.img_label = ctk.CTkLabel(
                self, text="🖼️\n图片加载失败",
                text_color=COLORS["text_light"],
                font=ctk.CTkFont(size=24),
                width=self.THUMB_W, height=self.THUMB_H,
            )
        self.img_label.pack(pady=(8, 4))
        self.img_label.bind("<Button-1>", lambda e: self._open_full())

        # 标题
        ctk.CTkLabel(
            self, text=title,
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(10),
            wraplength=self.THUMB_W - 10,
        ).pack(pady=(0, 8))

    def _open_full(self):
        """打开大图查看"""
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.result.get("title", "海报")[:40])
        dialog.configure(fg_color=COLORS["bg"])
        dialog.geometry("800x1200")
        dialog.transient(self)

        try:
            img = Image.open(self.result["path"])
            # 限制最大显示尺寸
            max_w, max_h = 760, 1160
            img.thumbnail((max_w, max_h))
            ctk_img = ctk.CTkImage(light_image=img, size=(img.width, img.height))
            label = ctk.CTkLabel(dialog, image=ctk_img, text="")
            label.image = ctk_img
            label.pack(pady=20)
        except Exception as e:
            ctk.CTkLabel(dialog, text=f"加载失败: {e}", text_color=COLORS["error"]).pack(pady=100)

        ctk.CTkButton(
            dialog, text="关闭", width=100, command=dialog.destroy,
            fg_color=COLORS["primary"], text_color="white",
        ).pack(pady=12)
