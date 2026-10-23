"""Validated API request contracts, independent of route registration."""

from typing import Literal

from pydantic import BaseModel, Field


class ImportArticle(BaseModel):
    url: str = Field(max_length=2000)
    title: str = Field(default="", max_length=240)
    text: str = Field(default="", max_length=100000)


class Options(BaseModel):
    word_count: int = Field(default=1200, ge=300, le=6000)
    style: str = Field(default="专业、有观点、自然简洁", max_length=300)
    platform: Literal["wechat", "x", "xiaohongshu", "weibo"] = "wechat"
    provider: Literal["deepseek", "openrouter"] = "deepseek"
    research: bool = True
    related_urls: list[str] = Field(default_factory=list, max_length=4)
    revise: bool = False


class Edit(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(max_length=50000)
    summary: str = Field(max_length=400)
    keywords: list[str] = Field(max_length=12)
    revision: int


class Paragraph(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    revision: int
    instruction: str = Field(default="让表达更自然简洁，保留事实与来源", max_length=1000)
    provider: Literal["deepseek", "openrouter"] = "deepseek"


class Approval(BaseModel):
    approved: bool
    alt: str = Field(default="配图", max_length=240)


class StockQuery(BaseModel):
    query: str = Field(min_length=1, max_length=120)


class Publish(BaseModel):
    platforms: list[Literal["wechat", "x", "xiaohongshu", "weibo"]] = Field(
        min_length=1, max_length=4
    )


class WechatSettings(BaseModel):
    author: str = Field(default="", max_length=8)
    thumb_media_id: str = Field(default="", max_length=200)


class Settings(BaseModel):
    wechat: WechatSettings
