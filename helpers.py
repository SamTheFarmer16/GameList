import os
import requests

from dotenv import load_dotenv
from flask import redirect, render_template, session
from functools import wraps

load_dotenv("setup.env")

STEAM_API_KEY = os.getenv("STEAM_API_KEY")

def error(message, code=400):
    """Render message as an error to user."""

    return render_template("error.hmtl", message, code)


def login_required(f):
    """
    Decorate routes to require login.

    https://flask.palletsprojects.com/en/latest/patterns/viewdecorators/
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function

def steam(steam_id):
    """Look up Steam profile for user."""

    url = f"http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={STEAM_API_KEY}&steamid={steam_id}&include_appinfo=1&format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for HTTP error responses
        response_data = response.json()
        owned_games = response_data.get("response", {})
        game_count = owned_games.get("game_count", 0)
        games = owned_games.get("games", [])
        return {
            "game_count": game_count,
            "games": games
        }
    except requests.RequestException as e:
        print(f"Request error: {e}")
    except (KeyError, ValueError) as e:
        print(f"Data parsing error: {e}")
    return None

"""for getting a picture of the logo http://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{hash}.jpg"""