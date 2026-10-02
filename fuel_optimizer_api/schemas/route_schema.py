"""
Route Optimization Schemas

This module defines all request and response schemas
used by the Fuel Optimization API.

Schemas are responsible only for:

- Validating incoming data
- Documenting API structure
- Formatting API responses
"""


from typing import List

from ninja import Schema
from pydantic import Field



# ============================================================
# Location Schemas
# ============================================================


class LocationSchema(Schema):
    """
    Represents a geographical location.

    Used for:
    - Starting point
    - Destination point
    - Fuel station coordinates
    """


    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude coordinate"
    )


    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude coordinate"
    )



# ============================================================
# Route Request Schema
# ============================================================


class RouteRequestSchema(Schema):
    """
    Request body for route optimization.

    The user provides:

    - Starting location
    - Destination location

    The API calculates:

    - Driving route
    - Fuel stops
    - Total fuel cost
    """


    start: LocationSchema = Field(
        ...,
        description="Starting location of the trip"
    )


    finish: LocationSchema = Field(
        ...,
        description="Destination location of the trip"
    )



# ============================================================
# Fuel Stop Response Schema
# ============================================================


class FuelStopSchema(Schema):
    """
    Represents a recommended fuel station.

    Contains:

    - Station name
    - Location
    - Fuel price
    - Distance from route
    """


    name: str = Field(
        ...,
        description="Fuel station name"
    )


    city: str = Field(
        ...,
        description="City where station is located"
    )


    state: str = Field(
        ...,
        description="US state where station is located"
    )


    price: float = Field(
        ...,
        description="Fuel price per gallon"
    )


    latitude: float = Field(
        ...,
        description="Fuel station latitude"
    )


    longitude: float = Field(
        ...,
        description="Fuel station longitude"
    )


    distance_from_route: float = Field(
        ...,
        description="Distance from route in miles"
    )



# ============================================================
# GeoJSON Geometry Schema
# ============================================================


class GeometrySchema(Schema):
    """
    Simplified GeoJSON geometry response.
    """

    type: str

    coordinates: List[List[float]]


# ============================================================
# Route Optimization Response Schema
# ============================================================


class RouteResponseSchema(Schema):
    """
    Final API response returned after route optimization.
    """


    route_distance_miles: float = Field(
        ...,
        description="Total driving distance in miles"
    )


    fuel_needed_gallons: float = Field(
        ...,
        description="Total fuel required"
    )


    total_cost: float = Field(
        ...,
        description="Estimated total fuel cost"
    )


    fuel_stops: List[FuelStopSchema] = Field(
        ...,
        description="Recommended fuel stations"
    )
    """
    Final response returned after route optimization.

    Includes:

    - Total route distance
    - Required fuel
    - Estimated fuel cost
    - Recommended fuel stops
    - Route geometry for maps
    """


    route_distance_miles: float = Field(
        ...,
        description="Total driving distance in miles"
    )


    fuel_needed_gallons: float = Field(
        ...,
        description="Total fuel required based on vehicle MPG"
    )


    total_cost: float = Field(
        ...,
        description="Estimated total fuel cost"
    )


    fuel_stops: List[FuelStopSchema] = Field(
        ...,
        description="Recommended fuel stations along the route"
    )


    # geometry: GeometrySchema = Field(
    #     ...,
    #     description="GeoJSON route geometry used for map rendering"
    # )


    # ============================================================
# Error Response Schema
# ============================================================


class ErrorResponseSchema(Schema):
    """
    Standard API error response.
    """

    message: str = Field(
        ...,
        description="Human-readable error message"
    )

    code: str = Field(
        ...,
        description="Machine-readable error code"
    )