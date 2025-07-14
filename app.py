import os
import sqlite3
import sys

from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import error, login_required, steam

# Configure application
app = Flask(__name__)

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

@app.route("/")
@login_required
def index():

    return render_template("index.html")

@app.route("/profile")
@login_required
def settings():

    return render_template("index.html")
