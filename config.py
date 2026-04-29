"""
config.py - 配置管理
S1 - 配置文件
支持两个独立 LLM：筛选模型(sift) + 简报模型(brief)
"""
import json
import os
import ssl
import platform

# SSL context：跳过证书验证（解决国内网络 CERTIFICATE_VERIFY_FAILED）
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

# ========== 路径配置 ==========
if platform.system() == "Windows":
    BASE_DIR = os.path.join(os.environ["USERPROFILE"], "literature_brief")
else:
    BASE_DIR = os.path.expanduser("~/literature_brief")

DATA_DIR = os.path.join(BASE_DIR, "data")
PAPERS_DIR = os.path.join(DATA_DIR, "papers")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
POSTERS_DIR = os.path.join(DATA_DIR, "posters")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(POSTERS_DIR, exist_ok=True)


# ========== 默认配置 ==========
DEFAULT_CONFIG = {
    "screen_mode": "人工筛选",
    "brief_review_needed": False,
    "sift": {
        "provider": "openai",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "max_tokens": 2000,
        "temperature": 0.3,
        "timeout": 600,
    },
    "brief": {
        "provider": "openai",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "max_tokens": 2000,
        "temperature": 0.5,
        "timeout": 600,
    },

    # 兼容旧配置（单 LLM 时代）
    "llm_provider": "openai",
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o-mini",
    "max_tokens": 2000,
    "temperature": 0.3,

    # 搜索配置
    "max_results": 20,
    "default_sort": "relevance",

    # 筛选配置
    "auto_score_threshold": 0.6,
    "ai_search_max_turns": 5,
    "ai_search_consecutive_empty_stop": 5,
    "max_papers_to_review": 50,

    # Pi 服务器配置
    "pi_ip": "10.106.147.220",
    "pi_port": 5000,

    # 海报生成配置
    "poster_enabled": False,
    "poster": {
        "provider": "openai",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "doubao-seedream-4-0-250828",
        "max_tokens": 2000,
        "temperature": 0.5,
    },
}


def load_config() -> dict:
    """加载配置，不存在则创建默认配置"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 补充缺失的默认键
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        # 旧版配置迁移：如果没有 brief，用旧配置填充
        # 旧版配置迁移
        if "sift" not in cfg or not cfg["sift"]:
            cfg["sift"] = {
                "provider": cfg.get("llm_provider", "openai"),
                "api_key": cfg.get("api_key", ""),
                "base_url": cfg.get("base_url", "https://api.openai.com/v1"),
                "model": cfg.get("model", "gpt-4o-mini"),
                "max_tokens": cfg.get("max_tokens", 2000),
                "temperature": cfg.get("temperature", 0.3),
            }
        if "brief" not in cfg or not cfg["brief"]:
            cfg["brief"] = {
                "provider": cfg.get("llm_provider", "openai"),
                "api_key": cfg.get("api_key", ""),
                "base_url": cfg.get("base_url", "https://api.openai.com/v1"),
                "model": cfg.get("model", "gpt-4o-mini"),
                "max_tokens": 4000,
                "temperature": 0.5,
            }
        return cfg
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    """保存配置"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


# ========== 全局配置实例 ==========
cfg = load_config()
