"""
prompts_manager.py - 提示词管理器
管理四种提示词模板：检索AI / 文本简报 / 图片脚本 / 图片生成
支持读取、更新、重置为默认值，以及导出/导入 .txt 文件
"""
import os
from pathlib import Path
from config import BASE_DIR

PROMPTS_DIR = Path(BASE_DIR) / "prompts"
PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 默认提示词
# ============================================================

DEFAULT_SEARCH_AI_PROMPT = """你是一个专业的学术文献搜索 Agent。你的任务是根据用户的研究主题，通过调用 search_papers 工具找到最相关的论文。

## 核心规则
- 每轮搜索后，我会告诉你：本轮搜到多少篇、通过筛选多少篇、累计通过多少篇
- **停止条件（满足任一即可）：**
  1. 累计通过数 >= {TARGET_COUNT} 且你判断已经覆盖主要论文
  2. 连续 {CONSECUTIVE_EMPTY_STOP} 轮没有新论文通过（说明已穷尽）
  3. 你主动认为搜索结果足够，不需要继续
  4. 达到最大搜索轮数 {MAX_TURNS}
- 每次调用 max_results 建议不超过 {max_results}

## 搜索策略建议
- 第一轮可以稍宽泛，确保覆盖面
- 后续轮次根据未通过论文的原因调整策略
- 善用 arXiv 语法：ti:标题 abs:摘要 cat:分类
- 注意去重：已经搜到的论文 ID 我会记录，不会重复计入

## 注意
当你决定停止搜索时，直接回复"搜索完成"即可，不需要再调用工具。"""

DEFAULT_BRIEF_SYSTEM_PROMPT = """你是一位专业学术编辑，擅长将论文转化为清晰、深入、有洞见的科研导读。"""

DEFAULT_BRIEF_USER_TEMPLATE = """【任务】为以下论文撰写科研导读，严格按照示例的格式和语言风格输出。

【格式规范】
- 不使用 Markdown 标记（不用 ##、**、-、数字列表等）
- 每篇论文用 "序号 | 主题标题" 作为小标题，后面直接跟正文
- 正文全部用自然段落，首行不缩进，段间空一行
- 每段 3-5 句话，语言简洁有力，不重复
- 结尾列出 3 条具体研究趋势（用数字序号）

【示例】
===== 示例开始 =====
研究透视：活性物质的自组织行为 | Science

本次共筛选 5 篇论文，涵盖活性物质中的自组织、相变与集群行为等核心议题。

01 | 相变与自组织
近日，荷兰特文特大学 Yogesh Shelke 等人在 Science 发表研究，发现当长径比和面积分数突破临界值时，系统从无序的活性湍流转变为高度有序的集群相，并伴随巨型涡旋的形成。该工作为理解生物系统中的组织化运动提供了新的统计力学框架。

02 | 拓扑缺陷与集群行为
柏林自由大学研究组系统测量了活性湍流中拓扑缺陷的统计分布，发现缺陷密度与宏观流速呈幂律关系，且可通过调节粒子活性实现缺陷的定向输运，暗示拓扑缺陷可作为信息传递的载体。

总体来看，当前活性物质研究的核心趋势在于：
1. 从单纯描述现象转向建立统一的统计力学框架
2. 拓扑缺陷与几何约束的相互作用成为新的焦点
3. 微粒追踪和流动成像的结合为定量研究提供了可能
===== 示例结束 =====

【本次论文】
论文标题：{title}
作者：{authors}
arXiv：{arxiv_id}
提交日期：{submitted_date}
论文摘要：{abstract}

论文全文（部分）：
{full_text}

请严格按照上述示例的格式和语言风格，为这篇论文撰写科研导读。"""

DEFAULT_POSTER_SCRIPT_PROMPT = """你是一位专业的学术内容提炼专家。你的任务是将学术论文的核心内容结构化提取，供图片生成模型使用。

## 你的输出格式

严格返回以下 JSON（不要 markdown 代码块，不要其他文字）：
{
  "poster_title": "海报主标题（15字以内，英文，直接概括论文核心贡献）",
  "subtitle": "副标题（30字以内，补充说明方法或应用场景）",
  "core_findings": [
    "核心发现1（一句话，必须包含具体数据或定量结论）",
    "核心发现2",
    "核心发现3"
  ],
  "visual_description": "海报视觉内容描述（英文，100-200词）。只描述需要展示的实质内容：数据图的类型和含义、实验装置或方法的示意图、关键物理量的关系、理论模型的图示等。不描述配色和字体——这些由图片模型自行决定。",
  "figure_hints": ["论文中图X展示了XX相图，可作为核心视觉", "图Y的统计曲线展示了关键趋势"],
  "figure_selections": [0, 2]
}

## 原则

- 只提取论文中真实存在的内容，不虚构数据或图表
- visual_description 用英文，聚焦于"画什么"，不操心"怎么配色"
- figure_selections 是从参考图列表中选择的索引（0-based），选 1-2 张最能体现核心发现的图
- figure_hints 用中文，给图片模型提示这些参考图在海报中如何利用
- 核心发现必须包含具体信息，不能空洞"""

DEFAULT_POSTER_IMAGE_PROMPT = """Create a professional academic research poster with the following specifications:

## Format
- Portrait orientation (vertical layout)
- Suitable for academic conference display and printing
- Clean, professional, modern scientific aesthetic

## Layout Structure
1. **Title Section** (top 15%): Large, bold title with author line below
2. **Core Visual Area** (middle 40%): Main scientific figures, data visualizations, diagrams
3. **Findings Section** (next 30%): Key research findings with supporting visuals
4. **Conclusion Bar** (bottom 15%): Summary takeaway and references/qr code area

## Style Requirements
- High contrast for readability
- Modern sans-serif typography
- No cluttered text blocks - prioritize visual impact
- Data visualizations integrated naturally into the layout
- Professional color palette (avoid neon or garish colors)
- White or light background preferred for printing

## Content Integration
- Use the provided script content to populate each section
- If reference images are provided, incorporate their key visual elements
- Scale and position reference images appropriately within the layout
- Add visual hierarchy through size, color, and positioning"""

# ============================================================
# 注册表
# ============================================================

PROMPT_DEFINITIONS = {
    "search_ai": {
        "name": "检索AI提示词",
        "description": "控制 AI 搜索 Agent 的搜索策略和停止条件",
        "file": "search_ai.txt",
        "default": DEFAULT_SEARCH_AI_PROMPT,
    },
    "brief_text": {
        "name": "文本简报提示词",
        "description": "控制系统提示词（style）和用户消息模板",
        "file": "brief_system.txt",
        "default": DEFAULT_BRIEF_SYSTEM_PROMPT,
    },
    "brief_user_template": {
        "name": "文本简报用户模板",
        "description": "控制生成每篇论文解读时的用户消息格式（含 {title} 等占位符）",
        "file": "brief_user_template.txt",
        "default": DEFAULT_BRIEF_USER_TEMPLATE,
    },
    "poster_script": {
        "name": "图片脚本生成提示词",
        "description": "控制将论文提炼为海报脚本 JSON 的格式和风格",
        "file": "poster_script.txt",
        "default": DEFAULT_POSTER_SCRIPT_PROMPT,
    },
    "poster_image": {
        "name": "图片生成提示词",
        "description": "控制图片大模型生成学术海报的布局、风格和内容要求",
        "file": "poster_image.txt",
        "default": DEFAULT_POSTER_IMAGE_PROMPT,
    },
}


class PromptsManager:
    """提示词管理器单例"""

    def get(self, key: str) -> str:
        """获取提示词内容（从文件读取，文件不存在则自动创建默认文件）"""
        if key not in PROMPT_DEFINITIONS:
            raise KeyError(f"未知提示词类型: {key}")
        filepath = PROMPTS_DIR / PROMPT_DEFINITIONS[key]["file"]
        if filepath.exists():
            return filepath.read_text(encoding="utf-8")
        # 自动创建默认文件
        default_text = PROMPT_DEFINITIONS[key]["default"]
        filepath.write_text(default_text, encoding="utf-8")
        return default_text

    def update(self, key: str, content: str) -> None:
        """更新提示词内容（写入文件）"""
        if key not in PROMPT_DEFINITIONS:
            raise KeyError(f"未知提示词类型: {key}")
        filepath = PROMPTS_DIR / PROMPT_DEFINITIONS[key]["file"]
        filepath.write_text(content, encoding="utf-8")

    def reset(self, key: str) -> None:
        """重置为默认提示词"""
        if key not in PROMPT_DEFINITIONS:
            raise KeyError(f"未知提示词类型: {key}")
        filepath = PROMPTS_DIR / PROMPT_DEFINITIONS[key]["file"]
        filepath.write_text(PROMPT_DEFINITIONS[key]["default"], encoding="utf-8")

    def export_to(self, key: str, dest_path: str) -> None:
        """导出提示词到指定 .txt 文件"""
        content = self.get(key)
        Path(dest_path).write_text(content, encoding="utf-8")

    def import_from(self, key: str, src_path: str) -> None:
        """从 .txt 文件导入提示词"""
        content = Path(src_path).read_text(encoding="utf-8")
        self.update(key, content)

    def list_all(self) -> list[dict]:
        """列出所有提示词类型"""
        return [
            {
                "key": key,
                "name": info["name"],
                "description": info["description"],
                "file": str(PROMPTS_DIR / info["file"]),
            }
            for key, info in PROMPT_DEFINITIONS.items()
        ]


# 全局单例
prompts = PromptsManager()
