import os
import sqlite3
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from datetime import date
from flask import Flask, flash, redirect, render_template, request, session
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
            cur.execute("SELECT appid, icon_img, gamename, platform, status, multiplayer, coop, genre, playtime, length FROM gamelist WHERE user_id = ? AND listed = ?", (user_id, 1, ))
            gamelist = cur.fetchall()

            return render_template("index.html", gamelist=gamelist)

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Allow user to input SteadID64 and update their gamelist"""

    if request.method == "POST":
        steam_id64 = request.form.get("steam_id64")
        user_id = session["user_id"]

        # Check if SteamID is valid
        if not steam_id64:
            return error("must provide steamID", 400)
        if len(steam_id64) != 17 or not steam_id64.isdigit():
            return error("invalid steamID", 400)
        if is_valid_steamid64(steam_id64) == False:
            return error("Invalid SteamID", 400)
        
        with sqlite3.connect("gamelist.db") as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()

            # Check if user exists
            cur.execute("SELECT steam_id FROM users WHERE id = ?", (user_id, ))
            result = cur.fetchone()
            current_steam_id = result["steam_id"] if result else None

            if current_steam_id is None:
                # Insert SteamID into DB
                cur.execute("UPDATE users SET steam_id = ? WHERE id = ?" , (steam_id64, user_id, ))
                con.commit()

                # Add new games to list and update current total count
                library_update(steam_id64, user_id)

            else:
                if steam_id64 == current_steam_id:
                    return error("SteamID unchanged", 400)
                else:
                    today = date.today().isoformat()
                    # Delist games the user currently has from steam and add date
                    cur.execute("UPDATE gamelist SET listed = ?, delist_date = ? WHERE user_id = ?", (0, today, user_id))
                    con.commit()

                    # Add new games to list and update current total count
                    library_update(steam_id64, user_id)

    return render_template("profile.html")