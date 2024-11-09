from random import choice, randint
from gsheet_service import gsheet_analysis, update_gsheet


def get_response(user_input: str) -> str:
    lowered: str = user_input.lower()

    if lowered == "":
        return "silent?"
    elif "date" in lowered:
        return update_gsheet(lowered)
    elif "gsheet analysis" in lowered:
        return gsheet_analysis()
    else:
        return "nigga dont play with me"
