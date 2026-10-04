"""
Fuel Optimization Service

Responsible for:
- Respecting the vehicle's maximum 500-mile range
- Finding reachable fuel stations along the route
- Prioritizing cost-effective fuel prices
- Minimizing route detours
- Calculating total fuel consumption
- Estimating total fuel cost

Vehicle assumptions:
- Maximum range: 500 miles
- Fuel efficiency: 10 MPG

The routing provider is called only once.
All fuel optimization is performed locally.
"""


from bisect import bisect_left
from math import radians, sin, cos, sqrt, atan2
from typing import Dict, List, Tuple

from .fuel_service import fuel_station_service


# ============================================================
# Vehicle Configuration
# ============================================================

VEHICLE_RANGE_MILES = 500
VEHICLE_MPG = 10

EARTH_RADIUS_MILES = 3958.8


# ============================================================
# Fuel Search Configuration
# ============================================================

# Keep a small safety margin below the absolute 500-mile limit.
MAX_REFUEL_TARGET_MILES = 490


# Normally we prefer not to stop too early.
PREFERRED_MIN_PROGRESS_MILES = 150


# If no station exists in the preferred window,
# search almost the complete reachable range.
FALLBACK_MIN_PROGRESS_MILES = 20


# Examine the route every 5 miles.
#
# Smaller interval:
# + More accurate
# + Better chance of finding stations
# - Slightly more local calculations
SEARCH_INTERVAL_MILES = 5


# Progressive search radius.
#
# The optimizer starts close to the route and expands
# only when no closer station exists.
DETOUR_SEARCH_LEVELS = (
    10,
    20,
    30,
    50,
    75,
    100,
    125,
    150,
    175,
    200,
    225,
    240,
)


# ============================================================
# Fuel Optimizer Service
# ============================================================


class FuelOptimizerService:
    """
    Finds a feasible and cost-effective sequence
    of fuel stops along a route.
    """

    def __init__(
        self,
        max_range: float = VEHICLE_RANGE_MILES,
        mpg: float = VEHICLE_MPG,
    ):
        self.max_range = max_range
        self.mpg = mpg

        self.tank_capacity_gallons = (
            self.max_range
            / self.mpg
        )


    # ========================================================
    # Main Optimization
    # ========================================================

    def optimize(
        self,
        route: Dict,
    ) -> Dict:
        """
        Find optimal fuel stops for the supplied route.

        Expected route format:

        {
            "distance": 1000.0,

            "geometry": {
                "type": "LineString",

                "coordinates": [
                    [longitude, latitude],
                    ...
                ]
            }
        }
        """

        # ----------------------------------------------------
        # Extract route information
        # ----------------------------------------------------

        total_distance = float(
            route["distance"]
        )


        coordinates = (
            route["geometry"]
            ["coordinates"]
        )


        # ----------------------------------------------------
        # Validate route
        # ----------------------------------------------------

        if total_distance <= 0:
            raise ValueError(
                "Route distance must be greater than zero."
            )


        if (
            not coordinates
            or len(coordinates) < 2
        ):
            raise ValueError(
                "Route geometry is invalid."
            )


        # ----------------------------------------------------
        # Calculate real cumulative distance along
        # the OSRM geometry.
        # ----------------------------------------------------

        cumulative_distances = (
            self._build_cumulative_distances(
                coordinates
            )
        )


        geometry_distance = (
            cumulative_distances[-1]
        )


        if geometry_distance <= 0:
            raise ValueError(
                "Unable to calculate route geometry distance."
            )


        # ----------------------------------------------------
        # OSRM road distance and Haversine geometry distance
        # may differ slightly.
        #
        # Scale geometry mileage so our checkpoints match
        # the OSRM route distance.
        # ----------------------------------------------------

        scale_factor = (
            total_distance
            / geometry_distance
        )


        cumulative_distances = [
            distance * scale_factor
            for distance in cumulative_distances
        ]


        # ----------------------------------------------------
        # Find fuel stops
        # ----------------------------------------------------

        selected_stops = (
            self._find_fuel_stops(
                coordinates=coordinates,
                cumulative_distances=cumulative_distances,
                total_distance=total_distance,
            )
        )


        # ----------------------------------------------------
        # Calculate fuel usage
        # ----------------------------------------------------

        fuel_needed_gallons = (
            total_distance
            / self.mpg
        )


        # ----------------------------------------------------
        # Calculate estimated trip cost
        # ----------------------------------------------------

        total_cost = (
            self._calculate_estimated_cost(
                total_gallons=fuel_needed_gallons,
                fuel_stops=selected_stops,
            )
        )


        # ----------------------------------------------------
        # Remove private optimization metadata
        # ----------------------------------------------------

        public_stops = []


        for stop in selected_stops:

            public_stops.append({

                "name":
                    stop["name"],

                "city":
                    stop["city"],

                "state":
                    stop["state"],

                "price":
                    round(
                        float(
                            stop["price"]
                        ),
                        3,
                    ),

                "latitude":
                    stop["latitude"],

                "longitude":
                    stop["longitude"],

                "distance_from_route":
                    round(
                        stop[
                            "distance_from_route"
                        ],
                        2,
                    ),
            })


        # ----------------------------------------------------
        # Final response
        # ----------------------------------------------------

        return {

            "fuel_stops":
                public_stops,

            "fuel_needed_gallons":
                round(
                    fuel_needed_gallons,
                    2,
                ),

            "total_cost":
                round(
                    total_cost,
                    2,
                ),
        }


    # ========================================================
    # Find All Required Fuel Stops
    # ========================================================

    def _find_fuel_stops(
        self,
        coordinates: List,
        cumulative_distances: List[float],
        total_distance: float,
    ) -> List[Dict]:
        """
        Continue selecting stations until the destination
        becomes reachable with one tank.

        No segment may exceed the 500-mile maximum range.
        """

        selected_stops = []

        current_mile = 0.0


        while (
            total_distance - current_mile
            > self.max_range
        ):

            station = (
                self._find_station_in_reachable_window(
                    coordinates=coordinates,
                    cumulative_distances=cumulative_distances,
                    current_mile=current_mile,
                    total_distance=total_distance,
                )
            )


            if station is None:

                raise ValueError(
                    "Unable to find a reachable fuel station "
                    f"between mile "
                    f"{round(current_mile, 1)} "
                    f"and mile "
                    f"{round(current_mile + self.max_range, 1)}."
                )


            if (
                station["_route_mile"]
                <= current_mile
            ):

                raise ValueError(
                    "Fuel optimization failed because "
                    "the selected station does not make "
                    "forward progress along the route."
                )


            selected_stops.append(
                station
            )


            current_mile = (
                station["_route_mile"]
            )


        return selected_stops


    # ========================================================
    # Search the Reachable Route Corridor
    # ========================================================

    def _find_station_in_reachable_window(
        self,
        coordinates: List,
        cumulative_distances: List[float],
        current_mile: float,
        total_distance: float,
    ):
        """
        Search the entire reachable route corridor.

        Search order:

        1. Prefer stations farther along the trip.
        2. Start with stations close to the route.
        3. Gradually expand the allowed detour.
        4. Fall back to earlier reachable stations.
        5. Reject stations that would exceed the vehicle range.
        """

        reachable_end = min(
            current_mile
            + MAX_REFUEL_TARGET_MILES,

            total_distance,
        )


        search_windows = [

            (
                current_mile
                + PREFERRED_MIN_PROGRESS_MILES,

                reachable_end,
            ),

            (
                current_mile
                + FALLBACK_MIN_PROGRESS_MILES,

                reachable_end,
            ),
        ]


        for (
            window_start,
            window_end,
        ) in search_windows:


            if (
                window_start
                >= window_end
            ):
                continue


            for detour_radius in DETOUR_SEARCH_LEVELS:

                candidates = {}

                checkpoint = (
                    window_start
                )


                while (
                    checkpoint
                    <= window_end
                ):

                    route_progress = (
                        checkpoint
                        - current_mile
                    )


                    maximum_feasible_detour = (

                        self.max_range
                        - route_progress

                    ) / 2


                    if (
                        maximum_feasible_detour
                        <= 0
                    ):

                        checkpoint += (
                            SEARCH_INTERVAL_MILES
                        )

                        continue


                    search_radius = min(
                        detour_radius,
                        maximum_feasible_detour,
                    )


                    if search_radius <= 0:

                        checkpoint += (
                            SEARCH_INTERVAL_MILES
                        )

                        continue


                    longitude, latitude = (
                        self._coordinate_at_distance(

                            coordinates=
                                coordinates,

                            cumulative_distances=
                                cumulative_distances,

                            target_distance=
                                checkpoint,
                        )
                    )


                    stations = (
                        fuel_station_service
                        .stations_within_radius(

                            latitude=
                                latitude,

                            longitude=
                                longitude,

                            radius_miles=
                                search_radius,
                        )
                    )


                    for station in stations:

                        station_detour = (
                            station[
                                "distance_from_route"
                            ]
                        )


                        estimated_detour = (
                            station_detour
                            * 2
                        )


                        estimated_leg_distance = (

                            route_progress

                            +

                            estimated_detour
                        )


                        if (
                            estimated_leg_distance
                            > self.max_range
                        ):

                            continue


                        station_key = (

                            round(
                                station[
                                    "latitude"
                                ],
                                5,
                            ),

                            round(
                                station[
                                    "longitude"
                                ],
                                5,
                            ),

                            station["name"],
                        )


                        candidate = {

                            **station,

                            "_route_mile":
                                checkpoint,

                            "_estimated_leg_distance":
                                estimated_leg_distance,
                        }


                        existing = (
                            candidates.get(
                                station_key
                            )
                        )


                        if (
                            existing is None

                            or

                            candidate[
                                "distance_from_route"
                            ]

                            <

                            existing[
                                "distance_from_route"
                            ]
                        ):

                            candidates[
                                station_key
                            ] = candidate


                    checkpoint += (
                        SEARCH_INTERVAL_MILES
                    )


                if candidates:

                    return (
                        self._select_best_station(

                            stations=list(
                                candidates.values()
                            ),

                            target_mile=
                                window_end,
                        )
                    )


        return None


    # ========================================================
    # Select Best Station
    # ========================================================

    @staticmethod
    def _select_best_station(
        stations: List[Dict],
        target_mile: float,
    ) -> Dict:
        """
        Select the most cost-effective fuel station.

        Priority:
        1. Lower fuel price
        2. Smaller detour
        3. Better forward progress

        Lower score = better station.
        """

        def score(
            station: Dict,
        ) -> float:

            price_score = (
                station["price"]
            )


            detour_penalty = (

                station[
                    "distance_from_route"
                ]

                * 0.008
            )


            miles_before_target = max(

                0,

                target_mile
                - station["_route_mile"],
            )


            progress_penalty = (
                miles_before_target
                * 0.002
            )


            return (

                price_score

                +

                detour_penalty

                +

                progress_penalty
            )


        return min(
            stations,
            key=score,
        )


    # ========================================================
    # Build Cumulative Route Distance
    # ========================================================

    def _build_cumulative_distances(
        self,
        coordinates: List,
    ) -> List[float]:
        """
        Calculate cumulative Haversine distance
        across all OSRM GeoJSON route points.
        """

        cumulative = [
            0.0
        ]


        for index in range(
            1,
            len(coordinates),
        ):

            previous = (
                coordinates[
                    index - 1
                ]
            )

            current = (
                coordinates[
                    index
                ]
            )


            segment_distance = (
                self._haversine_distance(

                    longitude1=
                        previous[0],

                    latitude1=
                        previous[1],

                    longitude2=
                        current[0],

                    latitude2=
                        current[1],
                )
            )


            cumulative.append(

                cumulative[-1]

                +

                segment_distance
            )


        return cumulative


    # ========================================================
    # Get Coordinate at Route Mileage
    # ========================================================

    @staticmethod
    def _coordinate_at_distance(
        coordinates: List,
        cumulative_distances: List[float],
        target_distance: float,
    ) -> Tuple[float, float]:
        """
        Return route coordinate closest to the requested
        route mileage.

        Binary search keeps this operation efficient.
        """

        index = bisect_left(
            cumulative_distances,
            target_distance,
        )


        if (
            index
            >= len(coordinates)
        ):

            index = (
                len(coordinates)
                - 1
            )


        longitude, latitude = (
            coordinates[index]
        )


        return (
            longitude,
            latitude,
        )


    # ========================================================
    # Haversine Distance
    # ========================================================

    @staticmethod
    def _haversine_distance(
        longitude1: float,
        latitude1: float,
        longitude2: float,
        latitude2: float,
    ) -> float:
        """
        Calculate straight-line geographical distance
        between two coordinates in miles.
        """

        lat1 = radians(
            latitude1
        )

        lat2 = radians(
            latitude2
        )

        lon1 = radians(
            longitude1
        )

        lon2 = radians(
            longitude2
        )


        delta_latitude = (
            lat2
            - lat1
        )

        delta_longitude = (
            lon2
            - lon1
        )


        a = (

            sin(
                delta_latitude / 2
            ) ** 2

            +

            cos(lat1)

            *

            cos(lat2)

            *

            sin(
                delta_longitude / 2
            ) ** 2
        )


        c = (
            2

            *

            atan2(
                sqrt(a),
                sqrt(1 - a),
            )
        )


        return (
            EARTH_RADIUS_MILES
            * c
        )


    # ========================================================
    # Fuel Cost Calculation
    # ========================================================

    def _calculate_estimated_cost(
        self,
        total_gallons: float,
        fuel_stops: List[Dict],
    ) -> float:
        """
        Estimate total fuel cost for the complete journey.

        Formula:

            fuel required =
                route distance / MPG

            total cost =
                total gallons × estimated fuel price

        Pricing strategy:

        1. If optimized fuel stops exist:
           use the average fuel price of those selected stops.

        2. If no fuel stop is required:
           use the average price from the supplied fuel-price
           dataset.

        This prevents short trips from incorrectly returning
        a total fuel cost of $0.
        """

        if total_gallons <= 0:
            return 0.0


        # ----------------------------------------------------
        # Route requires one or more optimized fuel stops
        # ----------------------------------------------------

        if fuel_stops:

            estimated_price = (

                sum(
                    station["price"]

                    for station
                    in fuel_stops
                )

                /

                len(
                    fuel_stops
                )
            )


        # ----------------------------------------------------
        # Route is shorter than the vehicle range.
        #
        # No mid-route stop is required, but fuel is still
        # consumed. Use the supplied dataset's average price
        # as the estimated fuel price.
        # ----------------------------------------------------

        else:

            estimated_price = (
                fuel_station_service
                .get_average_fuel_price()
            )


        return (
            total_gallons
            * estimated_price
        )


# ============================================================
# Shared Service Instance
# ============================================================


fuel_optimizer_service = (
    FuelOptimizerService()
)