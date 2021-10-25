import os
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response
    

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

 
@app.route("/")
@login_required
def index():
    """Show portfolio of stocks""" 
    shares = db.execute(
        "SELECT stock_shares, stock_name, stock_symbol, stock_price FROM overall WHERE user_id = ?", session["user_id"])
    cashs = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"]) 
    return render_template("index.html", shares=shares, cashs=cashs)

    
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # dictionary for the share information
    shareinfo = {}
    # selecting current logged person balance
    balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"]) 
    balance = float(balance[0]['cash'])
    status = "Bought"
    
    # getting symbol and shares entered from user
    shares = request.form.get('shares')
    symbol = request.form.get('symbol')
    
    if request.method == "POST":
        # checking if user didnt enter symbol or shares
        if not symbol or not shares:
            return apology("Please Enter symbol/shares", 400)
    
        if not(shares.isdigit()):
            return apology("Please Enter Number & Not Text", 400) 
            
        if int(float(shares)) < 0:  
            return apology("Please Enter Positive Value", 400)

        if not(float(shares).is_integer()):
            return apology("Please Enter Whole Number", 400) 
            
        # getting share information    
        shareinfo = lookup(request.form.get("symbol")) 
        
        # checking if symbol exists
        if not shareinfo:
            return apology("INVALID Symbol", 400)
        
        # getting share price
        price = float(shareinfo.get('price'))
        stock_symbol = shareinfo.get('symbol')
        stock_name = shareinfo.get('name') 
         
        # checking if balance is enough
        if balance < price * int(float(shares)): 
            return apology("Not Enough Balance", 400)
        
        # inserting into account table the new transaction    
        else:
            db.execute("INSERT INTO account (user_id, stock_name, stock_price, stock_shares, stock_symbol, status) VALUES(?, ?, ?, ?, ?, ?)",
                       session["user_id"], stock_name, price, shares, stock_symbol, status)
            symbol_list = db.execute("SELECT stock_symbol, stock_shares FROM overall WHERE user_id = ?", session["user_id"])
         
        condition = False
        if len(symbol_list) == 0:
            db.execute("INSERT INTO overall (user_id, stock_name, stock_shares, stock_price, stock_symbol) VALUES(?, ?, ?, ?, ?)",
                       session["user_id"], stock_name, shares, shareinfo.get('price'), stock_symbol)    
        else:
            for index in range(len(symbol_list)):
                for value in symbol_list[index]:
                    if str(symbol.upper()) == str(symbol_list[index]['stock_symbol']):
                        total_shares = int(float(shares)) + int(symbol_list[index]['stock_shares'])
                        db.execute("UPDATE overall SET stock_shares = ? WHERE stock_symbol = ?", 
                                   total_shares, symbol_list[index]['stock_symbol']) 
                        condition = True
        
        if condition == False and len(symbol_list) != 0: 
            db.execute("INSERT INTO overall (user_id, stock_name, stock_shares, stock_price, stock_symbol) VALUES(?, ?, ?, ?, ?)", session["user_id"],
                       stock_name, shares, shareinfo.get('price'), stock_symbol)    
                    
        # updating the new balance in users table
        value = float(price) * float(shares)
        remaining = float(balance) - float(value)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remaining, session["user_id"])
            
        return redirect("/")
    
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    shares = db.execute(
        "SELECT stock_shares, status, stock_symbol, stock_price, Timestamp FROM account WHERE user_id = ?", session["user_id"])
    return render_template("history.html", shares=shares)

    return apology("TODO/ route(history)")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    
    result = {}
    
    if request.method == "POST":
        result = lookup(request.form.get("symbol"))
        
        if not result:
            return apology("INVALID SYMBOL", 400)
        return render_template("quoted.html", result=result)
        
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must confirm password", 400)
        
        # search database for the same user
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        
        # if there is a row means there is a user with same name
        if len(rows) != 0:
            return apology("username already registered", 400)

        # compare two passwords
        if request.form.get("password") != request.form.get("confirmation"): 
            return apology("password didnt match", 400)
        
        # save username and hashedpasswords in db
        username = request.form.get("username")
        hashpassword = generate_password_hash(request.form.get("password"))
        
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hashpassword)
        
        # Redirect user to home page
        return redirect("/login") 

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html") 


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # dictionary for the share information
    stocks = db.execute(
        "SELECT stock_shares, stock_symbol FROM overall WHERE user_id = ? GROUP BY stock_symbol", session["user_id"]) 
    
    # getting symbol and shares entered from user 
    shares = request.form.get('shares')
    symbol = request.form.get('symbol')
    balance = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"]) 
    balance = float(balance[0]['cash'])
    status = "SOLD"
    
    if request.method == "POST":
        # checking if user didnt enter symbol or shares
        if not symbol or not shares:
            return apology("Please Enter symbol/shares", 400)
        
        shareinfo = {} 
        shareinfo = lookup(str(request.form.get("symbol")))
        price = float(shareinfo.get('price'))
        stock_name = shareinfo.get('name')
        
        for i in range(0, len(stocks)):
            if symbol == stocks[i]['stock_symbol']:
                number = i
            if int(shares) > stocks[i]['stock_shares'] and symbol == stocks[i]['stock_symbol']:
                return apology("Not Enough Shares", 400)
        
        remaining_shares = stocks[number]['stock_shares'] - int(shares)
        
        if remaining_shares == 0:
            db.execute("DELETE FROM overall WHERE stock_symbol = ?", symbol)  
        db.execute("INSERT INTO account (user_id, stock_name, stock_price, stock_shares, stock_symbol, status) VALUES(?, ?, ?, ?, ?, ?)", session["user_id"],
                   stock_name, price, shares, symbol, status)
        db.execute("UPDATE overall SET stock_shares = ? WHERE user_id = ? AND stock_symbol = ?",
                   remaining_shares, session["user_id"], symbol)
        
        value = float(price) * float(shares)
        remaining = float(balance) + float(value)
        db.execute("UPDATE users SET cash = ? WHERE id = ?", remaining, session["user_id"])
        
        return redirect("/")
        
    else:
        return render_template("sell.html", stocks=stocks)
        

def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)