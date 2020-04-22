import os, json
import requests
from datetime import datetime
from flask import Flask, session, render_template, request, redirect, jsonify, flash
from flask_session import Session
from functools import wraps
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)
# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))
def login_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
@login_required
def index():

    return render_template("index.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    """ Log user in """
    session.clear()
    user_name = request.form.get("user_name")
    password = request.form.get("password")
    if request.method == "POST":
        if not request.form.get("user_name"):
            return render_template("error.html", message="must provide username")
        elif not request.form.get("password"):
            return render_template("error.html", message="must provide password")

        rows = db.execute("SELECT * FROM users WHERE user_name = :user_name",
                            {"user_name": user_name})
        result = rows.fetchone()
        # Ensure username exists and password is correct
        if result == None:
            return render_template("error.html", message="invalid username or password")
        # Remember  users has logged in
        session["user_id"] = result[0]
        session["user_name"] = result[1]
        flash("You have been logged in", 'success')
        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """ Log user out """
    session.clear()
    flash("You have already logged out!", "warning")
    # Redirect user to login form
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    """ Register user """
    session.clear()
    user_name = request.form.get("user_name")
    if request.method == "POST":
        if not request.form.get("user_name"):
            return render_template("error.html", message="must provide username")
        user = db.execute("SELECT * FROM users WHERE user_name = :user_name",
                          {"user_name": user_name}).fetchone()
        if user:
            return render_template("error.html", message="username already exist")
        elif not request.form.get("password"):
            return render_template("error.html", message="must provide password")
        elif not request.form.get("confirmation"):
            return render_template("error.html", message="confirm password")
        elif request.form.get("password")!= request.form.get("confirmation"):
            return render_template("error.html", message="passwords didn't match")
        password = request.form.get("password")
        # Insert register into DB
        db.execute("INSERT INTO users (user_name, password) VALUES (:user_name, :password)",
                            {"user_name": user_name, "password": password})
        # Commit changes to database
        db.commit()
        flash('Account created', 'warning')
        # Redirect user to login page
        return redirect("/login")
    else:
        return render_template("register.html")

@app.route("/search", methods=["GET"])
@login_required
def search():
        # Check book
    if not request.args.get("book"):
        return render_template("error.html", message="you must provide a book.")
        # is bringing a "dictionary" object or other collection-type of objects
    searched = "%" + request.args.get("book") + "%"
        # Capitalize all words of input for search
        # https://docs.python.org/3.7/library/stdtypes.html?highlight=title#str.title
    searched = searched.title()
    rows = db.execute("SELECT * FROM books WHERE(title LIKE :searched) OR (isbn LIKE :searched) OR (author LIKE :searched) LIMIT 15",
                    {"searched": searched})
    # Books not founded
    if rows.rowcount == 0:
        return render_template("error.html", message="we can't find books with that description.")
    # Fetch all the results
    books = rows.fetchall()

    return render_template("results.html", books=books)

@app.route("/book/<isbn>", methods=['GET','POST'])
@login_required
def book(isbn):
    """ Save user review and load same page with reviews updated."""
    if request.method == "POST":
        # Save current user info
        currentUser = session["user_id"]
        # Fetch form data
        rating = request.form.get("rating")
        comment = request.form.get("comment")
        # Search book_id by ISBN
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn",
                                {"isbn": isbn})
        # Save id into variable
        bookId = row.fetchone()
        bookId = bookId[0]

        # Check for user submission, only 1 review allowed per book
        row2 = db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
                    {"user_id": currentUser,
                     "book_id": bookId})
        # review already exist
        if row2.rowcount == 1:

            flash('You not be able to submit multiple review for the same book', 'warning')
            return redirect("/book/" + isbn)
        # Convert to save into DB
        rating = int(rating)

        db.execute("INSERT INTO reviews (user_id, book_id, comment, rating) VALUES (:user_id, :book_id, :comment, :rating)",
                    {"user_id": currentUser, "book_id": bookId, "comment": comment, "rating": rating})
        # Commit transactions to DB and close the connection
        db.commit()
        flash('Review submitted!', 'info')

        return redirect("/book/" + isbn)

    # Take the book ISBN and redirect to his page (GET)
    else:

        row = db.execute("SELECT isbn, title, author, year FROM books WHERE isbn = :isbn", {"isbn": isbn})

        bookInfo = row.fetchall()
        """ GOODREADS review """
        # Read API key from env variable
        key = os.getenv("GOODREADS_KEY")
        # Query the api with key and ISBN as parameters
        query = requests.get("https://www.goodreads.com/book/review_counts.json",
                params={"key": key, "isbns": isbn})
        # Convert the response to JSON
        response = query.json()
        # "Clean" the JSON before passing it to the bookInfo list
        response = response['books'][0]
        # Append it as the second element on the list. [1]
        bookInfo.append(response)
        """ Users review """
         # Search book_id by ISBN
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn", {"isbn": isbn})
        # Save id into variable
        book = row.fetchone() # (id,)
        book = book[0]
        # book reviews
        # Date formatting (https://www.postgresql.org/docs/12.2/functions-formatting.html)
        results = db.execute("SELECT users.user_name, comment, rating, \
                            to_char(com_time :: TIMESTAMP, 'Day, Mon-DD, YYYY HH24:MI:SS') as time \
                            FROM users \
                            INNER JOIN reviews \
                            ON users.id = reviews.user_id \
                            WHERE book_id = :book \
                            ORDER BY time",
                            {"book": book})
        reviews = results.fetchall()

        return render_template("book.html", bookInfo=bookInfo, reviews=reviews)

@app.route("/api/<isbn>", methods=['GET'])
@login_required
def api_call(isbn):
    # COUNT returns rowcount
    # rowcount sqlalchemy method returns the number of rows matched
    # INNER JOIN associates books with reviews tables
    row = db.execute("SELECT title, author, year, isbn, \
                    COUNT(reviews.id) as review_count, \
                    AVG(reviews.rating) as average_score \
                    FROM books \
                    INNER JOIN reviews \
                    ON books.id = reviews.book_id \
                    WHERE isbn = :isbn \
                    GROUP BY title, author, year, isbn",
                    {"isbn": isbn})
    # Error checking
    if row.rowcount != 1:
        return jsonify({"Error": "Invalid book ISBN"}), 422
    # Fetch result from RowProxy
    tmp = row.fetchone()
    # Convert to dict
    result = dict(tmp.items())
    # Round Avg Score to 2 decimal. This returns a string which does not meet the requirement.
    # https://floating-point-gui.de/languages/python/
    result['average_score'] = float('%.2f'%(result['average_score']))

    return jsonify(result)
