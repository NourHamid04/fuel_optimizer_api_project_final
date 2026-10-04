"""
Fuel Station Search Service

Responsible for:

- Loading processed fuel station data
- Building a BallTree spatial index
- Finding nearest fuel stations
- Finding all fuel stations within a specified radius

The CSV is loaded once when Django starts, which avoids
re-reading and rebuilding the spatial index for every request.
"""


import os
from typing import Dict, List

import numpy as np
import pandas as pd

from sklearn.neighbors import BallTree


# ============================================================
# Constants
# ============================================================


# Average Earth radius in miles.
# Used to convert Haversine angular distances into miles.
EARTH_RADIUS_MILES = 3958.8


# Default number of stations returned by nearest-neighbor search.
DEFAULT_STATION_LIMIT = 10


# ============================================================
# Fuel Station Service
# ============================================================


class FuelStationService:
    """
    Provides fast spatial searches over the fuel station dataset.

    BallTree is built only once when Django imports this module.
    """

    def __init__(self):

        # Load and validate dataset.
        self.fuel_data = (
            self._load_fuel_data()
        )

        # Build spatial search tree.
        self.search_tree = (
            self._build_spatial_tree()
        )


    # ========================================================
    # Load Dataset
    # ========================================================

    def _load_fuel_data(
        self,
    ) -> pd.DataFrame:
        """
        Load the processed fuel station CSV.

        Required columns:

        - name
        - city
        - state
        - price
        - latitude
        - longitude
        """

        base_dir = os.path.dirname(
            os.path.dirname(__file__)
        )


        csv_path = os.path.join(
            base_dir,
            "data",
            "fuel-prices-processed.csv",
        )


        if not os.path.exists(
            csv_path
        ):
            raise FileNotFoundError(
                f"Fuel price dataset was not found: {csv_path}"
            )


        fuel_data = pd.read_csv(
            csv_path
        )


        # ----------------------------------------------------
        # Validate required columns
        # ----------------------------------------------------

        required_columns = {
            "name",
            "city",
            "state",
            "price",
            "latitude",
            "longitude",
        }


        missing_columns = (
            required_columns
            - set(fuel_data.columns)
        )


        if missing_columns:
            raise ValueError(
                "Fuel dataset is missing required columns: "
                f"{missing_columns}"
            )


        # ----------------------------------------------------
        # Clean text fields
        #
        # Removes trailing/leading whitespace such as:
        #
        # "Page                        "
        #
        # becoming:
        #
        # "Page"
        # ----------------------------------------------------

        fuel_data["name"] = (
            fuel_data["name"]
            .astype(str)
            .str.strip()
        )


        fuel_data["city"] = (
            fuel_data["city"]
            .astype(str)
            .str.strip()
        )


        fuel_data["state"] = (
            fuel_data["state"]
            .astype(str)
            .str.strip()
        )


        # ----------------------------------------------------
        # Convert numerical values safely
        # ----------------------------------------------------

        fuel_data["price"] = (
            pd.to_numeric(
                fuel_data["price"],
                errors="coerce",
            )
        )


        fuel_data["latitude"] = (
            pd.to_numeric(
                fuel_data["latitude"],
                errors="coerce",
            )
        )


        fuel_data["longitude"] = (
            pd.to_numeric(
                fuel_data["longitude"],
                errors="coerce",
            )
        )


        # Remove invalid records.
        fuel_data = (
            fuel_data.dropna(
                subset=[
                    "price",
                    "latitude",
                    "longitude",
                ]
            )
            .reset_index(
                drop=True
            )
        )


        if fuel_data.empty:
            raise ValueError(
                "Fuel station dataset contains no valid records."
            )


        return fuel_data


    # ========================================================
    # Build Spatial Index
    # ========================================================

    def _build_spatial_tree(
        self,
    ) -> BallTree:
        """
        Build BallTree using latitude and longitude.

        Haversine metric requires coordinates to be expressed
        in radians.
        """

        coordinates = np.radians(
            self.fuel_data[
                [
                    "latitude",
                    "longitude",
                ]
            ].to_numpy()
        )


        return BallTree(
            coordinates,
            metric="haversine",
        )


    # ========================================================
    # Validate Coordinates
    # ========================================================

    @staticmethod
    def _validate_coordinates(
        latitude: float,
        longitude: float,
    ) -> None:
        """
        Ensure latitude and longitude are valid.
        """

        if not -90 <= latitude <= 90:
            raise ValueError(
                "Latitude must be between -90 and 90."
            )


        if not -180 <= longitude <= 180:
            raise ValueError(
                "Longitude must be between -180 and 180."
            )


    # ========================================================
    # Convert DataFrame Row to Response Dictionary
    # ========================================================

    @staticmethod
    def _station_to_dict(
        station,
        distance_miles: float,
    ) -> Dict:
        """
        Convert one station row into the format expected
        by the optimizer and API response.
        """

        return {

            "name":
                str(
                    station["name"]
                ),

            "city":
                str(
                    station["city"]
                ),

            "state":
                str(
                    station["state"]
                ),

            "price":
                float(
                    station["price"]
                ),

            "latitude":
                float(
                    station["latitude"]
                ),

            "longitude":
                float(
                    station["longitude"]
                ),

            "distance_from_route":
                round(
                    distance_miles,
                    2,
                ),
        }


    # ========================================================
    # Nearest-Neighbor Search
    # ========================================================

    def nearest_stations(
        self,
        latitude: float,
        longitude: float,
        limit: int = DEFAULT_STATION_LIMIT,
    ) -> List[Dict]:
        """
        Return the nearest fuel stations to a coordinate.

        Results are ordered from nearest to farthest.
        """

        self._validate_coordinates(
            latitude,
            longitude,
        )


        if limit <= 0:
            raise ValueError(
                "Station search limit must be greater than zero."
            )


        # Cannot ask BallTree for more rows than exist.
        limit = min(
            limit,
            len(self.fuel_data),
        )


        search_point = np.radians(
            [
                [
                    latitude,
                    longitude,
                ]
            ]
        )


        distances, indexes = (
            self.search_tree.query(
                search_point,
                k=limit,
            )
        )


        stations = []


        for distance, index in zip(
            distances[0],
            indexes[0],
        ):

            station = (
                self.fuel_data.iloc[
                    index
                ]
            )


            distance_miles = (
                float(distance)
                * EARTH_RADIUS_MILES
            )


            stations.append(
                self._station_to_dict(
                    station,
                    distance_miles,
                )
            )


        return stations


    # ========================================================
    # Radius Search
    # ========================================================

    def stations_within_radius(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float,
    ) -> List[Dict]:
        """
        Return all fuel stations within the provided radius.

        This is used by the optimizer when searching an entire
        reachable route corridor instead of only the nearest
        fixed number of stations.

        Parameters
        ----------
        latitude:
            Route-point latitude.

        longitude:
            Route-point longitude.

        radius_miles:
            Maximum straight-line distance from the route point.

        Returns
        -------
        List[Dict]
            Fuel stations ordered from nearest to farthest.
        """

        self._validate_coordinates(
            latitude,
            longitude,
        )


        if radius_miles <= 0:
            raise ValueError(
                "Search radius must be greater than zero."
            )


        search_point = np.radians(
            [
                [
                    latitude,
                    longitude,
                ]
            ]
        )


        # BallTree Haversine radius must be represented
        # as angular distance in radians.
        radius_radians = (
            radius_miles
            / EARTH_RADIUS_MILES
        )


        indexes, distances = (
            self.search_tree.query_radius(
                search_point,
                r=radius_radians,
                return_distance=True,
                sort_results=True,
            )
        )


        stations = []


        for index, distance in zip(
            indexes[0],
            distances[0],
        ):

            station = (
                self.fuel_data.iloc[
                    index
                ]
            )


            distance_miles = (
                float(distance)
                * EARTH_RADIUS_MILES
            )


            stations.append(
                self._station_to_dict(
                    station,
                    distance_miles,
                )
            )


        return stations


    # ========================================================
    # Average Fuel Price
    # ========================================================

    def get_average_fuel_price(
        self,
    ) -> float:
        """
        Return the average fuel price from the supplied
        processed fuel-price dataset.

        This is primarily used when a trip is shorter than
        the vehicle's 500-mile range and therefore no
        mid-route refueling stop is required.

        The trip still consumes fuel, so we need a reasonable
        price estimate rather than returning a $0 fuel cost.
        """

        if self.fuel_data.empty:
            raise ValueError(
                "Fuel dataset contains no fuel price information."
            )


        average_price = (
            self.fuel_data["price"]
            .mean()
        )


        if pd.isna(
            average_price
        ):
            raise ValueError(
                "Unable to calculate average fuel price."
            )


        return float(
            average_price
        )


# ============================================================
# Shared Service Instance
# ============================================================


fuel_station_service = (
    FuelStationService()
)