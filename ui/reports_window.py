"""
reports_window.py - 简报管理界面
"""
import os
import glob as _glob_mod
from datetime import datetime
import customtkinter as ctk
from config import REPORTS_DIR

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


class ReportsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📄 简报管理")
        self.geometry("700x500")
        self.configure(fg_color=COLORS["bg"])
        self.transient(parent)
        self.grab_set()

        self.on_refresh_main = None

        self._build_widgets()
        self._load_reports()

    def _build_widgets(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ====== 顶部工具栏 ======
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["surface"], height=50)
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        toolbar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            toolbar,
            text="📁 已生成的文献简报",
            text_color=COLORS["text"],
            font=ctk.CTkFont(14, weight="bold"),
        ).grid(row=0, column=0, padx=(12, 8), pady=10, sticky="w")

        self.refresh_btn = ctk.CTkButton(
            toolbar,
            text="🔄 刷新",
            width=80, height=30,
            fg_color=COLORS["bg"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["text"],
            command=self._load_reports,
        )
        self.refresh_btn.grid(row=0, column=1, padx=4, pady=10, sticky="e")

        self.open_dir_btn = ctk.CTkButton(
            toolbar,
            text="📂 打开文件夹",
            width=100, height=30,
            fg_color=COLORS["primary_light"],
            text_color=COLORS["primary"],
            command=self._open_reports_dir,
        )
        self.open_dir_btn.grid(row=0, column=2, padx=(4, 12), pady=10, sticky="e")

        # ====== 简报列表 ======
        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["surface"],
            corner_radius=10,
        )
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=6)

        # ====== 底部状态栏 ======
        self.status_label = ctk.CTkLabel(
            self,
            text="",
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(11),
        )
        self.status_label.grid(row=2, column=0, padx=16, pady=8, sticky="w")

    def _load_reports(self):
        """加载简报列表"""
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        pattern = os.path.join(REPORTS_DIR, "*.docx")
        files = _glob_mod.glob(pattern)

        if not files:
            self._show_empty_state()
            self.status_label.configure(text="暂无简报")
            return

        # 按修改时间倒序排列
        files.sort(key=os.path.getmtime, reverse=True)

        for i, filepath in enumerate(files):
            ReportCard(
                self.list_frame,
                filepath,
                on_open=self._open_report,
                on_delete=self._delete_report,
            ).pack(fill="x", pady=3)

        self.status_label.configure(text=f"共 {len(files)} 份简报")

    def _show_empty_state(self):
        inner = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        inner.pack(pady=60)

        ctk.CTkLabel(
            inner, text="📭",
            font=ctk.CTkFont(size=36),
            text_color=COLORS["text_light"],
        ).pack()

        ctk.CTkLabel(
            inner, text="暂无生成的简报",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLORS["text"],
        ).pack(pady=(8, 4))

        ctk.CTkLabel(
            inner,
            text='搜索并选择论文后，点击"生成简报"即可创建',
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        ).pack()

    def _open_report(self, filepath: str):
        """打开简报文件"""
        try:
            os.startfile(filepath)
            self.status_label.configure(text=f"已打开: {os.path.basename(filepath)}")
        except Exception as e:
            self.status_label.configure(text=f"打开失败: {e}")

    def _delete_report(self, filepath: str):
        """删除简报文件"""
        filename = os.path.basename(filepath)
        # 确认对话框
        dialog = ctk.CTkToplevel(self)
        dialog.title("确认删除")
        dialog.geometry("320x120")
        dialog.configure(fg_color=COLORS["bg"])
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f"确定要删除 \"{filename}\" 吗？",
            text_color=COLORS["text"],
            font=ctk.CTkFont(12),
        ).pack(pady=(20, 10))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)

        def do_delete():
            try:
                os.remove(filepath)
                dialog.destroy()
                self._load_reports()
                self.status_label.configure(text=f"已删除: {filename}")
                if self.on_refresh_main:
                    self.on_refresh_main()
            except Exception as e:
                self.status_label.configure(text=f"删除失败: {e}")
                dialog.destroy()

        ctk.CTkButton(
            btn_frame,
            text="取消",
            width=80, height=32,
            fg_color=COLORS["bg"],
            text_color=COLORS["text"],
            command=dialog.destroy,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame,
            text="删除",
            width=80, height=32,
            fg_color=COLORS["error"],
            hover_color="#dc2626",
            command=do_delete,
        ).pack(side="left", padx=8)

    def _open_reports_dir(self):
        """打开简报所在文件夹"""
        try:
            os.startfile(REPORTS_DIR)
        except Exception as e:
            self.status_label.configure(text=f"打开文件夹失败: {e}")


class ReportCard(ctk.CTkFrame):
    def __init__(self, parent, filepath: str, on_open=None, on_delete=None):
        super().__init__(
            parent,
            fg_color=COLORS["bg"],
            corner_radius=8,
        )
        self.filepath = filepath
        self.on_open = on_open
        self.on_delete = on_delete

        filename = os.path.basename(filepath)
        mtime = os.path.getmtime(filepath)
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        size_kb = os.path.getsize(filepath) / 1024

        # 解析文件名获取主题和日期
        # 格式: 简报_{topic}_{date}.docx
        name_parts = filename.replace(".docx", "").split("_")
        if len(name_parts) >= 3:
            topic = name_parts[1] if name_parts[1] else "未知主题"
            date = name_parts[2] if len(name_parts) > 2 else ""
        else:
            topic = filename.replace(".docx", "")
            date = ""

        self.grid_columnconfigure(1, weight=1)

        # 图标
        ctk.CTkLabel(
            self,
            text="📄",
            font=ctk.CTkFont(size=24),
            width=40,
        ).grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=12, sticky="n")

        # 文件名/主题
        ctk.CTkLabel(
            self,
            text=topic[:50] + ("..." if len(topic) > 50 else ""),
            text_color=COLORS["text"],
            font=ctk.CTkFont(12, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, padx=(0, 8), pady=(10, 0), sticky="nw")

        # 元信息
        meta = f"{mtime_str}  ·  {size_kb:.0f} KB"
        if date:
            meta = f"{date}  ·  {mtime_str}  ·  {size_kb:.0f} KB"
        ctk.CTkLabel(
            self,
            text=meta,
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(10),
            anchor="w",
        ).grid(row=1, column=1, padx=(0, 8), pady=(0, 8), sticky="nw")

        # 按钮组
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=10, sticky="n")

        ctk.CTkButton(
            btn_frame,
            text="打开",
            width=60, height=28,
            fg_color=COLORS["primary"],
            hover_color="#2563EB",
            text_color="white",
            font=ctk.CTkFont(11),
            corner_radius=6,
            command=lambda: self.on_open and self.on_open(self.filepath),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_frame,
            text="删除",
            width=60, height=28,
            fg_color="transparent",
            hover_color=COLORS["error"],
            text_color=COLORS["text_secondary"],
            font=ctk.CTkFont(11),
            corner_radius=6,
            command=lambda: self.on_delete and self.on_delete(self.filepath),
        ).pack(side="left")


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    root = ctk.CTk()
    root.withdraw()
    win = ReportsWindow(root)
    root.mainloop()
