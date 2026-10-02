"""
Fuel Optimization API Routes

This module exposes the endpoint responsible for:
- Receiving start and finish coordinates
- Retrieving the driving route
- Optimizing fuel stops
- Returning the complete trip and fuel plan
"""

from ninja import Router

from ..schemas.route_schema import (
    RouteRequestSchema,
    RouteResponseSchema,
    ErrorResponseSchema,
)

from ..services.routing_service import routing_service
from ..services.optimizer import fuel_optimizer_service


# ============================================================
# Router Configuration
# ============================================================

router = Router(
    tags=["Fuel Optimization"]
)


# ============================================================
# Optimize Fuel Route
# ============================================================

@router.post(
    "/optimize-fuel",
    response={
        200: RouteResponseSchema,
        400: ErrorResponseSchema,
        500: ErrorResponseSchema,
    },
    summary="Calculate route and optimal fuel stops",
)
def optimize_route(
    request,
    payload: RouteRequestSchema,
):
    """
    Calculate a driving route and determine
    cost-effective fuel stops along the route.

    Vehicle assumptions:
    - Maximum range: 500 miles
    - Fuel efficiency: 10 MPG
    """

    try:

        # ----------------------------------------------------
        # Extract request locations
        # ----------------------------------------------------

        start_location = payload.start
        finish_location = payload.finish


        # ----------------------------------------------------
        # Retrieve route from OSRM
        #
        # Only one external routing API request is made.
        # ----------------------------------------------------

        route_data = routing_service.get_route(

            start_longitude=start_location.longitude,
            start_latitude=start_location.latitude,

            end_longitude=finish_location.longitude,
            end_latitude=finish_location.latitude,
        )


        # ----------------------------------------------------
        # Calculate fuel optimization locally
        # ----------------------------------------------------

        fuel_plan = fuel_optimizer_service.optimize(
            route_data
        )


        # ----------------------------------------------------
        # Build response
        # ----------------------------------------------------

        response_data = {

            "route_distance_miles": round(
                route_data["distance"],
                2,
            ),

            "geometry": route_data["geometry"],

            **fuel_plan,
        }


        return 200, response_data


    except ValueError as error:

        return 400, {
            "message": str(error),
            "code": "invalidRequest",
        }


    except Exception as error:

        return 500, {
            "message": str(error),
            "code": "internalServerError",
        }