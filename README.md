# 文献简报生成器

基于 AI 的学术文献简报自动生成工具。输入关键词搜索 arXiv 论文，自动筛选、打分，生成中文简报报告和学术海报。

## 功能

- **AI 搜索**：调用 LLM 自动多轮检索 arXiv，精准定位目标论文
- **智能筛选**：自动评分筛选，也支持手动选择和上传 PDF
- **简报生成**：基于筛选后的论文，调用 LLM 生成结构化的中文简报（Word 文档）
- **海报生成**：基于简报内容生成学术海报图片（支持豆包 Seedream 等图片模型）
- **提示词管理**：可自定义下载/上传/重置 5 类提示词模板

## 安装

### 从源码运行

```bash
# 1. 克隆项目
git clone https://github.com/zxx157461/literature_brief.git
cd literature_brief

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行
python main.py
```

### 打包版本

下载 Release 中的 `LiteratureBrief.zip`，解压后运行 `LiteratureBrief.exe` 即可（无需安装 Python）。

## 配置

首次运行后，程序会自动在用户目录下创建配置文件 `C:\Users\<用户名>\literature_brief\config.json`（macOS/Linux 下为 `~/literature_brief/config.json`）。

打开配置文件填入你的 API Key：

```json
{
  "sift": {
    "provider": "dashscope",
    "api_key": "你的阿里云 DashScope API Key",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3.6-plus"
  },
  "brief": {
    "provider": "dashscope",
    "api_key": "你的阿里云 DashScope API Key",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3.6-plus"
  },
  "poster_enabled": false,
  "poster": {
    "provider": "doubao",
    "api_key": "你的火山引擎 API Key",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "model": "doubao-seedream-5-0-260128"
  }
}
```

支持的 LLM 提供商：
- **DashScope**（阿里云）：通义千问系列模型
- **火山引擎 Ark**：豆包系列模型（文本 + 图片生成）
- **OpenAI 兼容接口**：任何兼容 OpenAI API 的服务

## 技术栈

- Python 3.10+
- customtkinter（GUI）
- python-docx（Word 报告生成）
- arXiv API（论文检索）

## 许可证

[PolyForm Noncommercial License 1.0.0](LICENSE) — 个人、学术、非商业用途免费使用。商业用途需单独授权，请联系 zxx157461（1574614059@qq.com）。
