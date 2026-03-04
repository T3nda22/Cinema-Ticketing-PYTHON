from flask import Flask, render_template, request, redirect, url_for
import mysql.connector
from mysql.connector import Error
import random
import string

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'

# MySQL Database Configuration
db_config = {
    'host': 'localhost',
    'database': 'cinemax',
    'user': 'root',
    'password': ''  # Your MySQL password
}


def get_db_connection():
    """Create MySQL database connection"""
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None


def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return

    cursor = conn.cursor()

    try:
        # Movies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INT PRIMARY KEY AUTO_INCREMENT,
                title VARCHAR(255) NOT NULL,
                rating DECIMAL(2,1),
                duration VARCHAR(50),
                poster VARCHAR(500),
                director VARCHAR(255),
                director_sub VARCHAR(255),
                revenue VARCHAR(50),
                description TEXT,
                is_now_showing BOOLEAN DEFAULT TRUE
            )
        """)

        # Check if movies exist
        cursor.execute("SELECT COUNT(*) as count FROM movies")
        count = cursor.fetchone()[0]

        if count == 0:
            print("Inserting sample movies...")
            movies_data = [
                ('Us', 7.1, '2h 16m', 'images/cover1.jpg', 'JORDAN PEELE', 'WRITER/DIRECTOR OF GET OUT', '6m',
                 'A family\'s serene beach vacation turns to chaos when doppelgängers begin to terrorize them.'),
                ('The Shining', 8.4, '2h 26m',
                 'images/cover2.jpg',
                 'STANLEY KUBRICK', 'MASTER OF HORROR', '6m',
                 'A family heads to an isolated hotel for the winter where a sinister presence influences the father into violence.'),
                ('Beauty and the Beast', 7.7, '2h 9m',
                 'images/cover3.jpeg',
                 'BILL CONDON', 'DISNEY\'S LIVE ACTION', '6m',
                 'A selfish prince is cursed to become a monster for the rest of his life unless he learns to fall in love with a beautiful young woman he keeps prisoner.'),
                ('Step Brothers', 6.9, '1h 38m',
                 'images/cover4.jpg',
                 'ADAM MCKAY', 'COMEDY CLASSIC', '9m',
                 'Two aimless middle-aged losers still living at home are forced against their will to become roommates when their parents marry.'),
                ('AFTER', 7.0, '1h 45m',
                 'images/cover5.jpg',
                 'JENNIE GAGE', 'BASED ON THE NOVEL', '8m',
                 'A young woman falls for a guy with a dark secret and the two embark on a rocky relationship.')
            ]

            insert_query = """
                INSERT INTO movies (title, rating, duration, poster, director, director_sub, revenue, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.executemany(insert_query, movies_data)
            conn.commit()
            print(f"Inserted {cursor.rowcount} movies")

        # Showtimes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS showtimes (
                id INT PRIMARY KEY AUTO_INCREMENT,
                movie_id INT NOT NULL,
                show_time VARCHAR(20) NOT NULL,
                show_date DATE NOT NULL,
                price DECIMAL(8,2) DEFAULT 15.00,
                FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
            )
        """)

        # Check if showtimes exist
        cursor.execute("SELECT COUNT(*) as count FROM showtimes")
        showtime_count = cursor.fetchone()[0]

        if showtime_count == 0:
            # Get all movie IDs
            cursor.execute("SELECT id FROM movies")
            movie_ids = cursor.fetchall()

            show_times = ['10:00 AM', '1:00 PM', '4:00 PM', '7:00 PM', '10:00 PM']
            from datetime import date, timedelta

            for movie_id_row in movie_ids:
                movie_id = movie_id_row[0]
                for time in show_times:
                    cursor.execute("""
                        INSERT INTO showtimes (movie_id, show_time, show_date, price)
                        VALUES (%s, %s, DATE_ADD(CURDATE(), INTERVAL 1 DAY), 15.00)
                    """, (movie_id, time))
            conn.commit()
            print("Inserted showtimes")

        # Seats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seats (
                id INT PRIMARY KEY AUTO_INCREMENT,
                seat_row VARCHAR(2) NOT NULL,
                seat_number INT NOT NULL,
                seat_type VARCHAR(20) DEFAULT 'Standard',
                UNIQUE KEY unique_seat (seat_row, seat_number)
            )
        """)

        # Check if seats exist
        cursor.execute("SELECT COUNT(*) as count FROM seats")
        seat_count = cursor.fetchone()[0]

        if seat_count == 0:
            seat_layout = [
                ('A', list(range(10, 18))),
                ('B', list(range(2, 18))),
                ('C', list(range(1, 18))),
                ('D', list(range(2, 18))),
                ('E', list(range(2, 18))),
                ('F', list(range(6, 12))),
                ('G', [6, 8, 9, 11, 12]),
                ('H', list(range(6, 13)))
            ]

            for row, seats in seat_layout:
                for num in seats:
                    cursor.execute(
                        "INSERT INTO seats (seat_row, seat_number) VALUES (%s, %s)",
                        (row, num)
                    )
            conn.commit()
            print("Inserted seats")

        # Bookings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INT PRIMARY KEY AUTO_INCREMENT,
                booking_reference VARCHAR(20) UNIQUE NOT NULL,
                movie_id INT NOT NULL,
                showtime VARCHAR(20) NOT NULL,
                show_date DATE NOT NULL,
                seats VARCHAR(255) NOT NULL,
                number_of_tickets INT NOT NULL,
                total_amount DECIMAL(10,2) NOT NULL,
                customer_name VARCHAR(255),
                customer_email VARCHAR(255),
                booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (movie_id) REFERENCES movies(id)
            )
        """)

        # Users table for authentication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        print("Database initialization complete!")

    except Error as e:
        print(f"Error creating tables: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


# Initialize database
try:
    init_db()
except Exception as e:
    print(f"Database initialization error: {e}")


def get_movie_by_id(movie_id):
    """Fetch a single movie by ID"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
            movie = cursor.fetchone()
            cursor.close()
            conn.close()
            return movie
    except Exception as e:
        print(f"Error fetching movie: {e}")
    return None


def get_showtimes_for_movie(movie_id):
    """Fetch showtimes for a specific movie"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM showtimes 
                WHERE movie_id = %s 
                ORDER BY show_time
            """, (movie_id,))
            showtimes = cursor.fetchall()
            cursor.close()
            conn.close()
            return showtimes
    except Exception as e:
        print(f"Error fetching showtimes: {e}")
    return []


def get_all_movies():
    """Fetch all now showing movies"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM movies WHERE is_now_showing = TRUE")
            movies = cursor.fetchall()
            cursor.close()
            conn.close()
            return movies
    except Exception as e:
        print(f"Error fetching movies: {e}")
    return []


@app.route('/')
def index():
    movies = get_all_movies()
    return render_template('index.html', movies=movies)


@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    movie = get_movie_by_id(movie_id)
    showtimes = get_showtimes_for_movie(movie_id)

    if movie is None:
        return "Movie not found", 404

    return render_template('movie_details.html',
                           movie=movie,
                           showtimes=showtimes)


@app.route('/movie/<int:movie_id>/seats')
def seat_selection(movie_id):
    # Get parameters from URL
    showtime = request.args.get('showtime', '7:00 PM')
    tickets = request.args.get('tickets', '2')
    show_date = request.args.get('date', 'Today')

    # Get movie from database
    movie = get_movie_by_id(movie_id)

    if movie is None:
        return "Movie not found", 404

    # Get booked seats for this showtime (from database)
    booked_seats = []
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT seats FROM bookings 
                WHERE movie_id = %s AND showtime = %s
            """, (movie_id, showtime))
            bookings = cursor.fetchall()
            cursor.close()
            conn.close()

            # Extract booked seats
            for booking in bookings:
                if booking['seats']:
                    booked_seats.extend(booking['seats'].split(','))
    except Exception as e:
        print(f"Error fetching booked seats: {e}")

    return render_template('seat_selection.html',
                           movie=movie,
                           showtime=showtime,
                           tickets=int(tickets),
                           show_date=show_date,
                           booked_seats=booked_seats)


@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    if request.method == 'POST':
        # Get form data
        movie_id = request.form.get('movie_id')
        movie_title = request.form.get('movie_title')
        showtime = request.form.get('showtime')
        seats = request.form.get('seats')
        tickets = request.form.get('tickets')
        total = request.form.get('total')
        show_date = request.form.get('show_date')

        # Generate booking reference
        booking_ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        # Save to database
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO bookings (booking_reference, movie_id, showtime, show_date, seats, number_of_tickets, total_amount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (booking_ref, movie_id, showtime, show_date, seats, tickets, total))
                conn.commit()
                cursor.close()
                conn.close()
        except Exception as e:
            print(f"Error saving booking: {e}")

        return render_template('booking_confirmation.html',
                               booking_ref=booking_ref,
                               movie_title=movie_title,
                               showtime=showtime,
                               seats=seats,
                               tickets=tickets,
                               total=total,
                               show_date=show_date)


# Navigation Routes
@app.route('/showtimes')
def showtimes():
    # Get all movies for showtimes
    movies = get_all_movies()
    return render_template('showtimes.html', movies=movies)


@app.route('/coming-soon')
def coming_soon():
    # For now, just show all movies since we don't have a status field
    movies = get_all_movies()
    return render_template('coming_soon.html', movies=movies)


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/all-movies')
def all_movies():
    movies = get_all_movies()
    return render_template('all_movies.html', movies=movies)


# Authentication Routes
@app.route('/signin')
def signin():
    return render_template('signin.html')


@app.route('/login', methods=['POST'])
def login():
    # Process login form
    email = request.form.get('email')
    password = request.form.get('password')
    remember = request.form.get('remember')

    # TODO: Add your login logic here
    # - Check if user exists in database
    # - Verify password
    # - Create session

    print(f"Login attempt: {email}, Remember: {remember}")

    # For now, just redirect to home page
    return redirect(url_for('index'))


@app.route('/signup', methods=['POST'])
def signup():
    # Process signup form
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    terms = request.form.get('terms')

    # TODO: Add your signup logic here
    # - Validate passwords match
    # - Check if user/email already exists
    # - Hash password
    # - Insert into database

    print(f"Signup attempt: {username}, {email}, Terms accepted: {terms}")

    # For now, just redirect to signin page
    return redirect(url_for('signin'))


@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')


@app.route('/logout')
def logout():
    # TODO: Clear session
    return redirect(url_for('index'))


@app.route('/update-posters')
def update_posters():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        # Update Us to use local image
        cursor.execute("""
            UPDATE movies 
            SET poster = 'images/cover1.jpg' 
            WHERE id = 1
        """)

        # Update other movies to use local images (if you want)
        # cursor.execute("UPDATE movies SET poster = 'images/cover2.jpg' WHERE id = 2")
        # cursor.execute("UPDATE movies SET poster = 'images/cover3.jpeg' WHERE id = 3")
        # cursor.execute("UPDATE movies SET poster = 'images/cover4.jpg' WHERE id = 4")
        # cursor.execute("UPDATE movies SET poster = 'images/cover5.jpg' WHERE id = 5")

        conn.commit()
        cursor.close()
        conn.close()
        return "Poster paths updated! <a href='/'>Go to home page</a>"
    return "Database connection failed"


if __name__ == '__main__':
    app.run(debug=True, port=5000)