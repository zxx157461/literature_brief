"""
settings_window.py - 设置界面
白色主题版
3种筛选模式 + 独立人工复核设置
"""
import os
import customtkinter as ctk
from config import cfg, save_config

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

# 3种筛选模式
SCREEN_MODES = [
    "人工筛选",
    "openclaw筛选",
    "其他AI筛选",
]

MODE_DESCS = {
    "人工筛选":    "检索结果由您手动选择，选好后由简报模型生成简报（需配简报模型）",
    "openclaw筛选": "openclaw自动筛选论文，可选人工复核后由简报模型生成简报（需配简报模型）",
    "其他AI筛选":  "AI模型评分筛选论文，可选人工复核后生成简报（需配筛选模型 + 简报模型）",
}


def _llm_block(parent, title, color_label):
    """构建一套 LLM 配置块：Provider下拉 + Key + 地址 + 模型 + Token/Temp"""
    frame = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=10)
    frame.pack(fill="x", pady=(0, 10), ipady=6)

    ctk.CTkLabel(
        frame, text=f"{color_label} {title}", text_color=COLORS["text"],
        font=ctk.CTkFont(size=13, weight="bold"),
    ).pack(anchor="w", padx=16, pady=(8, 4))

    row1 = ctk.CTkFrame(frame, fg_color="transparent")
    row1.pack(fill="x", padx=16, pady=3)
    ctk.CTkLabel(row1, text="来源:", text_color=COLORS["text_secondary"], width=50, anchor="w").pack(side="left")
    provider_menu = ctk.CTkOptionMenu(
        row1, values=["OpenAI", "千问", "MiniMax", "本地模型", "自定义API"], width=130,
        fg_color=COLORS["bg"], dropdown_fg_color=COLORS["surface"], text_color=COLORS["text"],
    )
    provider_menu.pack(side="left")

    row2 = ctk.CTkFrame(frame, fg_color="transparent")
    row2.pack(fill="x", padx=16, pady=3)
    ctk.CTkLabel(row2, text="Key:", text_color=COLORS["text_secondary"], width=50, anchor="w").pack(side="left")
    api_key_entry = ctk.CTkEntry(row2, width=310, fg_color=COLORS["bg"])
    api_key_entry.pack(side="left")

    row3 = ctk.CTkFrame(frame, fg_color="transparent")
    row3.pack(fill="x", padx=16, pady=3)
    ctk.CTkLabel(row3, text="地址:", text_color=COLORS["text_secondary"], width=50, anchor="w").pack(side="left")
    base_url_entry = ctk.CTkEntry(row3, width=310, fg_color=COLORS["bg"])
    base_url_entry.pack(side="left")

    row4 = ctk.CTkFrame(frame, fg_color="transparent")
    row4.pack(fill="x", padx=16, pady=3)
    ctk.CTkLabel(row4, text="模型:", text_color=COLORS["text_secondary"], width=50, anchor="w").pack(side="left")
    model_entry = ctk.CTkEntry(row4, width=200, fg_color=COLORS["bg"])
    model_entry.pack(side="left")

    row5 = ctk.CTkFrame(frame, fg_color="transparent")
    row5.pack(fill="x", padx=16, pady=3)
    ctk.CTkLabel(row5, text="Token:", text_color=COLORS["text_secondary"], width=50, anchor="w").pack(side="left")
    max_tokens_entry = ctk.CTkEntry(row5, width=60, fg_color=COLORS["bg"])
    max_tokens_entry.pack(side="left")
    ctk.CTkLabel(row5, text="Temp:", text_color=COLORS["text_secondary"], width=36).pack(side="left", padx=(12, 0))
    temp_entry = ctk.CTkEntry(row5, width=50, fg_color=COLORS["bg"])
    temp_entry.pack(side="left")
    ctk.CTkLabel(row5, text="(0严谨/1创意)", text_color=COLORS["text_light"], font=ctk.CTkFont(size=10)).pack(side="left", padx=(6, 0))

    def _on_provider_change(value=None):
        """切换 provider 时自动填充默认地址和模型"""
        if value is None:
            value = provider_menu.get()
        defaults = {
            "OpenAI":  ("https://api.openai.com/v1", "gpt-4o-mini"),
            "千问":    ("https://dashscope.aliyuncs.com/compatible-mode/v1", "qwen-plus"),
            "MiniMax": ("https://api.minimaxi.com", "abab6.5-chat"),
            "本地模型": ("http://127.0.0.1:1234/v1", "qwen/qwen3.6-35b-a3b"),
            "自定义API": ("", ""),
        }
        url, model = defaults.get(value, ("", ""))
        # 切换 provider 时总是覆盖地址和模型
        base_url_entry.delete(0, "end")
        if url:
            base_url_entry.insert(0, url)
        model_entry.delete(0, "end")
        if model:
            model_entry.insert(0, model)
        # 本地模型自动填充默认 Key，非本地模型清空
        if value == "本地模型":
            api_key_entry.delete(0, "end")
            api_key_entry.insert(0, "lm-studio")
        elif value == "自定义API":
            pass  # 保留用户输入
        else:
            api_key_entry.delete(0, "end")

    provider_menu.configure(command=_on_provider_change)

    return {
        "frame": frame,
        "provider_menu": provider_menu,
        "api_key_entry": api_key_entry,
        "base_url_entry": base_url_entry,
        "model_entry": model_entry,
        "max_tokens_entry": max_tokens_entry,
        "temp_entry": temp_entry,
    }


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("⚙️ 设置")
        self.geometry("600x780")
        self.configure(fg_color=COLORS["bg"])
        self.transient(parent)
        self.grab_set()

        self.on_saved = None
        self._build_widgets()
        self._load_config()

    def _build_widgets(self):
        canvas = ctk.CTkScrollableFrame(self, fg_color="transparent")
        canvas.pack(fill="both", expand=True, padx=20, pady=15)

        # ===== 筛选模式 =====
        ctk.CTkLabel(
            canvas, text="🔎 筛选模式", text_color=COLORS["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(0, 8))

        mode_frame = ctk.CTkFrame(canvas, fg_color=COLORS["surface"], corner_radius=10)
        mode_frame.pack(fill="x", pady=(0, 12), ipady=10)

        row_mode = ctk.CTkFrame(mode_frame, fg_color="transparent")
        row_mode.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(row_mode, text="模式:", text_color=COLORS["text_secondary"], width=40, anchor="w").pack(side="left")
        self.mode_menu = ctk.CTkOptionMenu(
            row_mode, values=SCREEN_MODES, width=220,
            fg_color=COLORS["bg"], dropdown_fg_color=COLORS["surface"], text_color=COLORS["text"],
            command=self._on_mode_change,
        )
        self.mode_menu.pack(side="left")

        self.mode_desc_label = ctk.CTkLabel(
            mode_frame, text="",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
            wraplength=500, justify="left",
        )
        self.mode_desc_label.pack(anchor="w", padx=16, pady=(0, 4))

        # 人工复核（仅模式2/3显示）
        self.review_var = ctk.BooleanVar(value=False)
        self.review_checkbox = ctk.CTkCheckBox(
            mode_frame,
            text="需要人工复核（勾选：筛选后弹出复核窗口；不勾选：直接生成简报）",
            variable=self.review_var,
            fg_color=COLORS["primary"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(11),
        )

        # ===== 筛选模型（仅其他AI筛选时显示）=====
        self.ai_container = ctk.CTkFrame(canvas, fg_color="transparent")

        self._ai_title = ctk.CTkLabel(
            self.ai_container, text="🤖 筛选模型", text_color=COLORS["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self._ai_subtitle = ctk.CTkLabel(
            self.ai_container,
            text="AI 帮您筛选论文，打相关性分数",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
        )
        self.sift = _llm_block(self.ai_container, "筛选模型", "🔎")

        self.threshold_frame = ctk.CTkFrame(self.ai_container, fg_color=COLORS["surface"], corner_radius=10)
        row_thr = ctk.CTkFrame(self.threshold_frame, fg_color="transparent")
        row_thr.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(row_thr, text="AI筛选阈值:", text_color=COLORS["text_secondary"], width=70, anchor="w").pack(side="left")
        self.threshold_entry = ctk.CTkEntry(row_thr, width=60, fg_color=COLORS["bg"])
        self.threshold_entry.pack(side="left")
        ctk.CTkLabel(
            row_thr, text="高于此分直接收录（0~1）",
            text_color=COLORS["text_light"], font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=(8, 0))

        row_turns = ctk.CTkFrame(self.threshold_frame, fg_color="transparent")
        row_turns.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(row_turns, text="AI搜索最大轮数:", text_color=COLORS["text_secondary"], width=100, anchor="w").pack(side="left")
        self.max_turns_entry = ctk.CTkEntry(row_turns, width=60, fg_color=COLORS["bg"])
        self.max_turns_entry.pack(side="left")
        ctk.CTkLabel(
            row_turns, text="填 0 表示不限（一直搜到穷尽）",
            text_color=COLORS["text_light"], font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=(8, 0))

        row_empty = ctk.CTkFrame(self.threshold_frame, fg_color="transparent")
        row_empty.pack(fill="x", padx=16, pady=6)
        ctk.CTkLabel(row_empty, text="连续空轮停止:", text_color=COLORS["text_secondary"], width=100, anchor="w").pack(side="left")
        self.empty_stop_entry = ctk.CTkEntry(row_empty, width=60, fg_color=COLORS["bg"])
        self.empty_stop_entry.pack(side="left")
        ctk.CTkLabel(
            row_empty, text="连续几轮无新论文通过即停止，填 0 表示不启用",
            text_color=COLORS["text_light"], font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=(8, 0))

        # ===== 简报模型（非人工筛选模式时显示）=====
        self.brief_container = ctk.CTkFrame(canvas, fg_color="transparent")

        self._brief_title = ctk.CTkLabel(
            self.brief_container, text="📝 简报模型", text_color=COLORS["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self._brief_subtitle = ctk.CTkLabel(
            self.brief_container,
            text="多模态大模型生成图文并茂的文献简报",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
        )
        self.brief = _llm_block(self.brief_container, "简报模型", "📝")

        # ===== 海报生成设置 =====
        self.poster_container = ctk.CTkFrame(canvas, fg_color="transparent")

        ctk.CTkLabel(
            self.poster_container, text="🖼️ 海报生成", text_color=COLORS["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(8, 2))
        ctk.CTkLabel(
            self.poster_container,
            text="简报生成完成后，自动为每篇论文生成学术海报",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(0, 6))

        self.poster_enabled_var = ctk.BooleanVar(value=False)
        self.poster_enable_checkbox = ctk.CTkCheckBox(
            self.poster_container,
            text="生成简报后自动生成海报",
            variable=self.poster_enabled_var,
            fg_color=COLORS["primary"],
            text_color=COLORS["text"],
            font=ctk.CTkFont(11),
        )
        self.poster_enable_checkbox.pack(anchor="w", pady=(0, 8))

        self.poster = _llm_block(self.poster_container, "图片模型", "🖼️")
        self.poster["provider_menu"].configure(
            values=["OpenAI", "豆包"],
            command=lambda v=None: self._on_poster_provider_change(v),
        )

        # ===== 搜索设置 =====
        ctk.CTkLabel(
            canvas, text="🔍 搜索设置", text_color=COLORS["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(12, 8))

        search_frame = ctk.CTkFrame(canvas, fg_color=COLORS["surface"], corner_radius=10)
        search_frame.pack(fill="x", pady=(0, 15), ipady=8)
        row7 = ctk.CTkFrame(search_frame, fg_color="transparent")
        row7.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row7, text="最大结果数:", text_color=COLORS["text_secondary"], width=70, anchor="w").pack(side="left")
        self.max_results_entry = ctk.CTkEntry(row7, width=70, fg_color=COLORS["bg"])
        self.max_results_entry.pack(side="left")

        # ===== Pi 服务器 =====
        ctk.CTkLabel(
            canvas, text="🖥️ Pi 服务器", text_color=COLORS["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(12, 8))

        pi_frame = ctk.CTkFrame(canvas, fg_color=COLORS["surface"], corner_radius=10)
        pi_frame.pack(fill="x", pady=(0, 15), ipady=8)

        row_ip = ctk.CTkFrame(pi_frame, fg_color="transparent")
        row_ip.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_ip, text="Pi IP:", text_color=COLORS["text_secondary"], width=60, anchor="w").pack(side="left")
        self.pi_ip_entry = ctk.CTkEntry(row_ip, width=180, fg_color=COLORS["bg"])
        self.pi_ip_entry.pack(side="left")
        ctk.CTkLabel(row_ip, text="（如 10.106.147.220）", text_color=COLORS["text_light"], font=ctk.CTkFont(size=10)).pack(side="left", padx=(8, 0))

        row_port = ctk.CTkFrame(pi_frame, fg_color="transparent")
        row_port.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(row_port, text="端口:", text_color=COLORS["text_secondary"], width=60, anchor="w").pack(side="left")
        self.pi_port_entry = ctk.CTkEntry(row_port, width=80, fg_color=COLORS["bg"])
        self.pi_port_entry.pack(side="left")
        ctk.CTkLabel(row_port, text="（默认 5000）", text_color=COLORS["text_light"], font=ctk.CTkFont(size=10)).pack(side="left", padx=(8, 0))

        # ===== 提示词管理 =====
        self._build_prompt_section(canvas)

        # ===== 保存按钮 =====
        ctk.CTkButton(
            canvas, text="💾 保存设置", width=200, height=40,
            fg_color=COLORS["success"], hover_color="#0ea569",
            font=ctk.CTkFont(size=14, weight="bold"), command=self._save,
        ).pack(pady=(10, 0))

    def _build_prompt_section(self, parent):
        """构建提示词管理区域"""
        from prompts_manager import PROMPT_DEFINITIONS, prompts as pm
        from tkinter import filedialog

        section = ctk.CTkFrame(parent, fg_color="transparent")

        ctk.CTkLabel(
            section, text="📝 提示词管理", text_color=COLORS["text"],
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", pady=(12, 2))
        ctk.CTkLabel(
            section,
            text="下载提示词为 .txt 文件 → 修改 → 上传覆盖，或重置为默认",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=11),
        ).pack(anchor="w", pady=(0, 6))

        frame = ctk.CTkFrame(section, fg_color=COLORS["surface"], corner_radius=10)
        frame.pack(fill="x", pady=(0, 12), ipady=8)

        # 提示词类型选择
        row1 = ctk.CTkFrame(frame, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(row1, text="类型:", text_color=COLORS["text_secondary"], width=40, anchor="w").pack(side="left")
        prompt_keys = list(PROMPT_DEFINITIONS.keys())
        prompt_names = [PROMPT_DEFINITIONS[k]["name"] for k in prompt_keys]
        self.prompt_type_menu = ctk.CTkOptionMenu(
            row1, values=prompt_names, width=200,
            fg_color=COLORS["bg"], dropdown_fg_color=COLORS["surface"], text_color=COLORS["text"],
            command=self._on_prompt_type_change,
        )
        self.prompt_type_menu.pack(side="left")
        self._prompt_keys = prompt_keys

        # 描述文字
        self.prompt_desc_label = ctk.CTkLabel(
            frame, text="",
            text_color=COLORS["text_light"], font=ctk.CTkFont(size=10),
            wraplength=500, justify="left",
        )
        self.prompt_desc_label.pack(anchor="w", padx=16, pady=(0, 4))

        # 文件路径
        self.prompt_path_label = ctk.CTkLabel(
            frame, text="",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=9),
        )
        self.prompt_path_label.pack(anchor="w", padx=16, pady=(0, 6))

        # 按钮行
        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkButton(
            btn_row, text="⬇ 下载", width=80, height=30,
            fg_color=COLORS["primary"], hover_color="#2563EB",
            text_color="white", font=ctk.CTkFont(12),
            corner_radius=6,
            command=self._download_prompt,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="⬆ 上传", width=80, height=30,
            fg_color=COLORS["success"], hover_color="#0ea569",
            text_color="white", font=ctk.CTkFont(12),
            corner_radius=6,
            command=self._upload_prompt,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="🔄 重置", width=80, height=30,
            fg_color=COLORS["warning"], hover_color="#d97706",
            text_color="white", font=ctk.CTkFont(12),
            corner_radius=6,
            command=self._reset_prompt,
        ).pack(side="left")

        self.prompt_status_label = ctk.CTkLabel(
            btn_row, text="",
            text_color=COLORS["success"], font=ctk.CTkFont(10),
        )
        self.prompt_status_label.pack(side="left", padx=(12, 0))

        self._on_prompt_type_change(prompt_names[0])
        section.pack(fill="x")

    def _get_current_prompt_key(self) -> str:
        idx = self.prompt_type_menu.get()
        for k, v in zip(self._prompt_keys, self.prompt_type_menu.cget("values")):
            if v == self.prompt_type_menu.get():
                return k
        return self._prompt_keys[0]

    def _on_prompt_type_change(self, name):
        from prompts_manager import PROMPT_DEFINITIONS
        key = self._get_current_prompt_key()
        info = PROMPT_DEFINITIONS.get(key, {})
        self.prompt_desc_label.configure(text=info.get("description", ""))
        self.prompt_path_label.configure(text=f"文件: prompts/{info.get('file', '')}")
        self.prompt_status_label.configure(text="")

    def _download_prompt(self):
        from tkinter import filedialog
        from prompts_manager import prompts as pm, PROMPT_DEFINITIONS
        key = self._get_current_prompt_key()
        info = PROMPT_DEFINITIONS[key]
        default_name = info["file"]
        path = filedialog.asksaveasfilename(
            parent=self,
            title=f"导出 {info['name']}",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=default_name,
        )
        if not path:
            return
        try:
            pm.export_to(key, path)
            self.prompt_status_label.configure(
                text=f"已导出到 {os.path.basename(path)}",
                text_color=COLORS["success"],
            )
        except Exception as e:
            self.prompt_status_label.configure(
                text=f"导出失败: {e}",
                text_color=COLORS["error"],
            )

    def _upload_prompt(self):
        from tkinter import filedialog
        from prompts_manager import prompts as pm, PROMPT_DEFINITIONS
        key = self._get_current_prompt_key()
        info = PROMPT_DEFINITIONS[key]
        path = filedialog.askopenfilename(
            parent=self,
            title=f"导入 {info['name']}",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            pm.import_from(key, path)
            self.prompt_status_label.configure(
                text=f"已从 {os.path.basename(path)} 导入",
                text_color=COLORS["success"],
            )
        except Exception as e:
            self.prompt_status_label.configure(
                text=f"导入失败: {e}",
                text_color=COLORS["error"],
            )

    def _reset_prompt(self):
        from tkinter import messagebox
        from prompts_manager import prompts as pm, PROMPT_DEFINITIONS
        key = self._get_current_prompt_key()
        info = PROMPT_DEFINITIONS[key]
        ok = messagebox.askyesno(
            "确认重置",
            f"确定要将「{info['name']}」重置为默认提示词吗？\n\n当前自定义内容将被覆盖。",
            parent=self,
        )
        if not ok:
            return
        pm.reset(key)
        self.prompt_status_label.configure(
            text=f"已重置为默认",
            text_color=COLORS["success"],
        )

    def _load_config(self):
        provider_map = {"openai": "OpenAI", "dashscope": "千问", "minimax": "MiniMax", "local": "本地模型", "custom": "自定义API"}

        # 旧模式名迁移
        migration = {
            "纯手动（无需LLM）": "人工筛选",
            "哈基虾筛选（不复审）": "openclaw筛选",
            "哈基虾筛选（复审）": "openclaw筛选",
            "哈基虾筛选": "openclaw筛选",
            "openclaw筛选": "openclaw筛选",
            "人工筛选": "人工筛选",
            "其他AI筛选": "其他AI筛选",
        }
        mode = migration.get(cfg.get("screen_mode", "人工筛选"), "人工筛选")
        if mode not in SCREEN_MODES:
            mode = "人工筛选"
        self.mode_menu.set(mode)

        fallback = {
            "provider": "openai", "api_key": "", "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o-mini", "max_tokens": 2000, "temperature": 0.3,
        }

        sift_cfg = cfg.get("sift") or fallback
        self.sift["provider_menu"].set(provider_map.get(sift_cfg.get("provider", "openai"), "OpenAI"))
        self.sift["api_key_entry"].delete(0, "end")
        self.sift["api_key_entry"].insert(0, sift_cfg.get("api_key", ""))
        self.sift["base_url_entry"].delete(0, "end")
        self.sift["base_url_entry"].insert(0, sift_cfg.get("base_url", "https://api.openai.com/v1"))
        self.sift["model_entry"].delete(0, "end")
        self.sift["model_entry"].insert(0, sift_cfg.get("model", "gpt-4o-mini"))
        self.sift["max_tokens_entry"].delete(0, "end")
        self.sift["max_tokens_entry"].insert(0, str(sift_cfg.get("max_tokens", 2000)))
        self.sift["temp_entry"].delete(0, "end")
        self.sift["temp_entry"].insert(0, str(sift_cfg.get("temperature", 0.3)))

        self.threshold_entry.delete(0, "end")
        self.threshold_entry.insert(0, str(cfg.get("auto_score_threshold", 0.6)))

        self.max_turns_entry.delete(0, "end")
        self.max_turns_entry.insert(0, str(cfg.get("ai_search_max_turns", 5)))

        self.empty_stop_entry.delete(0, "end")
        self.empty_stop_entry.insert(0, str(cfg.get("ai_search_consecutive_empty_stop", 5)))

        brief_cfg = cfg.get("brief") or fallback
        self.brief["provider_menu"].set(provider_map.get(brief_cfg.get("provider", "openai"), "OpenAI"))
        self.brief["api_key_entry"].delete(0, "end")
        self.brief["api_key_entry"].insert(0, brief_cfg.get("api_key", ""))
        self.brief["base_url_entry"].delete(0, "end")
        self.brief["base_url_entry"].insert(0, brief_cfg.get("base_url", "https://api.openai.com/v1"))
        self.brief["model_entry"].delete(0, "end")
        self.brief["model_entry"].insert(0, brief_cfg.get("model", "gpt-4o-mini"))
        self.brief["max_tokens_entry"].delete(0, "end")
        self.brief["max_tokens_entry"].insert(0, str(brief_cfg.get("max_tokens", 2000)))
        self.brief["temp_entry"].delete(0, "end")
        self.brief["temp_entry"].insert(0, str(brief_cfg.get("temperature", 0.5)))

        self.review_var.set(cfg.get("brief_review_needed", False))

        self.max_results_entry.delete(0, "end")
        self.max_results_entry.insert(0, str(cfg.get("max_results", 20)))

        # 海报设置加载
        self.poster_enabled_var.set(cfg.get("poster_enabled", False))
        poster_cfg = cfg.get("poster") or {}
        poster_provider_map = {"openai": "OpenAI", "doubao": "豆包"}
        self.poster["provider_menu"].set(poster_provider_map.get(poster_cfg.get("provider", "openai"), "OpenAI"))
        self.poster["api_key_entry"].delete(0, "end")
        self.poster["api_key_entry"].insert(0, poster_cfg.get("api_key", ""))
        self.poster["base_url_entry"].delete(0, "end")
        self.poster["base_url_entry"].insert(0, poster_cfg.get("base_url", "https://api.openai.com/v1"))
        self.poster["model_entry"].delete(0, "end")
        self.poster["model_entry"].insert(0, poster_cfg.get("model", "dall-e-3"))
        self.poster["max_tokens_entry"].delete(0, "end")
        self.poster["max_tokens_entry"].insert(0, str(poster_cfg.get("max_tokens", 2000)))
        self.poster["temp_entry"].delete(0, "end")
        self.poster["temp_entry"].insert(0, str(poster_cfg.get("temperature", 0.5)))
        self._on_poster_provider_change(self.poster["provider_menu"].get())

        self.pi_ip_entry.delete(0, "end")
        self.pi_ip_entry.insert(0, cfg.get("pi_ip", "10.106.147.220"))
        self.pi_port_entry.delete(0, "end")
        self.pi_port_entry.insert(0, str(cfg.get("pi_port", 5000)))

        self._on_mode_change(mode)

    def _on_mode_change(self, mode=None):
        if mode is None:
            mode = self.mode_menu.get()
        self.mode_desc_label.configure(text=MODE_DESCS.get(mode, ""))

        # 隐藏所有动态区域（含容器本身）
        self.review_checkbox.pack_forget()
        self.ai_container.pack_forget()
        self.brief_container.pack_forget()
        self.poster_container.pack_forget()

        if mode == "人工筛选":
            self.brief_container.pack(fill="x", pady=0)
            self._brief_title.pack(anchor="w", pady=(8, 2))
            self._brief_subtitle.pack(anchor="w", pady=(0, 6))
            self.brief["frame"].pack(fill="x", pady=(0, 10), ipady=6)
            self.poster_container.pack(fill="x", pady=0)

        elif mode == "openclaw筛选":
            self.review_checkbox.pack(anchor="w", padx=16, pady=(4, 8))
            self.brief_container.pack(fill="x", pady=0)
            self._brief_title.pack(anchor="w", pady=(8, 2))
            self._brief_subtitle.pack(anchor="w", pady=(0, 6))
            self.brief["frame"].pack(fill="x", pady=(0, 10), ipady=6)
            self.poster_container.pack(fill="x", pady=0)

        elif mode == "其他AI筛选":
            self.review_checkbox.pack(anchor="w", padx=16, pady=(4, 8))
            self.ai_container.pack(fill="x", pady=0)
            self._ai_title.pack(anchor="w", pady=(8, 2))
            self._ai_subtitle.pack(anchor="w", pady=(0, 6))
            self.sift["frame"].pack(fill="x", pady=(0, 6), ipady=6)
            self.threshold_frame.pack(fill="x", pady=(0, 12), ipady=8)
            self.brief_container.pack(fill="x", pady=0)
            self._brief_title.pack(anchor="w", pady=(8, 2))
            self._brief_subtitle.pack(anchor="w", pady=(0, 6))
            self.brief["frame"].pack(fill="x", pady=(0, 10), ipady=6)
            self.poster_container.pack(fill="x", pady=0)

        self.update()

    def _on_poster_provider_change(self, value=None):
        """切换海报模型 provider 时自动填充默认地址和模型"""
        if value is None:
            value = self.poster["provider_menu"].get()
        defaults = {
            "OpenAI":  ("https://api.openai.com/v1", "dall-e-3"),
            "豆包":    ("https://ark.cn-beijing.volces.com/api/v3", "doubao-image-xl"),
        }
        url, model = defaults.get(value, ("", ""))
        self.poster["base_url_entry"].delete(0, "end")
        if url:
            self.poster["base_url_entry"].insert(0, url)
        self.poster["model_entry"].delete(0, "end")
        if model:
            self.poster["model_entry"].insert(0, model)

    def _save(self):
        provider_map_rev = {"OpenAI": "openai", "千问": "dashscope", "MiniMax": "minimax", "本地模型": "local", "自定义API": "custom"}

        mode = self.mode_menu.get()
        cfg["screen_mode"] = mode
        cfg["brief_review_needed"] = self.review_var.get()

        if mode == "其他AI筛选":
            sift_key = self.sift["api_key_entry"].get()
            if any(ord(c) > 127 for c in sift_key):
                ctk.CTkMessageDialog(self, "筛选模型 API Key 包含非法字符，请重新输入纯 ASCII 的 key。", title="警告")
                return
            cfg["sift"] = {
                "provider": provider_map_rev.get(self.sift["provider_menu"].get(), "openai"),
                "api_key": self.sift["api_key_entry"].get(),
                "base_url": self.sift["base_url_entry"].get(),
                "model": self.sift["model_entry"].get(),
                "max_tokens": int(self.sift["max_tokens_entry"].get() or 2000),
                "temperature": float(self.sift["temp_entry"].get() or 0.3),
            }
            cfg["auto_score_threshold"] = float(self.threshold_entry.get() or 0.6)
            try:
                cfg["ai_search_max_turns"] = max(0, int(self.max_turns_entry.get() or 5))
            except ValueError:
                cfg["ai_search_max_turns"] = 5
            try:
                cfg["ai_search_consecutive_empty_stop"] = max(0, int(self.empty_stop_entry.get() or 5))
            except ValueError:
                cfg["ai_search_consecutive_empty_stop"] = 5

        # 所有模式都需要保存简报模型配置
        brief_key = self.brief["api_key_entry"].get()
        if any(ord(c) > 127 for c in brief_key):
            ctk.CTkMessageDialog(self, "API Key 包含非法字符，请重新输入纯 ASCII 的 key。", title="警告")
            return
        cfg["brief"] = {
            "provider": provider_map_rev.get(self.brief["provider_menu"].get(), "openai"),
            "api_key": self.brief["api_key_entry"].get(),
            "base_url": self.brief["base_url_entry"].get(),
            "model": self.brief["model_entry"].get(),
            "max_tokens": int(self.brief["max_tokens_entry"].get() or 2000),
            "temperature": float(self.brief["temp_entry"].get() or 0.5),
        }

        # 海报配置
        poster_provider_rev = {"OpenAI": "openai", "豆包": "doubao"}
        cfg["poster_enabled"] = self.poster_enabled_var.get()
        cfg["poster"] = {
            "provider": poster_provider_rev.get(self.poster["provider_menu"].get(), "openai"),
            "api_key": self.poster["api_key_entry"].get(),
            "base_url": self.poster["base_url_entry"].get(),
            "model": self.poster["model_entry"].get(),
            "max_tokens": int(self.poster["max_tokens_entry"].get() or 2000),
            "temperature": float(self.poster["temp_entry"].get() or 0.5),
        }

        cfg["max_results"] = int(self.max_results_entry.get() or 20)
        cfg["pi_ip"] = self.pi_ip_entry.get().strip()
        cfg["pi_port"] = int(self.pi_port_entry.get().strip() or 5000)

        save_config(cfg)
        if self.on_saved:
            self.on_saved(cfg)
        self.destroy()

