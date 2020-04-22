# Project 1

Web Programming with Python and JavaScript

My project consist of seven template's folder files.
 Login.html, where user must fill form with username and password.
 Register.html - for registering on the site, providing creating a username and password.
After register you redirect to login.html to log in and then leap to index.html with flash message
"have been logged in", where you can search a book by one of: title, isbn, author. After performing
search you redirect to results.html where site display a list of matching results of the search.
When click on the wanted book from the result of the search, you would be taken to a book.html with title, isbn, author, publication year, and any reviews that users have been left. Also on the book page you are able to submit only one review for the same book, which consist of rating(1-5) and a text. If you make a GET request to site/api/isbn route, it would be return a JSON response with the book title, author, publication date, isbn, number reviews and average score.  
