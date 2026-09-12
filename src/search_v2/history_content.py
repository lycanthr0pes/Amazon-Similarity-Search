"""Bounded private display snapshots, independent of ranking and provider caches."""

import base64
import binascii
from io import BytesIO
from typing import Annotated, Literal
import unicodedata

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.search_v2.condition_language import ConditionExpression

Label = Annotated[str, StringConstraints(min_length=1, max_length=2000)]
ConditionId = Annotated[
    str, StringConstraints(pattern=r"^(?:visual-)?condition-(?:[0-9]{3}|price)$")
]


class HistoryContent(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )
    profile: Literal["history-content-v1"] = "history-content-v1"
    source_text: Label = Field(repr=False)
    condition_labels: dict[ConditionId, Label] = Field(max_length=32, repr=False)
    condition_review: tuple[ConditionExpression, ...] = Field(max_length=24, repr=False)

    @model_validator(mode="after")
    def validate_source(self):
        if not self.source_text.strip() or any(
            unicodedata.category(char).startswith("C") and char not in "\n\r\t"
            for char in self.source_text
        ):
            raise ValueError("Invalid history source")
        seen = set()
        for row in self.condition_review:
            span = (row.start, row.end)
            if (
                row.end <= row.start
                or row.end > len(self.source_text)
                or row.quote != self.source_text[row.start : row.end]
                or not row.target
                or len(row.target) > 2000
                or span in seen
                or row.reason
                not in {
                    "explicit_condition",
                    "permission",
                    "avoidance",
                    "preference_suffix",
                    "requirement_suffix",
                    "preference_prefix",
                    "requirement_prefix",
                }
            ):
                raise ValueError("Invalid history condition range")
            seen.add(span)
        return self

    def browser_fields(self):
        return {
            "historyContentAvailable": True,
            "input": self.source_text,
            "conditionLabels": dict(self.condition_labels),
            "conditionReview": [row.model_dump(mode="json") for row in self.condition_review],
        }


def validate_thumbnail(value):
    if value is None:
        return None
    prefix = "data:image/png;base64,"
    try:
        if not value.startswith(prefix) or len(value) > 180000:
            raise ValueError
        body = base64.b64decode(value[len(prefix) :], validate=True)
        if not 0 < len(body) <= 128 * 1024:
            raise ValueError
        with Image.open(BytesIO(body)) as image:
            if (
                image.format != "PNG"
                or image.mode != "RGB"
                or not (1 <= image.width <= 192 and 1 <= image.height <= 192)
                or getattr(image, "n_frames", 1) != 1
            ):
                raise ValueError
            image.verify()
    except (
        ValueError,
        OSError,
        binascii.Error,
        UnidentifiedImageError,
        Image.DecompressionBombError,
    ):
        raise ValueError("Invalid history thumbnail") from None
    return value
