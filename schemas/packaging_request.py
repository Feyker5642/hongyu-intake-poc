"""詢價資料模型。對應 docs/DATA_SCHEMA.md；欄位沒提到一律 None，不猜。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Dimensions(BaseModel):
    length_mm: Optional[float] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    original_text: Optional[str] = None  # 防呆 3：換算後仍保留原文


class PackagingRequest(BaseModel):
    # A. 客戶與來源
    source_channel: Optional[str] = None
    company: Optional[str] = None
    contact_name: Optional[str] = None
    contact_info: Optional[str] = None
    raw_request: str = ""  # 永不覆寫

    # B. 產品與使用情境
    product_category: Optional[str] = None
    contents: Optional[str] = None
    purpose: Optional[str] = None
    product_dimensions: Optional[Dimensions] = None  # 內容物尺寸
    contents_weight_or_volume: Optional[str] = None
    storage_transport: Optional[str] = None

    # C. 包裝規格（與 B 的尺寸永遠分開——防呆 2）
    package_dimensions: Optional[Dimensions] = None
    dimensions_unclassified: Optional[Dimensions] = None  # 分不清歸屬時放這，標 ambiguous
    quantity: Optional[int] = None
    box_type: Optional[str] = None
    material_direction: Optional[str] = None
    paper_weight_gsm: Optional[int] = None
    lining: Optional[str] = None
    special_structure: Optional[str] = None

    # D. 印刷與加工
    print_method: Optional[str] = None
    print_sides: Optional[str] = None
    finishes: list[str] = Field(default_factory=list)
    artwork_status: Optional[str] = None
    proofing_needed: Optional[str] = None

    # E. 交付條件
    requested_delivery_date: Optional[str] = None  # ISO；不明確就 None
    delivery_date_original: Optional[str] = None   # 原文一律保留
    delivery_location: Optional[str] = None
    budget: Optional[str] = None
    preferences: list[str] = Field(default_factory=list)  # 「高級」「不要太貴」只能進這裡
    notes: Optional[str] = None


class Conflict(BaseModel):
    field: str
    values: list[str]
    evidence: str


class Ambiguity(BaseModel):
    field: str
    reason: str
    evidence: str


class SystemFields(BaseModel):
    """AI 可靠性欄位（DATA_SCHEMA F 節）。由 validator 決定，不信 LLM 單方。"""

    missing_fields: list[str] = Field(default_factory=list)
    ambiguous_fields: list[Ambiguity] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    evidence_by_field: dict[str, str] = Field(default_factory=dict)
    # 逐欄狀態，四值之一：已確認／AI抽取／不確定／未提供
    status_by_field: dict[str, str] = Field(default_factory=dict)
    risk_notes: list[str] = Field(default_factory=list)
    # 確認前恆為 True；只有 build_export 在人工確認後的匯出副本上翻成 False
    manual_review_required: bool = True
    data_completeness: str = "0/12"  # 形式固定為 已填/必填總數


class ParseResult(BaseModel):
    request: PackagingRequest
    system: SystemFields
    parser_mode: str = "offline_rules"  # offline_rules | openai
    parser_note: Optional[str] = None
