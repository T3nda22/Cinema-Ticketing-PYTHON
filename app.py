from flask import Flask, render_template, request
import mysql.connector
from mysql.connector import Error
import random
import string

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this'

# MySQL Database Configuration
db_config = {
    'host': 'localhost',
    'database': 'cinemax',  # your database name in Workbench
    'user': 'root',  # your MySQL username (default is 'root')
    'password': 'your_password'  # YOUR MySQL password here!
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
    """Initialize database tables (run once)"""
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return

    cursor = conn.cursor()

    # Create tables if they don't exist
    try:
        # Users table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS users
                       (
                           id
                           INT
                           PRIMARY
                           KEY
                           AUTO_INCREMENT,
                           username
                           VARCHAR
                       (
                           100
                       ) UNIQUE NOT NULL,
                           email VARCHAR
                       (
                           255
                       ) UNIQUE NOT NULL,
                           password_hash VARCHAR
                       (
                           255
                       ) NOT NULL,
                           full_name VARCHAR
                       (
                           255
                       ) NOT NULL,
                           phone VARCHAR
                       (
                           20
                       ),
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                           )
                       """)

        # Movies table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS movies
                       (
                           id
                           INT
                           PRIMARY
                           KEY
                           AUTO_INCREMENT,
                           title
                           VARCHAR
                       (
                           255
                       ) NOT NULL,
                           rating DECIMAL
                       (
                           2,
                           1
                       ),
                           duration VARCHAR
                       (
                           50
                       ),
                           poster VARCHAR
                       (
                           500
                       ),
                           director VARCHAR
                       (
                           255
                       ),
                           director_sub VARCHAR
                       (
                           255
                       ),
                           revenue VARCHAR
                       (
                           50
                       ),
                           is_now_showing BOOLEAN DEFAULT TRUE,
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                           )
                       """)

        # Showtimes table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS showtimes
                       (
                           id
                           INT
                           PRIMARY
                           KEY
                           AUTO_INCREMENT,
                           movie_id
                           INT
                           NOT
                           NULL,
                           show_time
                           VARCHAR
                       (
                           10
                       ) NOT NULL,
                           show_date DATE NOT NULL,
                           price DECIMAL
                       (
                           8,
                           2
                       ) DEFAULT 12.50,
                           FOREIGN KEY
                       (
                           movie_id
                       ) REFERENCES movies
                       (
                           id
                       ) ON DELETE CASCADE
                           )
                       """)

        # Seats table (matching your Kuan.png layout)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS seats
                       (
                           id
                           INT
                           PRIMARY
                           KEY
                           AUTO_INCREMENT,
                           seat_row
                           CHAR
                       (
                           1
                       ) NOT NULL,
                           seat_number INT NOT NULL,
                           seat_type VARCHAR
                       (
                           20
                       ) DEFAULT 'Standard',
                           UNIQUE KEY unique_seat
                       (
                           seat_row,
                           seat_number
                       )
                           )
                       """)

        # Bookings table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS bookings
                       (
                           id
                           INT
                           PRIMARY
                           KEY
                           AUTO_INCREMENT,
                           booking_reference
                           VARCHAR
                       (
                           20
                       ) UNIQUE NOT NULL,
                           user_id INT,
                           showtime_id INT NOT NULL,
                           number_of_tickets INT NOT NULL,
                           total_amount DECIMAL
                       (
                           10,
                           2
                       ) NOT NULL,
                           booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           booking_status VARCHAR
                       (
                           20
                       ) DEFAULT 'confirmed',
                           FOREIGN KEY
                       (
                           showtime_id
                       ) REFERENCES showtimes
                       (
                           id
                       ) ON DELETE CASCADE,
                           FOREIGN KEY
                       (
                           user_id
                       ) REFERENCES users
                       (
                           id
                       )
                         ON DELETE SET NULL
                           )
                       """)

        # Booked seats table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS booked_seats (
                           id INT PRIMARY KEY AUTO_INCREMENT,
                           booking_id
                           INT
                           NOT
                           NULL,
                           seat_id
                           INT
                           NOT
                           NULL,
                           price_paid
                           DECIMAL
                       (
                           8,
                           2
                       ) NOT NULL,
                           FOREIGN KEY
                       (
                           booking_id
                       ) REFERENCES bookings
                       (
                           id
                       ) ON DELETE CASCADE,
                           FOREIGN KEY
                       (
                           seat_id
                       ) REFERENCES seats
                       (
                           id
                       )
                         ON DELETE CASCADE,
                           UNIQUE KEY unique_booking_seat
                       (
                           booking_id,
                           seat_id
                       )
                           )
                       """)

        # Insert sample movies if table is empty
        cursor.execute("SELECT COUNT(*) FROM movies")
        count = cursor.fetchone()[0]

        if count == 0:
            movies_data = [
                ('Us', 7.1, '2h 16m', 'cover1.jpg', 'JORDAN PEELE', 'WRITER/DIRECTOR OF GET OUT', '6m'),
                ('The Shining', 8.4, '2h 26m',
                 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&h=600&fit=crop', 'STANLEY KUBRICK',
                 'MASTER OF HORROR', '6m'),
                ('Beauty and the Beast', 7.7, '2h 9m',
                 'https://images.unsplash.com/photo-1489599809516-9827b6d1cf13?w=400&h=600&fit=crop', 'BILL CONDON',
                 'DISNEY\'S LIVE ACTION', '6m'),
                ('Step Brothers', 6.9, '1h 38m',
                 'https://images.unsplash.com/photo-1534447677768-be436bb09401?w=400&h=600&fit=crop', 'ADAM MCKAY',
                 'COMEDY CLASSIC', '9m'),
                ('AFTER', 7.0, '1h 45m',
                 'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=400&h=600&fit=crop', 'JENNIE GAGE',
                 'BASED ON THE NOVEL', '8m')
            ]

            insert_query = """
                           INSERT INTO movies (title, rating, duration, poster, director, director_sub, revenue)
                           VALUES (%s, %s, %s, %s, %s, %s, %s) \
                           """
            cursor.executemany(insert_query, movies_data)

            # Insert seats matching your Kuan.png layout
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
            print("Sample data inserted successfully!")

    except Error as e:
        print(f"Error creating tables: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


# Initialize database when app starts
try:
    init_db()
except Exception as e:
    print(f"Database initialization error: {e}")

# Sample data (fallback if database fails)
movies_now_showing = [
    {
        "id": 1,
        "title": "Us",
        "rating": 7.1,
        "duration": "2h 16m",
        "poster": "cover1.jpg",
        "revenue": "6m",
        "director": "JORDAN PEELE",
        "director_sub": "WRITER/DIRECTOR OF GET OUT"
    },
    {
        "id": 2,
        "title": "The Shining",
        "rating": 8.4,
        "duration": "2h 26m",
        "poster": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=400&h=600&fit=crop",
        "revenue": "6m",
        "director": "STANLEY KUBRICK",
        "director_sub": "MASTER OF HORROR"
    },
    {
        "id": 3,
        "title": "Beauty and the Beast",
        "rating": 7.7,
        "duration": "2h 9m",
        "poster": "https://images.unsplash.com/photo-1489599809516-9827b6d1cf13?w=400&h=600&fit=crop",
        "revenue": "6m",
        "director": "BILL CONDON",
        "director_sub": "DISNEY'S LIVE ACTION"
    },
    {
        "id": 4,
        "title": "Step Brothers",
        "rating": 6.9,
        "duration": "1h 38m",
        "poster": "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=400&h=600&fit=crop",
        "revenue": "9m",
        "director": "ADAM MCKAY",
        "director_sub": "COMEDY CLASSIC"
    },
    {
        "id": 5,
        "title": "AFTER",
        "rating": 7.0,
        "duration": "1h 45m",
        "poster": "https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?w=400&h=600&fit=crop",
        "revenue": "8m",
        "director": "JENNIE GAGE",
        "director_sub": "BASED ON THE NOVEL"
    }
]

coming_soon = [
    {"title": "Coming Soon", "date": "May 5"},
    {"title": "More Jate", "date": "May 15"},
    {"title": "June 1", "date": "June 1"}
]


def get_movies_from_db():
    """Fetch movies from database"""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM movies WHERE is_now_showing = TRUE")
        movies = cursor.fetchall()
        cursor.close()
        conn.close()
        return movies
    except Error as e:
        print(f"Error fetching movies: {e}")
        if conn:
            conn.close()
        return None


@app.route('/')
def index():
    # Try to get from database first
    try:
        movies = get_movies_from_db()
        if movies:
            return render_template('index.html',
                                   movies=movies,
                                   coming_soon=coming_soon,
                                   tickets_sold="1,247",
                                   earnings="$15,820")
    except Exception as e:
        print(f"Database error: {e}")

    # Fallback to sample data
    return render_template('index.html',
                           movies=movies_now_showing,
                           coming_soon=coming_soon,
                           tickets_sold="1,247",
                           earnings="$15,820")


@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    # Try to get from database
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
            movie = cursor.fetchone()
            cursor.close()
            conn.close()

            if movie:
                return render_template('movie_details.html',
                                       movie=movie,
                                       tickets_sold="1,247",
                                       earnings="$15,820")
    except Exception as e:
        print(f"Database error: {e}")

    # Fallback to sample data
    movie = next((m for m in movies_now_showing if m["id"] == movie_id), None)
    if movie is None:
        return "Movie not found", 404
    return render_template('movie_details.html',
                           movie=movie,
                           tickets_sold="1,247",
                           earnings="$15,820")


@app.route('/movie/<int:movie_id>/seats')
def seat_selection(movie_id):
    # Get parameters from URL
    showtime = request.args.get('showtime', '6:00PM')  # Default if not provided
    tickets = request.args.get('tickets', '1')  # Default if not provided

    # Get movie from database (you'll need to implement this)
    movie = get_movie_by_id(movie_id)  # Your function to fetch movie

    return render_template('seat_selection.html',
                           movie=movie,
                           showtime=showtime,
                           tickets=int(tickets))
if __name__ == '__main__':
    app.run(debug=True, port=5000)