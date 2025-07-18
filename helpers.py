import os
import requests
import sqlite3

from dotenv import load_dotenv
from flask import redirect, render_template, session
from functools import wraps

load_dotenv("setup.env")

STEAM_API_KEY = os.getenv("STEAM_API_KEY")

def error(message, code=400):
    """Render message as an error to user."""

    return render_template("error.hmtl", message, code)

def is_valid_steamid64(steamid64):
    """Checks if steamid64 is valid."""

    if len(steamid64) != 17 or not steamid64.isdigit():
            return False
    try:
        sid = int(steamid64)
    except ValueError:
        return False
    
    Lower_limit = 76561197960265728
    if sid < Lower_limit:
        return False
    
    if not str(sid).startswith("7656119"):
        return False
    
    return True

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

def library_update(steam_id64, user_id ):
    """ Pulls data from Steam API and adds it to DB"""

    game_library = steam(steam_id64)
    if game_library is None:
        return error("Failed to retrieve game library", 500)
    else:
        with sqlite3.connect("gamelist.db") as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            game_data = [
                        (
                            user_id,
                            game["appid"],
                            game["img_icon_url"],
                            game["name"],
                            "Steam",
                            game["playtime_forever"]
                        )
                        for game in game_library["games"]
                    ]
            
            cur.executemany("""
                INSERT INTO gamelist (user_id, appid, icon_img, gamename, platform, playtime)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, appid) DO UPDATE SET 
                    icon_img = excluded.icon_img, 
                    playtime = CASE 
                        WHEN excluded.playtime > gamelist.playtime THEN excluded.playtime
                            ELSE gamelist.playtime
                            END
            """, game_data)
            con.commit()

            # Grab current count of games
            cur.execute("SELECT COUNT(*) FROM gamelist WHERE user_id = ? AND listed = ?", (user_id, 1, ))
            game_count = cur.fetchone()[0]

            # Update total game count
            cur.execute("UPDATE users SET game_count = ? WHERE id = ?", (game_count, user_id, ))
            con.commit()
