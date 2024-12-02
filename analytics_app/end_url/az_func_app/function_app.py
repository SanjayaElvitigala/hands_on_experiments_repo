import azure.functions as func
import logging
import json
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from binascii import unhexlify

import datetime
import pandas as pd
import numpy as np

import time
import requests
import os

import matplotlib.pyplot as plt
from io import BytesIO
import base64


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def verify_headers(request: func.HttpRequest, discord_public_key: str):
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    body = request.get_body().decode("utf-8")

    if not (signature and timestamp):
        return func.HttpResponse(
            "missing headers",
            status_code=400,
        )

    try:
        # Load the public key
        public_key = Ed25519PublicKey.from_public_bytes(unhexlify(discord_public_key))

        # Verify the signature
        public_key.verify(unhexlify(signature), f"{timestamp}{body}".encode("utf-8"))
    except InvalidSignature:
        return func.HttpResponse(
            "invalid request signature",
            status_code=401,
        )
    except ValueError as e:
        logging.error(f"Error processing public key or signature: {e}")
        return func.HttpResponse(
            "invalid public key or signature",
            status_code=400,
        )

    req_body = request.get_json()
    # Handle Discord PING type
    if req_body["type"] == 1:  # PING
        response_data = {"type": 1}  # PONG
        return func.HttpResponse(json.dumps(response_data), mimetype="application/json")


def get_spent_percentage(
    group,
    gby_cols,
    dollar_rate=300,
    calc_cols=["dollars", "credits", "debits", "in_hand"],
):

    total_bank_credits = group[group.dollars == 0].credits.sum()
    total_bank_debits = group.debits.sum()

    total_inhand_credits = group[
        (group.in_hand > 0) & (group.debits == 0)
    ].in_hand.sum()
    total_inhand_debits = np.abs(
        group[(group.in_hand < 0) & (group.credits == 0)].in_hand.sum()
    )

    total_dollar_credits = group[group.dollars > 0].dollars.sum() * dollar_rate
    total_dollar_debits = np.abs(
        group[(group.dollars < 0) & (group.credits == 0)].dollars.sum() * dollar_rate
    )

    total_credits = total_bank_credits + total_inhand_credits + total_dollar_credits
    total_debits = total_inhand_debits + total_bank_debits + total_dollar_debits

    spent_percentage = total_debits / total_credits

    out_group = {}  # group.drop_duplicates().copy()
    out_group["spent_percent"] = [np.round(spent_percentage * 100, 2)]
    out_group["total_debits"] = [total_debits]
    out_group["total_credits"] = [total_credits]
    out_group["dollar_debit"] = [total_dollar_debits]
    out_group["inhand_debit"] = [total_inhand_debits]
    out_group["bank_debit"] = [total_bank_debits]

    return pd.DataFrame(out_group)


def gsheet_analysis():
    SHEET_ID = os.environ["SHEET_ID"]
    SHEET_TAB_NAME = os.environ["SHEET_TAB_NAME"]
    SHEET_API_KEY = os.environ["SHEET_API_KEY"]
    SHEET_CONFIG_CELL = os.environ["SHEET_CONFIG_CELL"]
    get_sheets_url = (
        lambda sheet_id, data_range: f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{data_range}"
    )

    CONFIG_DATA_RANGE = f"{SHEET_TAB_NAME}!{SHEET_CONFIG_CELL}"
    PARAMS = {"key": SHEET_API_KEY}
    config_data_cell = requests.get(
        url=get_sheets_url(sheet_id=SHEET_ID, data_range=CONFIG_DATA_RANGE),
        params=PARAMS,
    )

    # these values are indicated in the A1 cell
    # cols_row = row number of the main columns
    # data_st_row = row number where the needed data starts
    # n_cols = number of main columns considered in cols_row
    # Note that cols_row and data_st_row are NOT zero indexed
    cols_row, data_st_row, col_range = config_data_cell.json()["values"][0][0].split(
        ","
    )
    cols_row, data_st_row = int(cols_row), int(data_st_row)

    sheet_data = requests.get(
        url=get_sheets_url(
            sheet_id=SHEET_ID, data_range=f"{SHEET_TAB_NAME}!{col_range}"
        ),
        params=PARAMS,
    )

    # getting only needed columns
    filtered_needed_df = pd.DataFrame(
        sheet_data.json()["values"][1:], columns=sheet_data.json()["values"][0]
    )
    filtered_needed_df.columns = [
        "transaction_date",
        "description",
        "dollars",
        "salary",
        "credits",
        "in_hand",
        "debits",
    ]  # renaming cols as needed
    filtered_needed_df["transaction_date"] = pd.to_datetime(
        filtered_needed_df["transaction_date"], format="mixed"
    )
    filtered_needed_df = filtered_needed_df.sort_values("transaction_date")
    filtered_needed_df[["dollars", "salary", "credits", "in_hand", "debits"]] = (
        filtered_needed_df[
            ["dollars", "salary", "credits", "in_hand", "debits"]
        ].replace("", "0.0")
    )

    for col in ["dollars", "salary", "credits", "in_hand", "debits"]:
        filtered_needed_df.loc[:, col] = (
            filtered_needed_df[col].str.strip().str.replace(",", "")
        )
        filtered_needed_df.loc[filtered_needed_df[col] == "", col] = (
            filtered_needed_df[col]
            .loc[filtered_needed_df[col] == ""]
            .replace("", "0.0")
        )
        filtered_needed_df.loc[:, col] = filtered_needed_df[col].astype("float")

    mod_data = filtered_needed_df.copy()
    mod_data["year"] = mod_data.transaction_date.dt.year
    mod_data["month"] = mod_data.transaction_date.dt.month
    mod_data["st_of_month"] = pd.to_datetime(
        mod_data.transaction_date.dt.year.astype("str")
        + "-"
        + mod_data.transaction_date.dt.month.astype("str")
        + "-01"
    )

    TODAY = datetime.datetime.today()
    START_OF_CURRENT_MONTH = pd.to_datetime(f"{TODAY.year}-{TODAY.month}-01")

    mod_data = (
        mod_data[mod_data.transaction_date < START_OF_CURRENT_MONTH]
        .groupby(["st_of_month"])
        .apply(
            lambda group: get_spent_percentage(group=group, gby_cols=["st_of_month"]),
            include_groups=False,
        )
        .reset_index()
    )
    mod_data = mod_data.drop("level_1", axis=1)

    if START_OF_CURRENT_MONTH.month == 1:
        YEAR = START_OF_CURRENT_MONTH.year - 1
        MONTH = 12
    else:
        YEAR = START_OF_CURRENT_MONTH.year
        MONTH = START_OF_CURRENT_MONTH.month

    PAST_2_MONTHS_ST = START_OF_CURRENT_MONTH - pd.to_timedelta(9, unit="W")

    LAST_MONTH = mod_data.sort_values("st_of_month").tail(1)

    LAST_3_MONTHS = mod_data.sort_values("st_of_month").tail(6)

    WA_analytics = f"Last month=> Spent %: {np.round(LAST_MONTH['spent_percent'].values[0],4)}, Total Credits: LKR {LAST_MONTH['total_credits'].values[0]}, Total Debits: LKR {LAST_MONTH['total_debits'].values[0]}"

    return WA_analytics


@app.route(route="http_discord")
def http_discord(req: func.HttpRequest) -> func.HttpResponse:
    DISCORD_PUBLIC_KEY = os.environ["DISCORD_PUBLIC_KEY"]
    logging.info("Python HTTP trigger function processed a request.")

    req_body = req.get_json()

    if req_body["type"] == 1:
        print("VERIFY SECTION CALLED")
        response_data = verify_headers(
            request=req, discord_public_key=DISCORD_PUBLIC_KEY
        )
        return response_data
    else:

        if req_body["data"]["name"] == "last_month":
            original_message = req_body["data"]["options"][0]["value"]
            analysis_out = gsheet_analysis()

            response_data = {
                "type": 4,
                "data": {"content": analysis_out},
            }

            print(f"FINAL RESPONSE ABOUT TO BE CALLED {response_data}")
            return func.HttpResponse(
                json.dumps(response_data), mimetype="application/json", status_code=200
            )
        elif req_body["data"]["name"] == "last_month_viz":
            fruits = ["apple", "blueberry", "cherry", "orange"]
            counts = [40, 100, 30, 55]

            plt.bar(x=fruits, height=counts)
            plt.tight_layout()

            # Save plot to BytesIO
            img_buffer = BytesIO()
            plt.savefig(img_buffer, format="jpg")
            img_buffer.seek(0)
            plt.close()

            # File
            files = {
                "file": (
                    "image.jpg",
                    img_buffer.getvalue(),
                    "image/jpg",
                )  # The picture that we want to send in binary
            }

            # Optional message to send with the picture
            payload = {"content": "yo yo"}

            r = requests.post(os.environ["CHANNEL_WEBHOOK"], data=payload, files=files)

            response_data = {
                "type": 4,
                "data": {"content": "visualization will be return shortly"},
            }
            return func.HttpResponse(
                json.dumps(response_data), mimetype="application/json", status_code=200
            )
