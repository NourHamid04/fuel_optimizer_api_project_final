import pandas as pd
import requests
from pathlib import Path
from io import StringIO


# ============================================================
# Files locations
# ============================================================


BASE_DIR = Path(__file__).resolve().parent.parent


DATA_DIR = (
    BASE_DIR
    / "fuel_optimizer_api"
    / "data"
)


INPUT_FILE = (
    DATA_DIR
    / "fuel-prices-for-be-assessment.csv"
)


OUTPUT_FILE = (
    DATA_DIR
    / "fuel-prices-processed.csv"
)



# ============================================================
# US Census Free Geocoder
# ============================================================


CENSUS_URL = (
    "https://geocoding.geo.census.gov/"
    "geocoder/locations/addressbatch"
)



# ============================================================
# Read original CSV
# ============================================================


def load_csv():

    print("Reading fuel prices CSV...")


    df = pd.read_csv(
        INPUT_FILE
    )


    print(
        f"Stations found: {len(df)}"
    )


    return df



# ============================================================
# Create file for Census geocoder
# ============================================================


def prepare_addresses(df):

    """
    Create the format required by
    US Census batch geocoder
    """


    batch = pd.DataFrame({

        "id":
            df.index,


        "address":
            df["Address"],


        "city":
            df["City"],


        "state":
            df["State"],


        "zip":
            ""

    })


    batch_file = (
        DATA_DIR
        /
        "addresses.csv"
    )


    batch.to_csv(
        batch_file,
        index=False,
        header=False
    )


    return batch_file



# ============================================================
# Send addresses to geocoder
# ============================================================


def get_coordinates(batch_file):

    print(
        "Getting coordinates..."
    )


    with open(
        batch_file,
        "rb"
    ) as file:


        response = requests.post(

            CENSUS_URL,

            files={
                "addressFile":
                (
                    "addresses.csv",
                    file
                )
            },

            data={
                "benchmark":
                "Public_AR_Current"
            },

            timeout=120
        )


    response.raise_for_status()


    return response.text



# ============================================================
# Convert geocoder response
# ============================================================


def parse_coordinates(data):


    columns = [

        "id",
        "input",
        "match",
        "type",
        "address",
        "coordinates",
        "tiger",
        "side"

    ]


    result = pd.read_csv(

        StringIO(data),

        header=None,

        names=columns

    )


    # Keep only successful matches

    result = result[
        result["match"] == "Match"
    ]



    # coordinates are:
    # longitude,latitude

    coords = (
        result["coordinates"]
        .str.split(
            ",",
            expand=True
        )
    )


    result["longitude"] = (
        coords[0]
    )


    result["latitude"] = (
        coords[1]
    )



    result["id"] = (
        result["id"]
        .astype(int)
    )


    return result[
        [
            "id",
            "latitude",
            "longitude"
        ]
    ]



# ============================================================
# Create processed CSV
# ============================================================


def create_processed_csv(
        original,
        coordinates
):


    original = (
        original
        .reset_index()
        .rename(
            columns={
                "index":"id"
            }
        )
    )


    merged = original.merge(

        coordinates,

        on="id"

    )


    processed = pd.DataFrame({

        "name":
            merged["Truckstop Name"],


        "city":
            merged["City"],


        "state":
            merged["State"],


        "price":
            merged["Retail Price"],


        "latitude":
            merged["latitude"],


        "longitude":
            merged["longitude"]

    })


    processed.to_csv(

        OUTPUT_FILE,

        index=False

    )


    print(
        "Created:",
        OUTPUT_FILE
    )


    print(
        "Processed stations:",
        len(processed)
    )



# ============================================================
# Run script
# ============================================================


def main():


    print(
        "Starting fuel data processing..."
    )


    fuel_data = load_csv()


    batch_file = prepare_addresses(
        fuel_data
    )


    response = get_coordinates(
        batch_file
    )


    coordinates = parse_coordinates(
        response
    )


    create_processed_csv(

        fuel_data,

        coordinates

    )


    print(
        "Finished!"
    )



if __name__ == "__main__":

    main()