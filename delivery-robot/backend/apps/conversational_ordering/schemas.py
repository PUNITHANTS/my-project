from pydantic import BaseModel, ConfigDict, Field


class SlotConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: float = Field(ge=0, le=1)
    quantity: float = Field(ge=0, le=1)
    customization: float = Field(ge=0, le=1)


class DraftLineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    menu_item_id: str | None
    mention: str
    quantity: int = Field(gt=0)
    customizations: list[str] = Field(default_factory=list)
    confidence: SlotConfidence


class ParsedOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DraftLineItem] = Field(default_factory=list)
    delivery_location: str | None
    confidence: float = Field(ge=0, le=1)
    delivery_location_confidence: float = Field(ge=0, le=1)
    clarification_needed: str | None = None
