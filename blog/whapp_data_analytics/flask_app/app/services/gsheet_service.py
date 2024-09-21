import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
import datetime
from dotenv import load_dotenv
import os

load_dotenv()
GSHEET_NAME = os.getenv("GSHEET_NAME")
GSHEET_TAB = os.getenv("GSHEET_TAB")


def authorize_gsheet_api():
    # Define the scope
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    # Add your service account credentials here
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json",
        scope,
    )

    # Authorize the client
    client = gspread.authorize(credentials)

    return client


def get_worksheet(gsheet_client):
    return gsheet_client.open(GSHEET_NAME).worksheet(title=GSHEET_TAB)


def update_gsheet(response):
    client = authorize_gsheet_api()
    worksheet = get_worksheet(client)

    cols_row = int(worksheet.cell(row=1, col=1).value)
    col_values = worksheet.row_values(cols_row)
    cols_values = {col: i for i, col in enumerate(col_values)}

    organize_response = dict(
        map(lambda col_val: col_val.split("="), response.split(","))
    )

    updating_row_lst = []
    for col, index in cols_values.items():
        value = organize_response.get(col)
        updating_row_lst.append(value)

    worksheet.append_row(updating_row_lst)

    return f"{updating_row_lst}"


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
    out_group["spent_percent"] = [spent_percentage]
    out_group["total_debits"] = [total_debits]
    out_group["total_credits"] = [total_credits]
    out_group["dollar_debit"] = [total_dollar_debits]
    out_group["inhand_debit"] = [total_inhand_debits]
    out_group["bank_debit"] = [total_bank_debits]

    return pd.DataFrame(out_group)


def gsheet_analysis():

    client = authorize_gsheet_api()
    worksheet = get_worksheet(client)

    # Get the data as a list of lists
    data = worksheet.get_all_values()

    # Convert it into a pandas DataFrame
    df = pd.DataFrame(data[1:], columns=data[0])

    cols_row = int(worksheet.cell(row=1, col=1).value)

    filtered_needed_df = df.iloc[(cols_row - 1) :]
    filtered_needed_df.columns = df.iloc[
        6
    ].values  # changing the column name in the freezed rows
    filtered_needed_df = filtered_needed_df[
        df.iloc[6].values[:7]
    ]  # getting only needed columns
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
        filtered_needed_df["transaction_date"]
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

    PAST_2_MONTHS_ST = pd.to_datetime("2024-08-01") - pd.to_timedelta(9, unit="W")

    LAST_MONTH = mod_data.sort_values("st_of_month").tail(1)

    LAST_3_MONTHS = mod_data.sort_values("st_of_month").tail(6)

    WA_analytics = f"Last month=> Spent %: {np.round(LAST_MONTH['spent_percent'].values[0],4)}, Total Credits: LKR {LAST_MONTH['total_credits'].values[0]}, Total Debits: LKR {LAST_MONTH['total_debits'].values[0]}"

    return WA_analytics
