import os
import sqlite3
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date
from flask import Flask, flash, redirect, render_template, request, session, jsonify
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import error, is_valid_steamid64, library_update, login_required, steam
from task import remove_delisted_games

# Configure application
app = Flask(__name__)

# Daily clear out of delisted games
scheduler = BackgroundScheduler()
scheduler.add_job(func=remove_delisted_games, trigger="interval", hours=24)
scheduler.start()

import atexit
atexit.register(lambda: scheduler.shutdown())

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

today = date.today().isoformat()

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if not username:
            return error("must provide username", 400)
        elif not password:
            return error("must provide password", 400)
        
        # Query database for username
        with sqlite3.connect("gamelist.db") as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE username = ?", (username, ))
            user = cur.fetchone()

        # Ensure username exists and password is correct
        if not user or not check_password_hash(user["hash"], password):
            return error("invalid username and/or password", 400)

        # Remember which user has logged in
        session["user_id"] = user["id"]

        # Redirect user to home page
        return redirect("/")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirmation = request.form.get("confirmation", "")

        # Check if username, password, and confirmation are empty and match
        if not username:
            return error("must provide username", 400)
        elif not password:
            return error("must provide password", 400)
        elif not confirmation:
            return error("must provide confirmation", 400)
        elif password != confirmation:
            return error("password and confirmation must match", 400)

        # Open DB
        with sqlite3.connect("gamelist.db") as con:
            cur = con.cursor()

            # Check if user exists
            cur.execute("SELECT username FROM users WHERE username = ?", (username, ))
            if cur.fetchone():
                return error("username already exists", 400)

            # Insert new user into DB
            hashed_pw = generate_password_hash(password)
            cur.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, hashed_pw))
            con.commit()

        return redirect("/")

    return render_template("register.html")

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Shows list of all games and allows edits and adds"""

    if request.method == "GET":
        with sqlite3.connect("gamelist.db") as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            user_id = session["user_id"]

            # Fetch current users game library
            cur.execute("SELECT id, appid, icon_img, gamename, platform, status, multiplayer, coop, genre, playtime, length FROM gamelist WHERE user_id = ? AND listed = ?", (user_id, 1, ))
            gamelist = cur.fetchall()

            return render_template("index.html", gamelist=gamelist)
        
@app.route("/games/update", methods=["POST"])
@login_required
def update_game():
    data = request.get_json()
    user_id = session["user_id"]

    with sqlite3.connect("gamelist.db") as con:
        cur = con.cursor()
        cur.execute("""
            UPDATE gamelist SET
                gamename = ?, platform = ?, status = ?, multiplayer = ?, coop = ?, genre = ?, playtime = ?, length = ?
                    WHERE user_id = ? AND id = ?
        """, (
            data["title"], data["platform"], data["status"],
            data["multiplayer"], data["coop"], data["genre"],
            data["playtime"], data["length"],
            user_id, data["id"]
        ))
        con.commit()

    return jsonify(success=True)

@app.route("/games/delete", methods=["POST"])
@login_required
def delete_game():
    data = request.get_json()
    user_id = session["user_id"]

    with sqlite3.connect("gamelist.db") as con:
        cur = con.cursor()
        cur.execute("DELETE FROM gamelist WHERE user_id = ? AND id = ?", (user_id, data["id"]))
        con.commit()

    return jsonify(success=True)

@app.route("/games/add", methods=["POST"])
@login_required
def add_game():
    data = request.get_json()
    user_id = session["user_id"]

    if not data["title"] or not data["platform"]:
        return jsonify(success=False, error="Missing title or platform"), 400

    with sqlite3.connect("gamelist.db") as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO gamelist (
                user_id, gamename, platform, status,
                multiplayer, coop, genre, playtime, length, listed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (
            user_id,
            data["title"],
            data["platform"],
            data.get("status", ""),
            data.get("multiplayer", 0),
            data.get("coop", 0),
            data.get("genre", ""),
            data.get("playtime", 0),
            data.get("length", 0)
        ))
        con.commit()

    return jsonify(success=True)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Allow user to input SteadID64 and update their gamelist"""

    user_id = session["user_id"]

    with sqlite3.connect("gamelist.db") as con:
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Check if user has a steamID
        cur.execute("SELECT steam_id FROM users WHERE id = ?", (user_id, ))
        result = cur.fetchone()
        current_steam_id = result["steam_id"] if result else None

        if request.method == "POST":
            action = request.form.get("action")
            steam_id64 = request.form.get("steam_id64")

            if action == "add" or action == "update" or action == "undo":
                # Check if SteamID is valid
                if not steam_id64:
                    return error("must provide steamID", 400)
                if is_valid_steamid64(steam_id64) == False:
                    return error("Invalid SteamID", 400)
                
                if action == "add":
                    # Insert SteamID into DB
                    if current_steam_id is None:
                        cur.execute("UPDATE users SET steam_id = ? WHERE id = ?", (steam_id64, user_id, ))
                        con.commit()

                        # Add new games to list and update current total count
                        library_update(steam_id64, user_id)

                        return redirect("/")

                elif action == "update":
                    if steam_id64 == current_steam_id:
                        return error("SteamID unchanged", 400)
                    else:
                        # update SteamID
                        cur.execute("UPDATE users SET steam_id = ?", (steam_id64, ))
                        # Delist games the user currently has from steam and add date
                        cur.execute("UPDATE gamelist SET listed = ?, delist_date = ? WHERE user_id = ? AND platform = ?", (0, today, user_id, "Steam", ))
                        con.commit()

                        # Add new games to list and update current total count
                        library_update(steam_id64, user_id)

                        return redirect("/")

                elif action == "undo":

                    game_library = steam(steam_id64)
                    if game_library is None:
                        return error("Failed to retrieve game library", 500)
                    
                    game_data = [
                        (
                            user_id,
                            steam_id64,
                            game["appid"],
                            game["img_icon_url"],
                            game["name"],
                            "Steam",
                            game["playtime_forever"]
                        )
                        for game in game_library["games"]
                    ]

                    # Relist games from users library
                    cur.executemany(
                        "UPDATE gamelist SET listed = ?, delist_date = ? WHERE appid = ? AND user_id = ? AND steam_id = ?", 
                        [
                            (1, None, appid, user_id, steam_id64)
                            for (_, _, appid, _, _, _, _) in game_data
                        ]
                    )
                    con.commit()
                    
                    # Add any new games and update data for all games in library
                    cur.executemany("""
                    INSERT INTO gamelist (user_id, steam_id, appid, icon_img, gamename, platform, playtime)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, appid) DO UPDATE SET 
                        icon_img = excluded.icon_img, 
                        playtime = CASE 
                            WHEN excluded.playtime > gamelist.playtime THEN excluded.playtime
                                ELSE gamelist.playtime
                                END
                    """, game_data)
                    con.commit()
                    

                    # Delist games that have the old steamid and add date
                    cur.execute("UPDATE gamelist SET listed = ?, delist_date = ? WHERE user_id = ? AND platform = ? AND steam_id = ?", (0, today, user_id, "Steam", current_steam_id, ))
                    con.commit()

                    # Grab current count of games
                    cur.execute("SELECT COUNT(*) FROM gamelist WHERE user_id = ? AND listed = ?", (user_id, 1, ))
                    game_count = cur.fetchone()[0]

                    # Update total game count
                    cur.execute("UPDATE users SET game_count = ? WHERE id = ?", (game_count, user_id, ))
                    con.commit()

                    # Update current steam_id
                    cur.execute("UPDATE users SET steam_id = ? WHERE id = ?", (steam_id64, user_id, ))
                    con.commit()

                    return redirect("/")

            elif action == "change_password":
                
                password = request.form.get("new_password", "")
                confirmation = request.form.get("confirm_password", "")
                current_password = request.form.get("current_password", "")

                # Check if user input all information and if it matches
                if not password:
                    return error("must provide password", 400)
                elif not confirmation:
                    return error("must provide confirmation", 400)
                elif not current_password:
                    return error("must provide current password", 400)
                elif password != confirmation:
                    return error("password and confirmation must match", 400)
                else: 
                    # Get old password from database
                    cur.execute("SELECT hash FROM users WHERE id = ?", (user_id, ))
                    old_password = cur.fetchone()
                    
                    if not check_password_hash(old_password["hash"], current_password):
                        return error("old password doesn't match", 400)
                    else:
                        # Generate hash for new password and update database
                        password = generate_password_hash(password)
                        cur.execute("UPDATE users SET hash = ? WHERE id = ?", (password, user_id, ))
                        con.commit()

            elif action == "delete_library":

                # Delist all games from users library
                cur.execute("UPDATE gamelist SET listed = ?, delist_date = ? WHERE user_id = ?", (0, today, user_id, ))
                con.commit()

                return redirect("/")

            elif action == "undo_delete_library":
                # Relist all delisted games in the users library
                cur.execute("UPDATE gamelist SET listed = ?, delist_date = ? WHERE user_id = ?", (1, None, user_id, ))
                con.commit()

                return redirect("/")

            elif action == "delete_account":
                # Delete users game library and account
                cur.execute("DELETE FROM gamelist WHERE user_id = ?", (user_id, ))
                cur.execute("DELETE FROM users WHERE id = ?", (user_id, ))
                con.commit()
                
                session.clear()

                return redirect("/register")

    return render_template("profile.html", current_steam_id=current_steam_id)