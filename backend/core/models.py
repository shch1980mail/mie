from typing import Literal, Optional

from pydantic import BaseModel, Field

Bias = Literal["bullish", "bearish", "neutral"]


class DataUnavailable(Exception):
    def __init__(self, msg: str, status: Optional[int] = None):
        super().__init__(msg)
        self.status = status


class BudgetExceeded(DataUnavailable):
    pass


class Target(BaseModel):
    price: float
    rr: float


class Signal(BaseModel):
    symbol: str
    name: str = ""
    asset_class: str
    timeframe: str
    candle_ts: str
    generated_at: str
    price: float
    atr: float
    bias: Bias
    score: float
    recommended: bool = False
    probability: Optional[float] = None
    probability_tp2: Optional[float] = None
    probability_source: str = "none"
    expectancy_r: Optional[float] = None
    levels: dict = Field(default_factory=dict)
    entry: Optional[dict] = None
    stop_loss: Optional[float] = None
    take_profits: list[Target] = Field(default_factory=list)
    rationale: dict = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    stale: bool = False
