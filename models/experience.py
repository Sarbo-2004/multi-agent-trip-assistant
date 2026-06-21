from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Attraction(BaseModel):
    """A recommended attraction or activity."""

    name: str = Field(
        ...,
        description="Name of the attraction",
    )

    category: Literal[
        "culture",
        "nature",
        "food",
        "adventure",
        "shopping",
        "nightlife",
        "other",
    ] = Field(
        ...,
        description="Type of attraction",
    )

    rating: float | None = Field(
        default=None,
        ge=0,
        le=5,
        description="User rating if available",
    )

    latitude: float = Field(
        ...,
        description="Latitude of the attraction",
    )

    longitude: float = Field(
        ...,
        description="Longitude of the attraction",
    )

    address: str | None = Field(
        default=None,
        description="Location of the attraction",
    )

    description: str | None = Field(
        default=None,
        description="Short description",
    )

    website: Optional[str] = Field(
        default=None,
        description="Official website of the attraction, if available",
    )

    city: str | None = Field(
        default=None,
        description="City this attraction belongs to (for multi-location trips)",
    )


class Experience(BaseModel):
    city: str = Field(...)

    country: str = Field(...)

    cities: List[str] = Field(
        default_factory=list,
        description="Selected cities for multi-location trips",
    )

    vibe_score: int = Field(
        ...,
        ge=1,
        le=10,
    )

    attractions: List[Attraction] = Field(
        default_factory=list,
    )

    notes: str | None = Field(
        default=None,
    )