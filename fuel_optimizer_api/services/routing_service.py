"""
Routing Service

Responsible for retrieving driving routes
from the external OSRM routing API.

OSRM provides:
- Route distance
- Route geometry
- Map visualization data


The service performs only one external API call
per request to keep response time low.
"""


from typing import Dict

import requests



# ============================================================
# Configuration
# ============================================================


OSRM_BASE_URL = (
    "https://router.project-osrm.org/"
    "route/v1/driving/"
)


REQUEST_TIMEOUT_SECONDS = 5


METERS_TO_MILES = 1609.34




# ============================================================
# Routing Service
# ============================================================


class RoutingService:
    """
    Handles communication with OSRM API.
    """



    def get_route(
        self,
        start_longitude: float,
        start_latitude: float,

        end_longitude: float,
        end_latitude: float

    ) -> Dict:
        """
        Retrieve the optimal driving route.

        Parameters:

        start_longitude:
            Starting point longitude

        start_latitude:
            Starting point latitude

        end_longitude:
            Destination longitude

        end_latitude:
            Destination latitude


        Returns:

        {
            distance: miles,
            geometry: GeoJSON
        }

        """



        # ----------------------------------------------------
        # Validate coordinates
        # ----------------------------------------------------

        self._validate_coordinates(
            start_latitude,
            start_longitude
        )


        self._validate_coordinates(
            end_latitude,
            end_longitude
        )



        # ----------------------------------------------------
        # Build OSRM request URL
        # ----------------------------------------------------

        url = (
            f"{OSRM_BASE_URL}"
            f"{start_longitude},{start_latitude};"
            f"{end_longitude},{end_latitude}"
            "?overview=full"
            "&geometries=geojson"
        )



        try:


            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT_SECONDS
            )


            response.raise_for_status()



        except requests.Timeout:

            raise Exception(
                "Routing service timeout"
            )



        except requests.RequestException as error:

            raise Exception(
                f"Routing API error: {error}"
            )



        # ----------------------------------------------------
        # Parse OSRM response
        # ----------------------------------------------------


        data = response.json()



        if (
            "routes" not in data
            or not data["routes"]
        ):

            raise ValueError(
                "No route found"
            )



        route = data["routes"][0]



        return {


            # Convert meters to miles

            "distance":
                round(
                    route["distance"]
                    /
                    METERS_TO_MILES,

                    2
                ),



            # GeoJSON LineString
            # Used directly by frontend maps

            "geometry":
                route["geometry"]

        }




    # --------------------------------------------------------
    # Coordinate validation
    # --------------------------------------------------------

    @staticmethod
    def _validate_coordinates(
        latitude: float,
        longitude: float
    ):
        """
        Validate geographical coordinates.
        """


        if not (
            -90 <= latitude <= 90
        ):

            raise ValueError(
                "Latitude must be between -90 and 90"
            )



        if not (
            -180 <= longitude <= 180
        ):

            raise ValueError(
                "Longitude must be between -180 and 180"
            )





# ============================================================
# Service instance
# ============================================================


routing_service = RoutingService()