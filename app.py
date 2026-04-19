from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import sqlite3
import random
import string
import json
import re
import time
import os
import requests
import base64
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this-in-production'
app.permanent_session_lifetime = timedelta(days=30)

# SQLite Database Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'db', 'cinemax.db')

# Ensure the db directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# PayMongo Configuration - FROM ENVIRONMENT VARIABLES
PAYMONGO_SECRET_KEY = os.getenv('PAYMONGO_SECRET_KEY', '')
PAYMONGO_PUBLIC_KEY = os.getenv('PAYMONGO_PUBLIC_KEY', '')

if not PAYMONGO_SECRET_KEY or not PAYMONGO_PUBLIC_KEY:
    print("⚠️ WARNING: PayMongo API keys not found in .env file!")

# Cinema Types Configuration
CINEMA_TYPES = {
    'regular': {
        'name': 'regular',
        'display_name': 'Regular Cinema',
        'icon': '🎬',
        'base_price': 350,
        'seat_layout': {'rows': 10, 'cols': 12, 'total_seats': 120},
        'features': ['Standard Seating', '7.1 Surround Sound', 'Regular Screen'],
        'color': 'primary',
        'badge': 'Standard'
    },
    'directors_club': {
        'name': 'directors_club',
        'display_name': "Director's Club",
        'icon': '✨',
        'base_price': 700,
        'seat_layout': {'rows': 6, 'cols': 8, 'total_seats': 48},
        'features': ['Luxury Recliners', 'Dolby Atmos', 'Wait Service', 'Exclusive Lounge Access'],
        'color': 'warning',
        'badge': 'Premium'
    },
    'imax': {
        'name': 'imax',
        'display_name': 'IMAX',
        'icon': '🎥',
        'base_price': 875,
        'seat_layout': {'rows': 12, 'cols': 15, 'total_seats': 180},
        'features': ['Giant Screen', 'IMAX Laser Projection', '12-Channel Sound', 'Enhanced Experience'],
        'color': 'danger',
        'badge': 'IMAX'
    }
}

# Predefined Admin and Employee Accounts
PREDEFINED_ACCOUNTS = {
    'admin': {
        'email': 'ron@gmail.com',
        'password': 'Admin123',
        'username': 'Administrator',
        'role': 'admin'
    },
    'employees': [
        {
            'email': 'employee1@cinemax.com',
            'password': 'Employee@123',
            'username': 'John Employee',
            'role': 'employee',
            'department': 'ticketing'
        },
        {
            'email': 'employee2@cinemax.com',
            'password': 'Employee@123',
            'username': 'Jane Employee',
            'role': 'employee',
            'department': 'concessions'
        },
        {
            'email': 'manager@cinemax.com',
            'password': 'Manager@123',
            'username': 'Mike Manager',
            'role': 'manager',
            'department': 'management'
        }
    ]
}


def get_db_connection():
    """Create SQLite database connection"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"Error connecting to SQLite: {e}")
        return None


def generate_seats_for_cinema_type(cinema_type, rows, cols):
    """Generate all seats for a specific cinema type"""
    seats = []
    for row in range(rows):
        row_label = chr(65 + row)  # A, B, C, etc.
        for col in range(1, cols + 1):
            seat_code = f"{row_label}{col}"
            seats.append((cinema_type, row_label, col, seat_code, 'standard', 1))
    return seats


def init_seats_table():
    """Initialize seats table with all seat layouts"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) as count FROM seats")
        count = cursor.fetchone()['count']

        if count == 0:
            print("Generating seats for all cinema types...")

            # Regular Cinema (10 rows x 12 cols = 120 seats)
            regular_seats = generate_seats_for_cinema_type('regular', 10, 12)
            for seat in regular_seats:
                cursor.execute("""
                    INSERT INTO seats (cinema_type, row_label, seat_number, seat_code, seat_type, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, seat)

            # Director's Club (6 rows x 8 cols = 48 seats)
            directors_seats = generate_seats_for_cinema_type('directors_club', 6, 8)
            for seat in directors_seats:
                cursor.execute("""
                    INSERT INTO seats (cinema_type, row_label, seat_number, seat_code, seat_type, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, seat)

            # IMAX (12 rows x 15 cols = 180 seats)
            imax_seats = generate_seats_for_cinema_type('imax', 12, 15)
            for seat in imax_seats:
                cursor.execute("""
                    INSERT INTO seats (cinema_type, row_label, seat_number, seat_code, seat_type, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, seat)

            conn.commit()
            print(f"✅ Generated {len(regular_seats) + len(directors_seats) + len(imax_seats)} seats total!")

    except Exception as e:
        print(f"Error initializing seats: {e}")
    finally:
        cursor.close()
        conn.close()


def init_db():
    """Initialize database tables with 3NF design"""
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to database")
        return

    cursor = conn.cursor()

    try:
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'user',
                reset_token VARCHAR(100),
                reset_token_expiry TIMESTAMP NULL,
                is_verified BOOLEAN DEFAULT 0,
                verification_token VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL
            )
        """)

        # Movies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                rating DECIMAL(2,1),
                duration VARCHAR(50),
                poster VARCHAR(500),
                director VARCHAR(255),
                director_sub VARCHAR(255),
                revenue VARCHAR(50),
                description TEXT,
                is_now_showing BOOLEAN DEFAULT 1
            )
        """)

        # Showtimes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS showtimes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_id INTEGER NOT NULL,
                show_time VARCHAR(20) NOT NULL,
                show_date DATE NOT NULL,
                cinema_type VARCHAR(50) DEFAULT 'regular',
                base_price DECIMAL(8,2) DEFAULT 350.00,
                price DECIMAL(8,2) DEFAULT 350.00,
                FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
            )
        """)

        # SEATS table (NEW - 3NF compliant)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cinema_type VARCHAR(50) NOT NULL,
                row_label VARCHAR(2) NOT NULL,
                seat_number INTEGER NOT NULL,
                seat_code VARCHAR(10) NOT NULL,
                seat_type VARCHAR(50) DEFAULT 'standard',
                is_active BOOLEAN DEFAULT 1,
                UNIQUE(cinema_type, seat_code)
            )
        """)

        # Bookings table (REMOVED seats column)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_reference VARCHAR(20) UNIQUE NOT NULL,
                user_id INTEGER,
                movie_id INTEGER NOT NULL,
                movie_title VARCHAR(255) NOT NULL,
                cinema_type VARCHAR(50) DEFAULT 'regular',
                showtime VARCHAR(20) NOT NULL,
                show_date DATE NOT NULL,
                number_of_tickets INTEGER NOT NULL,
                total_amount DECIMAL(10,2) NOT NULL,
                payment_method VARCHAR(50),
                payment_status VARCHAR(50) DEFAULT 'pending',
                paymongo_checkout_id VARCHAR(100),
                paymongo_payment_id VARCHAR(100),
                customer_name VARCHAR(255),
                customer_email VARCHAR(255),
                booking_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                paid_at TIMESTAMP NULL,
                cancelled_at TIMESTAMP NULL,
                cancellation_reason VARCHAR(255),
                FOREIGN KEY (movie_id) REFERENCES movies(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # BOOKING_SEATS table (NEW - Junction table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS booking_seats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_reference VARCHAR(20) NOT NULL,
                seat_id INTEGER NOT NULL,
                price DECIMAL(8,2) NOT NULL,
                FOREIGN KEY (booking_reference) REFERENCES bookings(booking_reference) ON DELETE CASCADE,
                FOREIGN KEY (seat_id) REFERENCES seats(id),
                UNIQUE(booking_reference, seat_id)
            )
        """)

        # Payments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_reference VARCHAR(20) NOT NULL,
                paymongo_payment_id VARCHAR(100),
                paymongo_checkout_id VARCHAR(100),
                amount DECIMAL(10,2) NOT NULL,
                payment_method VARCHAR(50),
                status VARCHAR(50),
                webhook_payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_reference) REFERENCES bookings(booking_reference)
            )
        """)

        # Movie Notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movie_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movie_id INTEGER,
                movie_title TEXT,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        print(f"Database initialized at: {DB_PATH}")

        # Initialize seats table with all seat layouts
        init_seats_table()

    except Exception as e:
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


# ============================================================
# PAYMONGO PAYMENT FUNCTIONS
# ============================================================

def create_paymongo_checkout(booking_ref, amount, description, success_url, cancel_url):
    """Create a PayMongo Checkout Session"""
    url = "https://api.paymongo.com/v1/checkout_sessions"
    amount_centavos = int(float(amount) * 100)

    payload = {
        "data": {
            "attributes": {
                "send_email_receipt": True,
                "show_description": True,
                "show_line_items": True,
                "description": description,
                "line_items": [
                    {
                        "currency": "PHP",
                        "amount": amount_centavos,
                        "name": "Cinemax Movie Ticket",
                        "quantity": 1,
                        "description": f"Booking Reference: {booking_ref}"
                    }
                ],
                "payment_method_types": ["card", "gcash", "grab_pay", "paymaya"],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": {
                    "booking_reference": booking_ref
                }
            }
        }
    }

    auth_string = base64.b64encode(f"{PAYMONGO_SECRET_KEY}:".encode()).decode()
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Basic {auth_string}"
    }

    try:
        print(f"Creating PayMongo checkout for booking {booking_ref}, amount: ₱{amount}")
        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200 or response.status_code == 201:
            result = response.json()
            if "data" in result and "attributes" in result["data"]:
                checkout_url = result["data"]["attributes"]["checkout_url"]
                checkout_id = result["data"]["id"]
                print(f"✅ Checkout created successfully! ID: {checkout_id}")
                return {
                    'success': True,
                    'checkout_url': checkout_url,
                    'checkout_id': checkout_id
                }
            else:
                error_msg = result.get('errors', [{}])[0].get('detail', 'Unknown error')
                return {'success': False, 'error': error_msg}
        else:
            return {'success': False, 'error': f'Payment service error (Status: {response.status_code})'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def retrieve_checkout_session(checkout_id):
    """Retrieve checkout session status"""
    url = f"https://api.paymongo.com/v1/checkout_sessions/{checkout_id}"
    auth_string = base64.b64encode(f"{PAYMONGO_SECRET_KEY}:".encode()).decode()
    headers = {"accept": "application/json", "authorization": f"Basic {auth_string}"}

    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return {'success': True, 'data': response.json().get('data', {})}
        return {'success': False, 'error': f"Status: {response.status_code}"}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_cinema_config(cinema_type):
    """Get cinema configuration by type"""
    return CINEMA_TYPES.get(cinema_type, CINEMA_TYPES['regular'])


def get_cinema_price(cinema_type):
    """Get price for cinema type"""
    config = get_cinema_config(cinema_type)
    return config['base_price']


def get_seat_layout(cinema_type):
    """Get seat layout for cinema type"""
    config = get_cinema_config(cinema_type)
    return config['seat_layout']


def get_movie_by_id(movie_id):
    """Fetch a single movie by ID"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
            movie = cursor.fetchone()
            cursor.close()
            conn.close()
            return dict(movie) if movie else None
    except Exception as e:
        print(f"Error fetching movie: {e}")
    return None


def get_showtimes_for_movie(movie_id, show_date=None, cinema_type=None):
    """Fetch showtimes for a specific movie with optional cinema type filter"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            query = "SELECT * FROM showtimes WHERE movie_id = ?"
            params = [movie_id]
            if show_date:
                query += " AND show_date = ?"
                params.append(show_date)
            if cinema_type:
                query += " AND cinema_type = ?"
                params.append(cinema_type)
            query += " ORDER BY show_time"
            cursor.execute(query, params)
            showtimes = cursor.fetchall()
            cursor.close()
            conn.close()
            return [dict(st) for st in showtimes]
    except Exception as e:
        print(f"Error fetching showtimes: {e}")
    return []


def get_all_movies():
    """Fetch all now showing movies"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE is_now_showing = 1")
            movies = cursor.fetchall()
            cursor.close()
            conn.close()
            return [dict(movie) for movie in movies]
    except Exception as e:
        print(f"Error fetching movies: {e}")
    return []


def get_booked_seats(movie_id, showtime, show_date, cinema_type):
    """Fetch booked seats for a specific show and cinema type (UPDATED for 3NF)"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.seat_code 
                FROM booking_seats bs
                JOIN bookings b ON bs.booking_reference = b.booking_reference
                JOIN seats s ON bs.seat_id = s.id
                WHERE b.movie_id = ? 
                AND b.showtime = ? 
                AND b.show_date = ? 
                AND b.cinema_type = ?
                AND b.payment_status IN ('paid', 'confirmed')
            """, (movie_id, showtime, show_date, cinema_type))
            bookings = cursor.fetchall()
            cursor.close()
            conn.close()
            return [booking['seat_code'] for booking in bookings]
    except Exception as e:
        print(f"Error fetching booked seats: {e}")
    return []


def generate_booking_reference():
    """Generate unique booking reference"""
    prefix = "CIN"
    while True:
        reference = prefix + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM bookings WHERE booking_reference = ?", (reference,))
            existing = cursor.fetchone()
            cursor.close()
            conn.close()
            if not existing:
                return reference


def save_booking_to_db(booking_data):
    """Save booking to database with seats (UPDATED for 3NF)"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            user_id = session.get('user_id')
            seats_list = booking_data['seats'].split(', ')

            # Insert into bookings table (no seats column)
            if user_id:
                cursor.execute("""
                    INSERT INTO bookings (
                        booking_reference, user_id, movie_id, movie_title, cinema_type, 
                        showtime, show_date, number_of_tickets, total_amount, payment_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    booking_data['booking_reference'],
                    user_id,
                    booking_data['movie_id'],
                    booking_data['movie_title'],
                    booking_data['cinema_type'],
                    booking_data['showtime'],
                    booking_data['show_date'],
                    booking_data['tickets'],
                    booking_data['total_amount'],
                    'pending'
                ))
            else:
                cursor.execute("""
                    INSERT INTO bookings (
                        booking_reference, movie_id, movie_title, cinema_type, 
                        showtime, show_date, number_of_tickets, total_amount, payment_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    booking_data['booking_reference'],
                    booking_data['movie_id'],
                    booking_data['movie_title'],
                    booking_data['cinema_type'],
                    booking_data['showtime'],
                    booking_data['show_date'],
                    booking_data['tickets'],
                    booking_data['total_amount'],
                    'pending'
                ))

            # Insert each seat into booking_seats table
            price_per_ticket = booking_data['total_amount'] / booking_data['tickets']

            for seat_code in seats_list:
                cursor.execute("SELECT id FROM seats WHERE cinema_type = ? AND seat_code = ?",
                               (booking_data['cinema_type'], seat_code))
                seat = cursor.fetchone()
                if seat:
                    cursor.execute("""
                        INSERT INTO booking_seats (booking_reference, seat_id, price)
                        VALUES (?, ?, ?)
                    """, (booking_data['booking_reference'], seat['id'], price_per_ticket))

            conn.commit()
            cursor.close()
            conn.close()
            return True
    except Exception as e:
        print(f"Error saving booking: {e}")
        import traceback
        traceback.print_exc()
    return False


def update_booking_payment_status(booking_ref, status):
    """Update booking payment status"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE bookings SET payment_status = ? WHERE booking_reference = ?", (status, booking_ref))
            if status == 'paid':
                cursor.execute("UPDATE bookings SET paid_at = CURRENT_TIMESTAMP WHERE booking_reference = ?",
                               (booking_ref,))
            conn.commit()
            cursor.close()
            conn.close()
            return True
    except Exception as e:
        print("Status update error:", e)
    return False


# ============================================================
# AUTHENTICATION DECORATORS
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'predefined_user' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('signin', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'predefined_user' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('signin', next=request.url))
        role = session.get('role')
        if role not in ['admin', 'manager']:
            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


def employee_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'predefined_user' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('signin', next=request.url))
        role = session.get('role')
        if role not in ['admin', 'manager', 'employee']:
            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)

    return decorated_function


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    """Home page"""
    try:
        conn = get_db_connection()
        if not conn:
            return render_template('index.html', now_showing_movies=[], coming_soon_movies=[])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movies WHERE is_now_showing = 1 ORDER BY id DESC")
        now_showing_movies = [dict(movie) for movie in cursor.fetchall()]
        cursor.execute("SELECT * FROM movies WHERE is_now_showing = 0 ORDER BY id DESC")
        coming_soon_movies = [dict(movie) for movie in cursor.fetchall()]
        cursor.close()
        conn.close()
        return render_template('index.html', now_showing_movies=now_showing_movies,
                               coming_soon_movies=coming_soon_movies)
    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('index.html', now_showing_movies=[], coming_soon_movies=[])


@app.route('/movie/<int:movie_id>')
def movie_details(movie_id):
    movie = get_movie_by_id(movie_id)
    if movie is None:
        return "Movie not found", 404
    if not movie.get('poster'):
        movie['poster'] = url_for('static', filename='images/default-poster.jpg')
    return render_template('movie_details.html', movie=movie)


@app.route('/movie/<int:movie_id>/cinema-selection')
def cinema_selection(movie_id):
    """Select cinema type page"""
    movie = get_movie_by_id(movie_id)
    show_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    if movie is None:
        return "Movie not found", 404
    available_cinemas = []
    for cinema_key, cinema_config in CINEMA_TYPES.items():
        showtimes = get_showtimes_for_movie(movie_id, show_date, cinema_key)
        if showtimes:
            available_cinemas.append({'type': cinema_key, 'config': cinema_config, 'showtimes': showtimes})
    return render_template('cinema_selection.html', movie=movie, cinema_types=CINEMA_TYPES,
                           available_cinemas=available_cinemas, show_date=show_date)


@app.route('/movie/<int:movie_id>/seats')
def seat_selection(movie_id):
    cinema_type = request.args.get('cinema_type', 'regular')
    showtime = request.args.get('showtime', '7:00 PM')
    tickets = request.args.get('tickets', '2')
    show_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    movie = get_movie_by_id(movie_id)
    if movie is None:
        return "Movie not found", 404
    cinema_config = get_cinema_config(cinema_type)
    price = cinema_config['base_price']
    booked_seats = get_booked_seats(movie_id, showtime, show_date, cinema_type)
    seat_layout = get_seat_layout(cinema_type)
    return render_template('seat_selection.html', movie=movie, cinema_type=cinema_type, cinema_config=cinema_config,
                           showtime=showtime, tickets=int(tickets), show_date=show_date, price=price,
                           booked_seats=booked_seats, seat_layout=seat_layout)


@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    try:
        movie_id = request.form.get('movie_id')
        movie_title = request.form.get('movie_title')
        cinema_type = request.form.get('cinema_type')
        showtime = request.form.get('showtime')
        show_date = request.form.get('show_date')
        seats = request.form.get('seats')
        tickets = request.form.get('tickets')
        total = request.form.get('total')

        if not all([movie_id, movie_title, cinema_type, showtime, show_date, seats, tickets, total]):
            missing = [f for f in
                       ['movie_id', 'movie_title', 'cinema_type', 'showtime', 'show_date', 'seats', 'tickets', 'total']
                       if not locals().get(f)]
            return f"Missing required fields: {', '.join(missing)}", 400

        tickets = int(tickets)
        total = float(total)
        booking_ref = generate_booking_reference()
        cinema_config = get_cinema_config(cinema_type)
        price_per_ticket = total / tickets if tickets > 0 else cinema_config['base_price']

        booking_data = {
            'booking_reference': booking_ref,
            'movie_id': movie_id,
            'movie_title': movie_title,
            'cinema_type': cinema_type,
            'showtime': showtime,
            'show_date': show_date,
            'seats': seats,
            'tickets': tickets,
            'total_amount': total
        }

        if save_booking_to_db(booking_data):
            return render_template('booking_confirmation.html', booking_ref=booking_ref, movie_id=movie_id,
                                   movie_title=movie_title, cinema_type=cinema_type,
                                   cinema_display_name=cinema_config['display_name'], showtime=showtime,
                                   show_date=show_date, seats=seats, tickets=tickets, total=total,
                                   price_per_ticket=price_per_ticket, paymongo_public_key=PAYMONGO_PUBLIC_KEY)
        else:
            return "Error saving booking to database", 500
    except Exception as e:
        print(f"Error in confirm_booking: {e}")
        return str(e), 500


@app.route('/process-payment', methods=['POST'])
def process_payment():
    try:
        booking_ref = request.form.get('booking_ref')
        amount = request.form.get('amount')
        payment_method = request.form.get('payment_method')

        if not all([booking_ref, amount, payment_method]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400

        amount_float = float(amount)
        if amount_float < 100:
            return jsonify({'success': False, 'message': 'Minimum payment amount is ₱100.00'}), 400

        base_url = request.host_url.rstrip('/')
        success_url = f"{base_url}{url_for('payment_success')}?booking_ref={booking_ref}"
        cancel_url = f"{base_url}{url_for('payment_failed')}?booking_ref={booking_ref}"
        description = f"Cinemax Booking {booking_ref}"

        result = create_paymongo_checkout(booking_ref, amount_float, description, success_url, cancel_url)

        if result and result.get('success'):
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE bookings SET paymongo_checkout_id = ?, payment_method = ? WHERE booking_reference = ?",
                        (result['checkout_id'], payment_method, booking_ref))
                    conn.commit()
                    cursor.close()
                    conn.close()
            except Exception as e:
                print(f"Error updating booking: {e}")
            return jsonify(
                {'success': True, 'checkout_url': result['checkout_url'], 'checkout_id': result['checkout_id']})
        else:
            error_message = result.get('error', 'Failed to create payment') if result else 'Payment creation failed'
            return jsonify({'success': False, 'message': error_message}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/payment/success')
def payment_success():
    booking_ref = request.args.get('booking_ref')
    if not booking_ref:
        flash('No booking reference provided', 'error')
        return redirect(url_for('index'))
    update_booking_payment_status(booking_ref, 'paid')
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bookings WHERE booking_reference = ?", (booking_ref,))
            booking = cursor.fetchone()
            cursor.close()
            conn.close()
            if booking:
                return render_template('payment_success.html', booking=dict(booking))
    except Exception as e:
        print(f"Error fetching booking: {e}")
    return render_template('payment_success.html', booking_ref=booking_ref)


@app.route('/payment/failed')
def payment_failed():
    booking_ref = request.args.get('booking_ref')
    if booking_ref:
        update_booking_payment_status(booking_ref, 'failed')
    return render_template('payment_failed.html', booking_ref=booking_ref)


@app.route('/cancel-booking', methods=['POST'])
def cancel_booking():
    booking_ref = request.form.get('booking_ref')
    reason = request.form.get('reason', 'User cancelled')
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE bookings SET payment_status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, cancellation_reason = ? WHERE booking_reference = ?",
                (reason, booking_ref))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True})
    except Exception as e:
        print(f"Error cancelling booking: {e}")
    return jsonify({'success': False}), 500


@app.route('/mark-paid-cash', methods=['POST'])
@login_required
def mark_paid_cash():
    booking_ref = request.form.get('booking_ref')
    if not booking_ref:
        return jsonify({'success': False, 'message': 'Missing booking reference'})
    if update_booking_payment_status(booking_ref, 'paid'):
        return jsonify({'success': True, 'message': 'Payment recorded'})
    else:
        return jsonify({'success': False, 'message': 'Database error'})


@app.route('/showtimes')
def showtimes():
    return render_template('showtimes.html')


@app.route('/coming-soon')
def coming_soon():
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM movies WHERE is_now_showing = 0 ORDER BY id DESC")
            coming_soon_movies = [dict(m) for m in cursor.fetchall()]
            cursor.close()
            conn.close()
            return render_template('coming_soon.html', coming_soon_movies=coming_soon_movies)
    except Exception as e:
        print(f"Error in coming_soon: {e}")
    return render_template('coming_soon.html', coming_soon_movies=[])


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/all-movies')
def all_movies():
    movies = get_all_movies()
    return render_template('all_movies.html', movies=movies)


@app.route('/signin')
def signin():
    if 'user_id' in session or 'predefined_user' in session:
        return redirect(url_for('index'))
    return render_template('signin.html')


@app.route('/login', methods=['POST'])
def login():
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'

        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'})

        # Check predefined accounts
        if email == PREDEFINED_ACCOUNTS['admin']['email']:
            if password == PREDEFINED_ACCOUNTS['admin']['password']:
                session['predefined_user'] = True
                session['user_id'] = 'admin_predefined'
                session['username'] = PREDEFINED_ACCOUNTS['admin']['username']
                session['email'] = PREDEFINED_ACCOUNTS['admin']['email']
                session['role'] = PREDEFINED_ACCOUNTS['admin']['role']
                if remember:
                    session.permanent = True
                return jsonify(
                    {'success': True, 'message': 'Admin login successful', 'redirect': url_for('admin_dashboard')})
            else:
                return jsonify({'success': False, 'error_type': 'wrong_password', 'message': 'Wrong password'})

        for employee in PREDEFINED_ACCOUNTS['employees']:
            if email == employee['email']:
                if password == employee['password']:
                    session['predefined_user'] = True
                    session['user_id'] = f"emp_{email}"
                    session['username'] = employee['username']
                    session['email'] = employee['email']
                    session['role'] = employee['role']
                    session['department'] = employee.get('department', '')
                    if remember:
                        session.permanent = True
                    redirect_url = url_for('employee_dashboard') if employee['role'] == 'employee' else url_for(
                        'manager_dashboard')
                    return jsonify({'success': True, 'message': f'{employee["role"].capitalize()} login successful',
                                    'redirect': redirect_url})
                else:
                    return jsonify({'success': False, 'error_type': 'wrong_password', 'message': 'Wrong password'})

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, password, role FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            if not user:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error_type': 'email_not_found',
                                'message': 'Email does not exist. Please check your email or sign up.'})
            if check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                session['role'] = user['role']
                if remember:
                    session.permanent = True
                cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
                conn.commit()
                cursor.close()
                conn.close()
                next_page = request.args.get('next')
                redirect_url = next_page if next_page else url_for('index')
                return jsonify({'success': True, 'message': 'Login successful', 'redirect': redirect_url})
            else:
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'error_type': 'wrong_password', 'message': 'Wrong password'})
        else:
            return jsonify({'success': False, 'message': 'Database connection error'})
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred during login'})


@app.route('/signup', methods=['POST'])
def signup():
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        terms = request.form.get('terms')

        if not all([username, email, password, confirm_password]):
            return jsonify({'success': False, 'message': 'All fields are required'})
        if password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'})
        if len(password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters'})
        if not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
            return jsonify({'success': False, 'message': 'Password must contain both letters and numbers'})
        if not terms:
            return jsonify({'success': False, 'message': 'You must agree to the Terms of Service'})
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'success': False, 'message': 'Invalid email format'})

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Email already registered'})
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Username already taken'})
            hashed_password = generate_password_hash(password)
            cursor.execute("INSERT INTO users (username, email, password, role, is_verified) VALUES (?, ?, ?, ?, ?)",
                           (username, email, hashed_password, 'user', 1))
            conn.commit()
            cursor.execute("SELECT id, username, email FROM users WHERE email = ?", (email,))
            new_user = cursor.fetchone()
            if new_user:
                session['user_id'] = new_user['id']
                session['username'] = new_user['username']
                session['email'] = new_user['email']
                session['role'] = 'user'
                session.permanent = True
                cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (new_user['id'],))
                conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': 'Account created successfully', 'redirect': url_for('index')})
        else:
            return jsonify({'success': False, 'message': 'Database connection error'})
    except Exception as e:
        print(f"Signup error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred during registration'})


@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')


@app.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        email = request.form.get('email')
        if not email:
            return jsonify({'success': False, 'message': 'Email is required'})
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'})
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Email not found in our records.'})
        reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        expiry = datetime.now() + timedelta(hours=1)
        cursor.execute("UPDATE users SET reset_token = ?, reset_token_expiry = ? WHERE id = ?",
                       (reset_token, expiry, user['id']))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Please set your new password.', 'reset_token': reset_token})
    except Exception as e:
        print(f"Reset password error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'})


@app.route('/update-password-direct', methods=['POST'])
def update_password_direct():
    try:
        email = request.form.get('email')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not email or not new_password or not confirm_password:
            return jsonify({'success': False, 'message': 'All fields are required'})
        if new_password != confirm_password:
            return jsonify({'success': False, 'message': 'Passwords do not match'})
        if len(new_password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters'})
        if not re.search(r'[A-Za-z]', new_password) or not re.search(r'[0-9]', new_password):
            return jsonify({'success': False, 'message': 'Password must contain both letters and numbers'})
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'})
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Email not found'})
        hashed_password = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password = ?, reset_token = NULL, reset_token_expiry = NULL WHERE id = ?",
                       (hashed_password, user['id']))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(
            {'success': True, 'message': 'Password reset successful! You can now log in with your new password.',
             'redirect': url_for('signin')})
    except Exception as e:
        print(f"Error updating password: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'})


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html', user=session, predefined_accounts=PREDEFINED_ACCOUNTS,
                           cinema_types=CINEMA_TYPES)


@app.route('/manager/dashboard')
@admin_required
def manager_dashboard():
    return render_template('manager_dashboard.html', user=session, cinema_types=CINEMA_TYPES)


@app.route('/employee/dashboard')
@employee_required
def employee_dashboard():
    return render_template('employee_dashboard.html', user=session)


@app.route('/admin/stats')
@admin_required
def admin_stats():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) as total FROM bookings WHERE payment_status = 'paid'")
        total_sales = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as count FROM movies")
        total_movies = cursor.fetchone()['count']
        cursor.execute(
            "SELECT COALESCE(SUM(number_of_tickets), 0) as total FROM bookings WHERE payment_status = 'paid'")
        total_tickets = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as count FROM bookings")
        total_bookings = cursor.fetchone()['count']
        cursor.execute(
            "SELECT cinema_type, COALESCE(SUM(total_amount), 0) as total FROM bookings WHERE payment_status = 'paid' GROUP BY cinema_type")
        sales_by_cinema = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'total_sales': float(total_sales), 'total_movies': total_movies,
                        'total_tickets': total_tickets, 'total_bookings': total_bookings,
                        'sales_by_cinema': sales_by_cinema})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/movies')
@admin_required
def admin_movies():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movies ORDER BY id DESC")
        movies = [dict(movie) for movie in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'movies': movies})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/movie/<int:movie_id>', methods=['GET'])
@admin_required
def admin_get_movie(movie_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM movies WHERE id = ?", (movie_id,))
        movie = cursor.fetchone()
        cursor.close()
        conn.close()
        if not movie:
            return jsonify({'success': False, 'message': 'Movie not found'}), 404
        return jsonify({'success': True, 'movie': dict(movie)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/movie', methods=['POST'])
@admin_required
def admin_add_movie():
    try:
        data = request.get_json()
        title = data.get('title')
        rating = data.get('rating')
        duration = data.get('duration')
        poster = data.get('poster')
        director = data.get('director')
        description = data.get('description')
        is_now_showing = data.get('is_now_showing', '1')
        if not title:
            return jsonify({'success': False, 'message': 'Movie title is required'}), 400
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO movies (title, rating, duration, poster, director, description, is_now_showing) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, rating, duration, poster, director, description, is_now_showing))
        conn.commit()
        movie_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Movie added successfully', 'movie_id': movie_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/movie/<int:movie_id>', methods=['PUT'])
@admin_required
def admin_update_movie(movie_id):
    try:
        data = request.get_json()
        title = data.get('title')
        rating = data.get('rating')
        duration = data.get('duration')
        poster = data.get('poster')
        director = data.get('director')
        description = data.get('description')
        is_now_showing = data.get('is_now_showing', '1')
        if not title:
            return jsonify({'success': False, 'message': 'Movie title is required'}), 400
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE movies SET title = ?, rating = ?, duration = ?, poster = ?, director = ?, description = ?, is_now_showing = ? WHERE id = ?",
            (title, rating, duration, poster, director, description, is_now_showing, movie_id))
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Movie not found'}), 404
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Movie updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/movie/<int:movie_id>', methods=['DELETE'])
@admin_required
def admin_delete_movie(movie_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE movie_id = ?", (movie_id,))
        booking_count = cursor.fetchone()['count']
        if booking_count > 0:
            cursor.close()
            conn.close()
            return jsonify(
                {'success': False, 'message': f'Cannot delete movie with {booking_count} existing bookings.'}), 400
        cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Movie not found'}), 404
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Movie deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/bookings')
@admin_required
def admin_bookings():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bookings ORDER BY booking_date DESC")
        bookings = [dict(booking) for booking in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'bookings': bookings})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(total_amount), 0) as total FROM bookings WHERE payment_status = 'paid' AND DATE(paid_at) = DATE('now')")
        today_sales = cursor.fetchone()['total']
        cursor.execute(
            "SELECT COALESCE(SUM(total_amount), 0) as total FROM bookings WHERE payment_status = 'paid' AND strftime('%W', paid_at) = strftime('%W', 'now')")
        week_sales = cursor.fetchone()['total']
        cursor.execute(
            "SELECT COALESCE(SUM(total_amount), 0) as total FROM bookings WHERE payment_status = 'paid' AND strftime('%m', paid_at) = strftime('%m', 'now') AND strftime('%Y', paid_at) = strftime('%Y', 'now')")
        month_sales = cursor.fetchone()['total']
        cursor.execute(
            "SELECT movie_title, COUNT(*) as booking_count FROM bookings WHERE payment_status = 'paid' GROUP BY movie_title ORDER BY booking_count DESC LIMIT 1")
        popular_movie = cursor.fetchone()
        most_popular_movie = popular_movie['movie_title'] if popular_movie else 'No data'
        cursor.execute(
            "SELECT showtime, COUNT(*) as booking_count FROM bookings WHERE payment_status = 'paid' GROUP BY showtime ORDER BY booking_count DESC LIMIT 1")
        peak = cursor.fetchone()
        peak_time = peak['showtime'] if peak else 'No data'
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'today_sales': float(today_sales), 'week_sales': float(week_sales),
                        'month_sales': float(month_sales), 'most_popular_movie': most_popular_movie,
                        'peak_time': peak_time})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/showtimes', methods=['GET'])
@admin_required
def admin_showtimes():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute(
            "SELECT s.*, m.title as movie_title FROM showtimes s JOIN movies m ON s.movie_id = m.id ORDER BY s.show_date DESC, s.show_time ASC")
        showtimes = [dict(st) for st in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'showtimes': showtimes})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/showtimes', methods=['POST'])
@admin_required
def admin_add_showtimes():
    try:
        data = request.get_json()
        movie_id = data.get('movie_id')
        show_date = data.get('show_date')
        show_times = data.get('show_times', [])
        cinema_type = data.get('cinema_type', 'regular')
        cinema_config = get_cinema_config(cinema_type)
        price = cinema_config['base_price']
        if not movie_id:
            return jsonify({'success': False, 'message': 'Movie ID is required'}), 400
        if not show_date:
            return jsonify({'success': False, 'message': 'Show date is required'}), 400
        if not show_times:
            return jsonify({'success': False, 'message': 'At least one show time is required'}), 400
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        added_count = 0
        skipped_count = 0
        for show_time in show_times:
            cursor.execute(
                "SELECT id FROM showtimes WHERE movie_id = ? AND show_date = ? AND show_time = ? AND cinema_type = ?",
                (movie_id, show_date, show_time, cinema_type))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO showtimes (movie_id, show_time, show_date, cinema_type, base_price, price) VALUES (?, ?, ?, ?, ?, ?)",
                    (movie_id, show_time, show_date, cinema_type, price, price))
                added_count += 1
            else:
                skipped_count += 1
        conn.commit()
        cursor.close()
        conn.close()
        if added_count > 0:
            message = f'{added_count} showtimes added successfully for {cinema_config["display_name"]}'
            if skipped_count > 0:
                message += f' ({skipped_count} skipped - already exist)'
            return jsonify({'success': True, 'message': message, 'added': added_count, 'skipped': skipped_count})
        else:
            return jsonify({'success': False, 'message': 'No new showtimes were added (they may already exist)'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/showtime/<int:showtime_id>', methods=['DELETE'])
@admin_required
def admin_delete_showtime(showtime_id):
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute("DELETE FROM showtimes WHERE id = ?", (showtime_id,))
        conn.commit()
        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Showtime not found'}), 404
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Showtime deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/showtimes')
def api_showtimes():
    try:
        date_param = request.args.get('date')
        movie_id = request.args.get('movie_id')
        cinema_type = request.args.get('cinema_type')
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        query = "SELECT s.id, s.movie_id, s.show_time, s.show_date, s.cinema_type, s.price, m.title as movie_title FROM showtimes s JOIN movies m ON s.movie_id = m.id WHERE 1=1"
        params = []
        if date_param:
            query += " AND s.show_date = ?"
            params.append(date_param)
        if movie_id:
            query += " AND s.movie_id = ?"
            params.append(movie_id)
        if cinema_type:
            query += " AND s.cinema_type = ?"
            params.append(cinema_type)
        query += " ORDER BY s.show_date ASC, s.show_time ASC"
        cursor.execute(query, params)
        showtimes = [dict(st) for st in cursor.fetchall()]
        for st in showtimes:
            if st['show_date']:
                if hasattr(st['show_date'], 'strftime'):
                    st['show_date'] = st['show_date'].strftime('%Y-%m-%d')
                else:
                    st['show_date'] = str(st['show_date'])[:10]
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'showtimes': showtimes, 'date': date_param, 'movie_id': movie_id,
                        'cinema_type': cinema_type, 'count': len(showtimes)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/notify-coming-soon', methods=['POST'])
def notify_coming_soon():
    try:
        data = request.get_json()
        movie_id = data.get('movie_id')
        movie_title = data.get('movie_title')
        email = data.get('email')
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO movie_notifications (movie_id, movie_title, email) VALUES (?, ?, ?)",
                           (movie_id, movie_title, email))
            conn.commit()
            cursor.close()
            conn.close()
        return jsonify({'success': True, 'message': f'You will be notified when {movie_title} is available!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/profile')
@login_required
def profile():
    try:
        if session.get('predefined_user'):
            return render_template('profile.html',
                                   user={'username': session.get('username'), 'email': session.get('email'),
                                         'role': session.get('role'), 'created_at': 'Predefined Account',
                                         'last_login': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, bookings=[])
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username, email, role, created_at, last_login FROM users WHERE id = ?",
                           (session['user_id'],))
            user = cursor.fetchone()
            cursor.execute("SELECT * FROM bookings WHERE user_id = ? ORDER BY booking_date DESC LIMIT 10",
                           (session['user_id'],))
            bookings = cursor.fetchall()
            cursor.close()
            conn.close()
            return render_template('profile.html', user=dict(user) if user else None,
                                   bookings=[dict(b) for b in bookings])
    except Exception as e:
        print(f"Profile error: {e}")
        flash('Error loading profile', 'error')
        return redirect(url_for('index'))


@app.route('/my-bookings')
@login_required
def my_bookings():
    try:
        if session.get('predefined_user'):
            return render_template('my_bookings.html', bookings=[])
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bookings WHERE user_id = ? ORDER BY booking_date DESC", (session['user_id'],))
            bookings = cursor.fetchall()
            cursor.close()
            conn.close()
            return render_template('my_bookings.html', bookings=[dict(b) for b in bookings])
    except Exception as e:
        print(f"My bookings error: {e}")
        flash('Error loading bookings', 'error')
        return redirect(url_for('index'))


@app.route('/my-bookings/api')
@login_required
def my_bookings_api():
    try:
        if session.get('predefined_user'):
            return jsonify({'success': True, 'bookings': []})
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bookings WHERE user_id = ? ORDER BY booking_date DESC", (session['user_id'],))
            bookings = cursor.fetchall()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'bookings': [dict(b) for b in bookings]})
        else:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        if not username or not email:
            return jsonify({'success': False, 'message': 'Username and email are required'}), 400
        if session.get('predefined_user'):
            return jsonify({'success': False, 'message': 'Predefined accounts cannot be modified'}), 400
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, session['user_id']))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Email already in use'}), 400
        cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, session['user_id']))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Username already taken'}), 400
        cursor.execute("UPDATE users SET username = ?, email = ? WHERE id = ?", (username, email, session['user_id']))
        conn.commit()
        session['username'] = username
        session['email'] = email
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        if not current_password or not new_password:
            return jsonify({'success': False, 'message': 'Current password and new password are required'}), 400
        if len(new_password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters'}), 400
        if not re.search(r'[A-Za-z]', new_password) or not re.search(r'[0-9]', new_password):
            return jsonify({'success': False, 'message': 'Password must contain both letters and numbers'}), 400
        if session.get('predefined_user'):
            return jsonify({'success': False, 'message': 'Predefined accounts cannot change passwords'}), 400
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        if not check_password_hash(user['password'], current_password):
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 400
        hashed_password = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, session['user_id']))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/test-paymongo')
def test_paymongo():
    try:
        test_result = create_paymongo_checkout("TEST001", 100, "Test Payment", "http://localhost:5000/",
                                               "http://localhost:5000/")
        if test_result.get('success'):
            return jsonify({'success': True, 'message': 'PayMongo connection successful!',
                            'checkout_url': test_result['checkout_url']})
        else:
            return jsonify(
                {'success': False, 'message': f'PayMongo error: {test_result.get("error", "Unknown error")}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)