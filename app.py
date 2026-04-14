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

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this-in-production'
app.permanent_session_lifetime = timedelta(days=30)

# SQLite Database Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'db', 'cinemax.db')

# Ensure the db directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# PayMongo Configuration - USING YOUR ACTUAL KEYS
PAYMONGO_SECRET_KEY = "sk_test_LiiWAcE6qzxw1c6aone4ebVb"
PAYMONGO_PUBLIC_KEY = "pk_test_q8oEnqhZ3VfTBb5MF9DZeZLR"

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


def init_db():
    """Initialize database tables"""
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
                price DECIMAL(8,2) DEFAULT 350.00,
                FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
            )
        """)

        # Bookings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_reference VARCHAR(20) UNIQUE NOT NULL,
                user_id INTEGER,
                movie_id INTEGER NOT NULL,
                movie_title VARCHAR(255) NOT NULL,
                showtime VARCHAR(20) NOT NULL,
                show_date DATE NOT NULL,
                seats VARCHAR(255) NOT NULL,
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

        # Insert sample movies if empty
        cursor.execute("SELECT COUNT(*) as count FROM movies")
        movie_count = cursor.fetchone()['count']

        if movie_count == 0:
            print("Adding sample movies...")
            sample_movies = [
                ('The Last Voyage', 8.5, '2h 15min', '', 'Christopher Nolan', 'Visionary Director', '$450M',
                 'A thrilling adventure across the ocean. Experience the journey of a lifetime.', 1),
                ('Midnight Express', 7.8, '1h 45min', '', 'David Fincher', 'Master of Suspense', '$120M',
                 'A gripping thriller set in the night. Every shadow hides a secret.', 1),
                ('Summer Memories', 9.2, '2h 00min', '', 'Greta Gerwig', 'Award-winning Director', '$80M',
                 'A heartwarming story of friendship and love that will touch your soul.', 1),
                ('Cyber Punk 2077', 8.0, '2h 30min', '', 'Denis Villeneuve', 'Sci-fi Visionary', '$350M',
                 'The future is now in this cyberpunk adventure. Enter a world of technology and chaos.', 0),
                ('The Last Kingdom', 8.9, '2h 10min', '', 'Ridley Scott', 'Epic Storyteller', '$280M',
                 'Epic battles and royal intrigue await in this historical masterpiece.', 1),
                ('GOAT', 9.5, '2h 45min', '', 'Venkat Prabhu', 'Blockbuster Director', '$500M',
                 'The greatest of all time - an unforgettable cinematic experience.', 1),
            ]

            for movie in sample_movies:
                cursor.execute("""
                    INSERT INTO movies (title, rating, duration, poster, director, director_sub, revenue, description, is_now_showing)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, movie)
            conn.commit()
            print("Sample movies added!")

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
# PAYMONGO PAYMENT FUNCTIONS (REWRITTEN)
# ============================================================

def create_paymongo_checkout(booking_ref, amount, description, success_url, cancel_url):
    """
    Create a PayMongo Checkout Session using direct API calls.
    This is more reliable than the paymongo library.
    """
    url = "https://api.paymongo.com/v1/checkout_sessions"

    # Amount in centavos (PHP's smallest unit)
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

    # Create Basic Auth header
    auth_string = base64.b64encode(f"{PAYMONGO_SECRET_KEY}:".encode()).decode()
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Basic {auth_string}"
    }

    try:
        print(f"Creating PayMongo checkout for booking {booking_ref}, amount: ₱{amount}")

        response = requests.post(url, json=payload, headers=headers)

        print(f"Response Status: {response.status_code}")

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
                print(f"API Error: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
        else:
            error_text = response.text
            print(f"HTTP Error {response.status_code}: {error_text}")
            return {
                'success': False,
                'error': f'Payment service error (Status: {response.status_code})'
            }

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return {
            'success': False,
            'error': f'Connection error: {str(e)}'
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def retrieve_checkout_session(checkout_id):
    """Retrieve checkout session status"""
    url = f"https://api.paymongo.com/v1/checkout_sessions/{checkout_id}"

    auth_string = base64.b64encode(f"{PAYMONGO_SECRET_KEY}:".encode()).decode()
    headers = {
        "accept": "application/json",
        "authorization": f"Basic {auth_string}"
    }

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            result = response.json()
            return {
                'success': True,
                'data': result.get('data', {})
            }
        else:
            return {
                'success': False,
                'error': f"Status: {response.status_code}"
            }
    except Exception as e:
        print(f"Error retrieving checkout: {e}")
        return {'success': False, 'error': str(e)}


# ============================================================
# HELPER FUNCTIONS
# ============================================================

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


def get_showtimes_for_movie(movie_id, show_date=None):
    """Fetch showtimes for a specific movie"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            if show_date:
                cursor.execute("""
                    SELECT * FROM showtimes 
                    WHERE movie_id = ? AND show_date = ?
                    ORDER BY show_time
                """, (movie_id, show_date))
            else:
                cursor.execute("""
                    SELECT * FROM showtimes 
                    WHERE movie_id = ? 
                    ORDER BY show_time
                """, (movie_id,))
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


def get_booked_seats(movie_id, showtime, show_date):
    """Fetch booked seats for a specific show"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT seats FROM bookings 
                WHERE movie_id = ? AND showtime = ? AND show_date = ?
                AND payment_status IN ('paid', 'confirmed')
            """, (movie_id, showtime, show_date))
            bookings = cursor.fetchall()
            cursor.close()
            conn.close()

            booked_seats = []
            for booking in bookings:
                if booking['seats']:
                    booked_seats.extend(booking['seats'].split(', '))
            return booked_seats
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
    """Save booking to database"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            user_id = session.get('user_id')

            if user_id:
                cursor.execute("""
                    INSERT INTO bookings (
                        booking_reference, user_id, movie_id, movie_title, showtime, show_date, 
                        seats, number_of_tickets, total_amount, payment_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    booking_data['booking_reference'],
                    user_id,
                    booking_data['movie_id'],
                    booking_data['movie_title'],
                    booking_data['showtime'],
                    booking_data['show_date'],
                    booking_data['seats'],
                    booking_data['tickets'],
                    booking_data['total_amount'],
                    'pending'
                ))
            else:
                cursor.execute("""
                    INSERT INTO bookings (
                        booking_reference, movie_id, movie_title, showtime, show_date, 
                        seats, number_of_tickets, total_amount, payment_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    booking_data['booking_reference'],
                    booking_data['movie_id'],
                    booking_data['movie_title'],
                    booking_data['showtime'],
                    booking_data['show_date'],
                    booking_data['seats'],
                    booking_data['tickets'],
                    booking_data['total_amount'],
                    'pending'
                ))

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

            cursor.execute("""
                UPDATE bookings
                SET payment_status = ?
                WHERE booking_reference = ?
            """, (status, booking_ref))

            if status == 'paid':
                cursor.execute("""
                    UPDATE bookings
                    SET paid_at = CURRENT_TIMESTAMP
                    WHERE booking_reference = ?
                """, (booking_ref,))

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
        now_showing_movies = cursor.fetchall()
        now_showing_movies = [dict(movie) for movie in now_showing_movies]

        cursor.execute("SELECT * FROM movies WHERE is_now_showing = 0 ORDER BY id DESC")
        coming_soon_movies = cursor.fetchall()
        coming_soon_movies = [dict(movie) for movie in coming_soon_movies]

        cursor.close()
        conn.close()

        return render_template('index.html',
                               now_showing_movies=now_showing_movies,
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


@app.route('/movie/<int:movie_id>/seats')
def seat_selection(movie_id):
    showtime = request.args.get('showtime', '7:00 PM')
    tickets = request.args.get('tickets', '2')
    show_date = request.args.get('date', 'Today')
    price = request.args.get('price', '350')

    movie = get_movie_by_id(movie_id)

    if movie is None:
        return "Movie not found", 404

    booked_seats = get_booked_seats(movie_id, showtime, show_date)

    return render_template('seat_selection.html',
                           movie=movie,
                           showtime=showtime,
                           tickets=int(tickets),
                           show_date=show_date,
                           price=float(price),
                           booked_seats=booked_seats)


@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    try:
        movie_id = request.form.get('movie_id')
        movie_title = request.form.get('movie_title')
        showtime = request.form.get('showtime')
        show_date = request.form.get('show_date')
        seats = request.form.get('seats')
        tickets = request.form.get('tickets')
        total = request.form.get('total')

        if not all([movie_id, movie_title, showtime, show_date, seats, tickets, total]):
            missing = []
            if not movie_id: missing.append('movie_id')
            if not movie_title: missing.append('movie_title')
            if not showtime: missing.append('showtime')
            if not show_date: missing.append('show_date')
            if not seats: missing.append('seats')
            if not tickets: missing.append('tickets')
            if not total: missing.append('total')

            error_msg = f"Missing required fields: {', '.join(missing)}"
            print(error_msg)
            return error_msg, 400

        tickets = int(tickets)
        total = float(total)
        booking_ref = generate_booking_reference()

        booking_data = {
            'booking_reference': booking_ref,
            'movie_id': movie_id,
            'movie_title': movie_title,
            'showtime': showtime,
            'show_date': show_date,
            'seats': seats,
            'tickets': tickets,
            'total_amount': total
        }

        print(f"Saving booking: {booking_data}")

        if save_booking_to_db(booking_data):
            return render_template(
                'booking_confirmation.html',
                booking_ref=booking_ref,
                movie_id=movie_id,
                movie_title=movie_title,
                showtime=showtime,
                show_date=show_date,
                seats=seats,
                tickets=tickets,
                total=total,
                paymongo_public_key=PAYMONGO_PUBLIC_KEY
            )
        else:
            return "Error saving booking to database", 500

    except Exception as e:
        print(f"Error in confirm_booking: {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500


@app.route('/process-payment', methods=['POST'])
def process_payment():
    try:
        booking_ref = request.form.get('booking_ref')
        amount = request.form.get('amount')
        payment_method = request.form.get('payment_method')

        print(f"Payment request received: {booking_ref}, {amount}, {payment_method}")

        if not all([booking_ref, amount, payment_method]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400

        amount_float = float(amount)

        if amount_float < 100:
            return jsonify({
                'success': False,
                'message': 'Minimum payment amount is ₱100.00'
            }), 400

        base_url = request.host_url.rstrip('/')
        success_url = f"{base_url}{url_for('payment_success')}?booking_ref={booking_ref}"
        cancel_url = f"{base_url}{url_for('payment_failed')}?booking_ref={booking_ref}"

        description = f"Cinemax Booking {booking_ref}"

        result = create_paymongo_checkout(
            booking_ref=booking_ref,
            amount=amount_float,
            description=description,
            success_url=success_url,
            cancel_url=cancel_url
        )

        if result and result.get('success'):
            # Save checkout ID to database
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE bookings 
                        SET paymongo_checkout_id = ?, payment_method = ?
                        WHERE booking_reference = ?
                    """, (result['checkout_id'], payment_method, booking_ref))
                    conn.commit()
                    cursor.close()
                    conn.close()
            except Exception as e:
                print(f"Error updating booking with checkout_id: {e}")

            return jsonify({
                'success': True,
                'checkout_url': result['checkout_url'],
                'checkout_id': result['checkout_id']
            })
        else:
            error_message = result.get('error', 'Failed to create payment') if result else 'Payment creation failed'
            return jsonify({
                'success': False,
                'message': error_message
            }), 500

    except Exception as e:
        print(f"Error in process_payment: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/payment/success')
def payment_success():
    booking_ref = request.args.get('booking_ref')

    if not booking_ref:
        flash('No booking reference provided', 'error')
        return redirect(url_for('index'))

    # Update booking status to paid
    update_booking_payment_status(booking_ref, 'paid')

    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM bookings 
                WHERE booking_reference = ?
            """, (booking_ref,))
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
            cursor.execute("""
                UPDATE bookings 
                SET payment_status = 'cancelled', 
                    cancelled_at = CURRENT_TIMESTAMP,
                    cancellation_reason = ?
                WHERE booking_reference = ?
            """, (reason, booking_ref))
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


# ============================================================
# NAVIGATION ROUTES
# ============================================================

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
            coming_soon_movies = cursor.fetchall()
            cursor.close()
            conn.close()
            return render_template('coming_soon.html', coming_soon_movies=[dict(m) for m in coming_soon_movies])
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


# ============================================================
# AUTHENTICATION ROUTES
# ============================================================

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

                return jsonify({
                    'success': True,
                    'message': 'Admin login successful',
                    'redirect': url_for('admin_dashboard')
                })
            else:
                return jsonify({
                    'success': False,
                    'error_type': 'wrong_password',
                    'message': 'Wrong password'
                })

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

                    return jsonify({
                        'success': True,
                        'message': f'{employee["role"].capitalize()} login successful',
                        'redirect': redirect_url
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error_type': 'wrong_password',
                        'message': 'Wrong password'
                    })

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, password, role FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()

            if not user:
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error_type': 'email_not_found',
                    'message': 'Email does not exist. Please check your email or sign up.'
                })

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

                return jsonify({
                    'success': True,
                    'message': 'Login successful',
                    'redirect': redirect_url
                })
            else:
                cursor.close()
                conn.close()
                return jsonify({
                    'success': False,
                    'error_type': 'wrong_password',
                    'message': 'Wrong password'
                })
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

            cursor.execute("""
                INSERT INTO users (username, email, password, role, is_verified) 
                VALUES (?, ?, ?, ?, ?)
            """, (username, email, hashed_password, 'user', 1))

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

            return jsonify({
                'success': True,
                'message': 'Account created successfully',
                'redirect': url_for('index')
            })
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
            return jsonify({
                'success': False,
                'message': 'Email not found in our records.'
            })

        reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        expiry = datetime.now() + timedelta(hours=1)

        cursor.execute("""
            UPDATE users 
            SET reset_token = ?, reset_token_expiry = ? 
            WHERE id = ?
        """, (reset_token, expiry, user['id']))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Please set your new password.',
            'reset_token': reset_token
        })

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

        cursor.execute("""
            UPDATE users 
            SET password = ?, reset_token = NULL, reset_token_expiry = NULL
            WHERE id = ?
        """, (hashed_password, user['id']))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Password reset successful! You can now log in with your new password.',
            'redirect': url_for('signin')
        })

    except Exception as e:
        print(f"Error updating password: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'})


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))


# ============================================================
# ADMIN DASHBOARD ROUTES
# ============================================================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html',
                           user=session,
                           predefined_accounts=PREDEFINED_ACCOUNTS)


@app.route('/manager/dashboard')
@admin_required
def manager_dashboard():
    return render_template('manager_dashboard.html', user=session)


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

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'total_sales': float(total_sales),
            'total_movies': total_movies,
            'total_tickets': total_tickets,
            'total_bookings': total_bookings
        })

    except Exception as e:
        print(f"Error in admin_stats: {e}")
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
        movies = cursor.fetchall()
        movies = [dict(movie) for movie in movies]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'movies': movies
        })

    except Exception as e:
        print(f"Error in admin_movies: {e}")
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

        return jsonify({
            'success': True,
            'movie': dict(movie)
        })

    except Exception as e:
        print(f"Error in admin_get_movie: {e}")
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

        cursor.execute("""
            INSERT INTO movies (title, rating, duration, poster, director, description, is_now_showing)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, rating, duration, poster, director, description, is_now_showing))

        conn.commit()
        movie_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Movie added successfully',
            'movie_id': movie_id
        })

    except Exception as e:
        print(f"Error in admin_add_movie: {e}")
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

        cursor.execute("""
            UPDATE movies 
            SET title = ?, rating = ?, duration = ?, poster = ?, 
                director = ?, description = ?, is_now_showing = ?
            WHERE id = ?
        """, (title, rating, duration, poster, director, description, is_now_showing, movie_id))

        conn.commit()

        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Movie not found'}), 404

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Movie updated successfully'
        })

    except Exception as e:
        print(f"Error in admin_update_movie: {e}")
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
            return jsonify({
                'success': False,
                'message': f'Cannot delete movie with {booking_count} existing bookings.'
            }), 400

        cursor.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        conn.commit()

        if cursor.rowcount == 0:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': 'Movie not found'}), 404

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Movie deleted successfully'
        })

    except Exception as e:
        print(f"Error in admin_delete_movie: {e}")
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
        bookings = cursor.fetchall()
        bookings = [dict(booking) for booking in bookings]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'bookings': bookings
        })

    except Exception as e:
        print(f"Error in admin_bookings: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/analytics')
@admin_required
def admin_analytics():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor()

        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as total 
            FROM bookings 
            WHERE payment_status = 'paid' AND DATE(paid_at) = DATE('now')
        """)
        today_sales = cursor.fetchone()['total']

        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as total 
            FROM bookings 
            WHERE payment_status = 'paid' AND strftime('%W', paid_at) = strftime('%W', 'now')
        """)
        week_sales = cursor.fetchone()['total']

        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as total 
            FROM bookings 
            WHERE payment_status = 'paid' AND strftime('%m', paid_at) = strftime('%m', 'now')
            AND strftime('%Y', paid_at) = strftime('%Y', 'now')
        """)
        month_sales = cursor.fetchone()['total']

        cursor.execute("""
            SELECT movie_title, COUNT(*) as booking_count 
            FROM bookings 
            WHERE payment_status = 'paid'
            GROUP BY movie_title 
            ORDER BY booking_count DESC 
            LIMIT 1
        """)
        popular_movie = cursor.fetchone()
        most_popular_movie = popular_movie['movie_title'] if popular_movie else 'No data'

        cursor.execute("""
            SELECT showtime, COUNT(*) as booking_count 
            FROM bookings 
            WHERE payment_status = 'paid'
            GROUP BY showtime 
            ORDER BY booking_count DESC 
            LIMIT 1
        """)
        peak = cursor.fetchone()
        peak_time = peak['showtime'] if peak else 'No data'

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'today_sales': float(today_sales),
            'week_sales': float(week_sales),
            'month_sales': float(month_sales),
            'most_popular_movie': most_popular_movie,
            'peak_time': peak_time
        })

    except Exception as e:
        print(f"Error in admin_analytics: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/showtimes', methods=['GET'])
@admin_required
def admin_showtimes():
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, m.title as movie_title 
            FROM showtimes s
            JOIN movies m ON s.movie_id = m.id
            ORDER BY s.show_date DESC, s.show_time ASC
        """)
        showtimes = cursor.fetchall()
        showtimes = [dict(st) for st in showtimes]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'showtimes': showtimes
        })

    except Exception as e:
        print(f"Error in admin_showtimes: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/showtimes', methods=['POST'])
@admin_required
def admin_add_showtimes():
    try:
        data = request.get_json()

        movie_id = data.get('movie_id')
        show_date = data.get('show_date')
        show_times = data.get('show_times', [])
        price = data.get('price', 350)

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
            cursor.execute("""
                SELECT id FROM showtimes 
                WHERE movie_id = ? AND show_date = ? AND show_time = ?
            """, (movie_id, show_date, show_time))

            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO showtimes (movie_id, show_time, show_date, price)
                    VALUES (?, ?, ?, ?)
                """, (movie_id, show_time, show_date, price))
                added_count += 1
            else:
                skipped_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        if added_count > 0:
            message = f'{added_count} showtimes added successfully'
            if skipped_count > 0:
                message += f' ({skipped_count} skipped - already exist)'
            return jsonify({
                'success': True,
                'message': message,
                'added': added_count,
                'skipped': skipped_count
            })
        else:
            return jsonify({
                'success': False,
                'message': 'No new showtimes were added (they may already exist)'
            }), 400

    except Exception as e:
        print(f"Error in admin_add_showtimes: {e}")
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

        return jsonify({
            'success': True,
            'message': 'Showtime deleted successfully'
        })

    except Exception as e:
        print(f"Error in admin_delete_showtime: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# API ROUTES
# ============================================================

@app.route('/api/showtimes')
def api_showtimes():
    try:
        date_param = request.args.get('date')
        movie_id = request.args.get('movie_id')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor()

        query = """
            SELECT 
                s.id,
                s.movie_id,
                s.show_time,
                s.show_date,
                s.price,
                m.title as movie_title
            FROM showtimes s
            JOIN movies m ON s.movie_id = m.id
            WHERE 1=1
        """
        params = []

        if date_param:
            query += " AND s.show_date = ?"
            params.append(date_param)

        if movie_id:
            query += " AND s.movie_id = ?"
            params.append(movie_id)

        query += " ORDER BY s.show_date ASC, s.show_time ASC"

        cursor.execute(query, params)
        showtimes = cursor.fetchall()
        showtimes = [dict(st) for st in showtimes]

        for st in showtimes:
            if st['show_date']:
                if hasattr(st['show_date'], 'strftime'):
                    st['show_date'] = st['show_date'].strftime('%Y-%m-%d')
                else:
                    st['show_date'] = str(st['show_date'])[:10]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'showtimes': showtimes,
            'date': date_param,
            'movie_id': movie_id,
            'count': len(showtimes)
        })

    except Exception as e:
        print(f"Error in api_showtimes: {e}")
        import traceback
        traceback.print_exc()
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
            cursor.execute("""
                INSERT INTO movie_notifications (movie_id, movie_title, email)
                VALUES (?, ?, ?)
            """, (movie_id, movie_title, email))
            conn.commit()
            cursor.close()
            conn.close()

        return jsonify({
            'success': True,
            'message': f'You will be notified when {movie_title} is available!'
        })
    except Exception as e:
        print(f"Error in notify_coming_soon: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ============================================================
# USER PROFILE ROUTES
# ============================================================

@app.route('/profile')
@login_required
def profile():
    try:
        if session.get('predefined_user'):
            return render_template('profile.html',
                                   user={
                                       'username': session.get('username'),
                                       'email': session.get('email'),
                                       'role': session.get('role'),
                                       'created_at': 'Predefined Account',
                                       'last_login': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                   },
                                   bookings=[])

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT username, email, role, created_at, last_login 
                FROM users WHERE id = ?
            """, (session['user_id'],))
            user = cursor.fetchone()

            cursor.execute("""
                SELECT * FROM bookings 
                WHERE user_id = ? 
                ORDER BY booking_date DESC 
                LIMIT 10
            """, (session['user_id'],))
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
            cursor.execute("""
                SELECT * FROM bookings 
                WHERE user_id = ? 
                ORDER BY booking_date DESC
            """, (session['user_id'],))
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
            cursor.execute("""
                SELECT * FROM bookings 
                WHERE user_id = ? 
                ORDER BY booking_date DESC
            """, (session['user_id'],))
            bookings = cursor.fetchall()
            cursor.close()
            conn.close()

            return jsonify({
                'success': True,
                'bookings': [dict(b) for b in bookings]
            })
        else:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

    except Exception as e:
        print(f"Error in my_bookings_api: {e}")
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

        cursor.execute("""
            UPDATE users 
            SET username = ?, email = ?
            WHERE id = ?
        """, (username, email, session['user_id']))

        conn.commit()

        session['username'] = username
        session['email'] = email

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'Profile updated successfully'})

    except Exception as e:
        print(f"Error in update_profile: {e}")
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

        cursor.execute("""
            UPDATE users 
            SET password = ?
            WHERE id = ?
        """, (hashed_password, session['user_id']))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'Password changed successfully'})

    except Exception as e:
        print(f"Error in change_password: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================
# TEST ROUTE
# ============================================================

@app.route('/test-paymongo')
def test_paymongo():
    """Test PayMongo connection"""
    try:
        test_result = create_paymongo_checkout(
            booking_ref="TEST001",
            amount=100,
            description="Test Payment",
            success_url="http://localhost:5000/",
            cancel_url="http://localhost:5000/"
        )

        if test_result.get('success'):
            return jsonify({
                'success': True,
                'message': 'PayMongo connection successful!',
                'checkout_url': test_result['checkout_url']
            })
        else:
            return jsonify({
                'success': False,
                'message': f'PayMongo error: {test_result.get("error", "Unknown error")}'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)