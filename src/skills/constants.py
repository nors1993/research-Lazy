"""Constants and shared configurations for skills."""

from __future__ import annotations

import re


# Supported document types
class DocType:
    PAPER = "PAPER"
    PATENT = "PATENT"
    ABSTRACT = "ABSTRACT"
    SURVEY = "SURVEY"
    PROPOSAL = "PROPOSAL"
    THESIS = "THESIS"


# Supported domains
class Domain:
    CS = "CS"  # Computer Science
    GEO = "GEO"  # Geography
    RS = "RS"  # Remote Sensing
    GEOL = "GEOL"  # Geology
    PHYS = "PHYS"  # Physics
    MATH = "MATH"  # Mathematics
    CHEM = "CHEM"  # Chemistry
    BIO = "BIO"  # Biology
    MED = "MED"  # Medicine
    ECON = "ECON"  # Economics
    ME = "ME"  # Mechanical Engineering
    EE = "EE"  # Electrical Engineering
    CHE = "CHE"  # Chemical Engineering
    ENV = "ENV"  # Environmental Science


# Skill names
class SkillName:
    PATENT_WRITING = "patent-writing"
    PAPER_WRITING = "paper-writing"
    DOCX_GENERATION = "docx"


# Supported languages
LANGUAGES = ["zh-CN", "en-US", "fr-FR", "ja-JP", "de-DE"]


# Patent document margins (CNIPA standard)
PATENT_MARGINS = {
    "top": 2.5,  # cm
    "bottom": 2.5,  # cm
    "left": 2.0,  # cm
    "right": 2.0,  # cm
}

# Paper document margins (academic standard)
PAPER_MARGINS = {
    "top": 2.54,  # cm
    "bottom": 2.54,  # cm
    "left": 2.54,  # cm
    "right": 2.54,  # cm
}

# Font settings
FONTS = {
    "chinese": {
        "body": "SimSun",  # 宋体
        "heading": "SimHei",  # 黑体
        "caption": "SimSun",
    },
    "english": {
        "body": "Times New Roman",
        "heading": "Arial",
        "caption": "Times New Roman",
    },
}

# Page sizes in centimeters
PAGE_SIZES = {
    "A4": {"width": 21.0, "height": 29.7},
    "Letter": {"width": 21.59, "height": 27.94},
}

# Patent section order (CNIPA standard)
PATENT_SECTIONS = [
    "title",  # 发明名称
    "abstract",  # 说明书摘要
    "claims",  # 权利要求书
    "technical_field",  # 技术领域
    "background",  # 背景技术
    "invention_content",  # 发明内容
    "detailed_description",  # 具体实施方式
]

# Paper section order (academic)
PAPER_SECTIONS = [
    "title",
    "abstract",
    "keywords",
    "introduction",
    "related_work",
    "methodology",
    "results",
    "discussion",
    "conclusion",
    "references",
    "appendix",
]

# AI pattern markers to remove
AI_PATTERNS_ZH = [
    "综上所述",
    "总而言之",
    "值得注意的是",
    "需要指出的是",
    "应当指出的是",
    "众所周知",
    "不难发现",
    "深入探讨",
    "画卷",
    "显而易见",
    "不容置疑",
]

AI_PATTERNS_EN = [
    "delve into",
    "it is important to note",
    "it should be noted",
    "it is worth mentioning",
    "to summarize",
    "in conclusion",
    "as discussed above",
    "notably",
    "significantly",
    "remarkably",
    "substantially",
]

# Similarity thresholds
SIMILARITY_THRESHOLDS = {
    "critical": 0.5,
    "high": 0.3,
    "medium": 0.15,
    "low": 0.1,
}

# Section-specific thresholds for papers
PAPER_SIMILARITY_THRESHOLDS = {
    "abstract": 0.1,
    "introduction": 0.2,
    "related_work": 0.3,
    "methodology": 0.15,
    "results": 0.1,
    "conclusion": 0.15,
}


def remove_ai_patterns(text: str, patterns: list[str]) -> str:
    if not text:
        return text

    result = text
    for pattern in patterns:
        result = result.replace(pattern, "")
        result = result.replace(pattern + "，", "")
        result = result.replace(pattern + "，", "")
        result = result.replace(pattern + ", ", "")
        result = result.replace(pattern + ". ", "")

    result = re.sub(r"\s+", " ", result)
    return result.strip()
