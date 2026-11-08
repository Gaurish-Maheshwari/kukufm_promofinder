"""Request/response models for the API."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AnalyzeOptions(BaseModel):
    platform: Literal["any", "tiktok", "reels", "shorts"] = "any"
    top_k: Optional[int] = Field(default=None, ge=1, le=200)
    min_score: Optional[float] = Field(default=None, ge=0, le=100)
    max_per_episode: Optional[int] = Field(default=None, ge=1, le=20)
    enable_montages: Optional[bool] = None
    use_llm: bool = True
    llm_key: Optional[str] = Field(default=None, description="Session-only key; never stored or logged")
    llm_model: Optional[str] = None
    show_title: Optional[str] = None
    include_timeline: bool = False

    def overrides(self) -> dict:
        promo = {}
        if self.min_score is not None:
            promo["min_score"] = self.min_score
        if self.max_per_episode is not None:
            promo["max_per_episode"] = self.max_per_episode
        if self.enable_montages is not None:
            promo["enable_montages"] = self.enable_montages
        return {"promo": promo} if promo else {}


class PathRequest(BaseModel):
    path: str = "data/input"
    manual_path: Optional[str] = None
    options: AnalyzeOptions = AnalyzeOptions()


class SampleRequest(BaseModel):
    with_manual: bool = True
    options: AnalyzeOptions = AnalyzeOptions()


class Feedback(BaseModel):
    run_id: str
    promo_id: str
    verdict: Literal["accept", "reject", "adjust"]
    episode: Optional[int] = None
    start: Optional[float] = None
    end: Optional[float] = None
    note: Optional[str] = Field(default=None, max_length=1000)
    editor: Optional[str] = Field(default=None, max_length=80)


class KeyCheck(BaseModel):
    key: Optional[str] = None
    ping: bool = False
