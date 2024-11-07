from random import choice, randint

def get_response(user_input: str) -> str:
    lowered: str = user_input.lower()

    if lowered=='':
        return 'silent?'
    elif 'roll dice' in lowered:
        return f"you rolled {randint(1,6)}"
    else:
        return "nigga dont play with me"
