from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
import mysql.connector
from mysql.connector import Error
import random
import string
import json
import re
import time
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from paymongo import Paymongo
from datetime import datetime, date


app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-this-in-production'  # Change this in production
app.permanent_session_lifetime = timedelta(days=30)

# MySQL Database Configuration
db_config = {
    'host': 'localhost',
    'database': 'cinemax',
    'user': 'root',
    'password': ''  # Your MySQL password
}

# PayMongo Configuration
PAYMONGO_SECRET_KEY = os.getenv("PAYMONGO_SECRET_KEY")  # Replace with your actual test key
PAYMONGO_PUBLIC_KEY = "pk_test_q8oEnqhZ3VfTBb5MF9DZeZLR"  # Replace with your actual public key

# Predefined Admin and Employee Accounts
PREDEFINED_ACCOUNTS = {
    'admin': {
        'email': 'admin@cinemax.com',
        'password': 'Admin@123',
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

# Initialize PayMongo client
paymongo = Paymongo(PAYMONGO_SECRET_KEY)


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'predefined_user' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('signin', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'predefined_user' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('signin', next=request.url))

        # Check if user is admin or manager
        role = session.get('role')
        if role not in ['admin', 'manager']:
            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function


# Employee required decorator
def employee_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'predefined_user' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('signin', next=request.url))

        # Check if user is employee or higher
        role = session.get('role')
        if role not in ['admin', 'manager', 'employee']:
            flash('You do not have permission to access this page', 'error')
            return redirect(url_for('index'))

        return f(*args, **kwargs)

    return decorated_function


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
        # Users table for authentication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'user',
                reset_token VARCHAR(100),
                reset_token_expiry TIMESTAMP NULL,
                is_verified BOOLEAN DEFAULT FALSE,
                verification_token VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL
            )
        """)

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

        # Showtimes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS showtimes (
                id INT PRIMARY KEY AUTO_INCREMENT,
                movie_id INT NOT NULL,
                show_time VARCHAR(20) NOT NULL,
                show_date DATE NOT NULL,
                price DECIMAL(8,2) DEFAULT 350.00,
                FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
            )
        """)

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

        # Bookings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INT PRIMARY KEY AUTO_INCREMENT,
                booking_reference VARCHAR(20) UNIQUE NOT NULL,
                user_id INT,
                movie_id INT NOT NULL,
                movie_title VARCHAR(255) NOT NULL,
                showtime VARCHAR(20) NOT NULL,
                show_date DATE NOT NULL,
                seats VARCHAR(255) NOT NULL,
                number_of_tickets INT NOT NULL,
                total_amount DECIMAL(10,2) NOT NULL,
                payment_method VARCHAR(50),
                payment_status VARCHAR(50) DEFAULT 'pending',
                paymongo_payment_id VARCHAR(100),
                paymongo_source_id VARCHAR(100),
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

        # Payments table for tracking PayMongo transactions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INT PRIMARY KEY AUTO_INCREMENT,
                booking_reference VARCHAR(20) NOT NULL,
                paymongo_payment_id VARCHAR(100),
                paymongo_source_id VARCHAR(100),
                amount DECIMAL(10,2) NOT NULL,
                payment_method VARCHAR(50),
                status VARCHAR(50),
                webhook_payload JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_reference) REFERENCES bookings(booking_reference)
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


def get_showtimes_for_movie(movie_id, show_date=None):
    """Fetch showtimes for a specific movie, optionally filtered by date"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            if show_date:
                cursor.execute("""
                    SELECT * FROM showtimes 
                    WHERE movie_id = %s AND show_date = %s
                    ORDER BY show_time
                """, (movie_id, show_date))
            else:
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


def get_booked_seats(movie_id, showtime, show_date):
    """Fetch booked seats for a specific show"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT seats FROM bookings 
                WHERE movie_id = %s AND showtime = %s AND show_date = %s
                AND payment_status IN ('paid', 'pending', 'confirmed')
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
            cursor.execute("SELECT id FROM bookings WHERE booking_reference = %s", (reference,))
            existing = cursor.fetchone()
            cursor.close()
            conn.close()

            if not existing:
                return reference


def save_booking_to_db(booking_data):
    """Save booking to database with user_id"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            # Check if user is logged in
            user_id = session.get('user_id')

            if user_id:
                cursor.execute("""
                    INSERT INTO bookings (
                        booking_reference, user_id, movie_id, movie_title, showtime, show_date, 
                        seats, number_of_tickets, total_amount, payment_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                SET payment_status = %s
                WHERE booking_reference = %s
            """, (status, booking_ref))

            # If status is 'paid', update paid_at timestamp
            if status == 'paid':
                cursor.execute("""
                    UPDATE bookings
                    SET paid_at = NOW()
                    WHERE booking_reference = %s
                """, (booking_ref,))

            conn.commit()
            cursor.close()
            conn.close()
            return True
    except Exception as e:
        print("Status update error:", e)
    return False


def save_payment_record(booking_ref, payment_data, payment_method, amount):
    """Save payment record to database"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO payments (
                    booking_reference, paymongo_payment_id, paymongo_source_id,
                    amount, payment_method, status, webhook_payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                booking_ref,
                payment_data.get('id'),
                payment_data.get('source_id'),
                amount / 100,  # Convert back from centavos
                payment_method,
                payment_data.get('status', 'pending'),
                json.dumps(payment_data)
            ))

            conn.commit()
            cursor.close()
            conn.close()
            return True
    except Exception as e:
        print(f"Error saving payment record: {e}")
    return False


# PayMongo Payment Functions
def create_gcash_payment(amount, description, success_url, failure_url, booking_ref):
    """
    Create a GCash payment source using PayMongo library
    """
    try:
        # Prepare source payload for GCash
        payment_source_payload = {
            "data": {
                "attributes": {
                    "type": "gcash",
                    "amount": amount,  # In centavos
                    "currency": "PHP",
                    "redirect": {
                        "success": success_url,
                        "failed": failure_url
                    },
                    "metadata": {
                        "booking_reference": booking_ref
                    }
                }
            }
        }

        # Create source
        print(f"Creating GCash source for booking {booking_ref}...")
        response_source = paymongo.sources.create(payment_source_payload)

        payment_source_id = response_source['id']
        checkout_url = response_source['attributes']['redirect']['checkout_url']

        print(f"Source created: {payment_source_id}")
        print(f"Checkout URL: {checkout_url}")

        return {
            'success': True,
            'source_id': payment_source_id,
            'checkout_url': checkout_url,
            'response': response_source
        }

    except Exception as e:
        print(f"PayMongo GCash creation error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def create_grab_pay_payment(amount, description, success_url, failure_url, booking_ref):
    """
    Create a GrabPay payment source using PayMongo library
    """
    try:
        # Prepare source payload for GrabPay
        payment_source_payload = {
            "data": {
                "attributes": {
                    "type": "grab_pay",
                    "amount": amount,  # In centavos
                    "currency": "PHP",
                    "redirect": {
                        "success": success_url,
                        "failed": failure_url
                    },
                    "metadata": {
                        "booking_reference": booking_ref
                    }
                }
            }
        }

        # Create source
        print(f"Creating GrabPay source for booking {booking_ref}...")
        response_source = paymongo.sources.create(payment_source_payload)

        payment_source_id = response_source['id']
        checkout_url = response_source['attributes']['redirect']['checkout_url']

        return {
            'success': True,
            'source_id': payment_source_id,
            'checkout_url': checkout_url,
            'response': response_source
        }

    except Exception as e:
        print(f"PayMongo GrabPay creation error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def create_card_payment_intent(amount, description, booking_ref):
    """
    Create a card payment intent using PayMongo library
    """
    try:
        # Create payment intent
        payment_intent_payload = {
            "data": {
                "attributes": {
                    "amount": amount,
                    "payment_method_allowed": ["card"],
                    "description": description,
                    "statement_descriptor": "CINEMAX",
                    "payment_method_options": {
                        "card": {
                            "request_three_d_secure": "automatic"
                        }
                    },
                    "currency": "PHP",
                    "metadata": {
                        "booking_reference": booking_ref
                    }
                }
            }
        }

        print(f"Creating card payment intent for booking {booking_ref}...")
        intent_response = paymongo.payment_intents.create(payment_intent_payload)

        intent_id = intent_response['id']
        client_key = intent_response['attributes']['client_key']

        return {
            'success': True,
            'intent_id': intent_id,
            'client_key': client_key,
            'response': intent_response
        }

    except Exception as e:
        print(f"PayMongo card payment error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def attach_payment_method_to_intent(intent_id, payment_method_id):
    """
    Attach a payment method to a payment intent
    """
    try:
        attach_payload = {
            "data": {
                "attributes": {
                    "payment_method": payment_method_id
                }
            }
        }

        result = paymongo.payment_intents.attach(intent_id, attach_payload)
        return {
            'success': True,
            'response': result
        }
    except Exception as e:
        print(f"Error attaching payment method: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def create_payment_method(card_details):
    """
    Create a payment method for card
    """
    try:
        payment_method_payload = {
            "data": {
                "attributes": {
                    "type": "card",
                    "details": {
                        "card_number": card_details['card_number'],
                        "exp_month": int(card_details['exp_month']),
                        "exp_year": int(card_details['exp_year']),
                        "cvc": card_details['cvc']
                    }
                }
            }
        }

        result = paymongo.payment_methods.create(payment_method_payload)
        return {
            'success': True,
            'payment_method_id': result['id'],
            'response': result
        }
    except Exception as e:
        print(f"Error creating payment method: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def process_payment_completion(source_id, amount, description, booking_ref):
    """
    Complete the payment after source is paid
    """
    try:
        # Wait a bit for the payment to be processed
        time.sleep(15)

        # Create payment using the source
        payment_payload = {
            "data": {
                "attributes": {
                    "description": description,
                    "statement_descriptor": "CINEMAX",
                    "amount": amount,
                    "currency": "PHP",
                    "source": {
                        "id": source_id,
                        "type": "source"
                    },
                    "metadata": {
                        "booking_reference": booking_ref
                    }
                }
            }
        }

        payment_response = paymongo.payments.create(payment_payload)

        return {
            'success': True,
            'payment_id': payment_response['id'],
            'response': payment_response
        }

    except Exception as e:
        print(f"Payment completion error: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# Home Routes
@app.route('/')
def index():
    """Home page with now showing and coming soon movies"""
    try:
        conn = get_db_connection()
        if not conn:
            return render_template('index.html', now_showing_movies=[], coming_soon_movies=[])

        cursor = conn.cursor(dictionary=True)

        # Get now showing movies
        cursor.execute("SELECT * FROM movies WHERE is_now_showing = 1 ORDER BY id DESC")
        now_showing_movies = cursor.fetchall()

        # Get coming soon movies
        cursor.execute("SELECT * FROM movies WHERE is_now_showing = 0 ORDER BY id DESC")
        coming_soon_movies = cursor.fetchall()

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

    # Set default poster if none exists
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
        # Get data from the form submission
        movie_id = request.form.get('movie_id')
        movie_title = request.form.get('movie_title')
        showtime = request.form.get('showtime')
        show_date = request.form.get('show_date')
        seats = request.form.get('seats')
        tickets = request.form.get('tickets')
        total = request.form.get('total')

        # Validate required fields
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

        # Convert to appropriate types
        tickets = int(tickets)
        total = float(total)

        # Generate unique booking reference
        booking_ref = generate_booking_reference()

        # Prepare booking data
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

        print(f"Saving booking: {booking_data}")  # Debug print

        # Save to database
        if save_booking_to_db(booking_data):
            # Pass ALL required variables to the template
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
                paymongo_public_key=PAYMONGO_PUBLIC_KEY  # Add this if you need it
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

        amount_centavos = int(float(amount) * 100)

        if amount_centavos < 10000:  # Minimum ₱100
            return jsonify({
                'success': False,
                'message': 'Minimum payment amount is ₱100.00'
            }), 400

        # IMPORTANT: Use your existing payment success/failed endpoints
        # NOT /paymongo_checkout
        base_url = request.host_url.rstrip('/')
        success_url = f"{base_url}{url_for('payment_success', booking_ref=booking_ref)}"
        failure_url = f"{base_url}{url_for('payment_failed', booking_ref=booking_ref)}"

        print(f"Success URL: {success_url}")
        print(f"Failure URL: {failure_url}")

        description = f"Cinemax Booking {booking_ref}"

        # For now, default to GCash
        result = create_gcash_payment(
            amount=amount_centavos,
            description=description,
            success_url=success_url,
            failure_url=failure_url,
            booking_ref=booking_ref
        )

        if result and result.get('success'):
            # Update booking with source ID
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE bookings 
                        SET paymongo_source_id = %s, payment_method = %s
                        WHERE booking_reference = %s
                    """, (result['source_id'], 'gcash', booking_ref))
                    conn.commit()
                    cursor.close()
                    conn.close()
            except Exception as e:
                print(f"Error updating booking with source_id: {e}")

            # Save payment record
            save_payment_record(booking_ref, result['response'], 'gcash', amount_centavos)

            return jsonify({
                'success': True,
                'checkout_url': result['checkout_url'],
                'source_id': result['source_id']
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


@app.route('/create-payment-method', methods=['POST'])
def create_payment_method_route():
    """Create a payment method for card payments"""
    try:
        data = request.json
        card_details = data.get('data', {}).get('attributes', {}).get('details', {})

        result = create_payment_method(card_details)

        if result['success']:
            return jsonify({
                'success': True,
                'payment_method_id': result['payment_method_id']
            })
        else:
            return jsonify({
                'success': False,
                'message': result['error']
            }), 400

    except Exception as e:
        print(f"Error in create_payment_method: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/attach-payment-method', methods=['POST'])
def attach_payment_method():
    """Attach payment method to intent"""
    try:
        intent_id = request.form.get('intent_id')
        payment_method_id = request.form.get('payment_method_id')
        booking_ref = request.form.get('booking_ref')

        result = attach_payment_method_to_intent(intent_id, payment_method_id)

        if result['success']:
            update_booking_payment_status(booking_ref, 'paid')
            return jsonify({
                'success': True,
                'message': 'Payment successful'
            })
        else:
            return jsonify({
                'success': False,
                'message': result['error']
            }), 400

    except Exception as e:
        print(f"Error attaching payment method: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/payment/success')
def payment_success():
    booking_ref = request.args.get('booking_ref')

    # Check if we have a source ID to complete payment
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM bookings 
                WHERE booking_reference = %s
            """, (booking_ref,))
            booking = cursor.fetchone()
            cursor.close()

            if booking and booking.get('paymongo_source_id'):
                # Complete the payment for e-wallets
                amount = int(float(booking['total_amount']) * 100)
                result = process_payment_completion(
                    source_id=booking['paymongo_source_id'],
                    amount=amount,
                    description=f"Cinemax Booking {booking_ref}",
                    booking_ref=booking_ref
                )

                if result['success']:
                    update_booking_payment_status(booking_ref, 'paid')
                    save_payment_record(booking_ref, result['response'], booking['payment_method'], amount)

            conn.close()
    except Exception as e:
        print(f"Error in payment success: {e}")

    # Update status to paid
    update_booking_payment_status(booking_ref, 'paid')

    # Fetch updated booking
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM bookings 
                WHERE booking_reference = %s
            """, (booking_ref,))
            booking = cursor.fetchone()
            cursor.close()
            conn.close()

            if booking:
                return render_template('payment_success.html', booking=booking)
    except Exception as e:
        print(f"Error fetching booking: {e}")

    return render_template('payment_success.html', booking_ref=booking_ref)


@app.route('/payment/failed')
def payment_failed():
    booking_ref = request.args.get('booking_ref')
    update_booking_payment_status(booking_ref, 'failed')
    return render_template('payment_failed.html', booking_ref=booking_ref)


@app.route('/paymongo-webhook', methods=['POST'])
def paymongo_webhook():
    """
    Handle PayMongo webhooks for payment status updates
    """
    payload = request.json

    if payload and 'data' in payload:
        event_type = payload['data']['attributes']['type']
        event_data = payload['data']['attributes']['data']

        print(f"Webhook received: {event_type}")

        # Extract booking reference from metadata
        booking_ref = None
        if 'attributes' in event_data and 'metadata' in event_data['attributes']:
            booking_ref = event_data['attributes']['metadata'].get('booking_reference')

        if event_type == 'source.chargeable':
            # Source is ready to be charged
            source_id = event_data['id']
            amount = event_data['attributes']['amount']

            if booking_ref:
                # Complete the payment
                result = process_payment_completion(
                    source_id=source_id,
                    amount=amount,
                    description=f"Cinemax Booking {booking_ref}",
                    booking_ref=booking_ref
                )

                if result['success']:
                    print(f"Payment completed for booking {booking_ref}")

        elif event_type == 'payment.paid':
            # Payment succeeded
            payment_id = event_data['id']
            if booking_ref:
                update_booking_payment_status(booking_ref, 'paid')
                print(f"Payment successful: {payment_id} for booking {booking_ref}")

        elif event_type == 'payment.failed':
            # Payment failed
            payment_id = event_data['id']
            if booking_ref:
                update_booking_payment_status(booking_ref, 'failed')
                print(f"Payment failed: {payment_id} for booking {booking_ref}")

    return jsonify({"status": "received"}), 200


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
                    cancelled_at = NOW(),
                    cancellation_reason = %s
                WHERE booking_reference = %s
            """, (reason, booking_ref))
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True})
    except Exception as e:
        print(f"Error cancelling booking: {e}")

    return jsonify({'success': False}), 500


@app.route('/mark-paid-cash', methods=['POST'])
@login_required  # optional, but probably want teller to be logged in
def mark_paid_cash():
    booking_ref = request.form.get('booking_ref')
    if not booking_ref:
        return jsonify({'success': False, 'message': 'Missing booking reference'})
    if update_booking_payment_status(booking_ref, 'paid'):
        return jsonify({'success': True, 'message': 'Payment recorded'})
    else:
        return jsonify({'success': False, 'message': 'Database error'})


# Navigation Routes
@app.route('/showtimes')
def showtimes():
    """Showtimes page"""
    return render_template('showtimes.html')


@app.route('/coming-soon')
def coming_soon():
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
    # If user is already logged in, redirect to home
    if 'user_id' in session or 'predefined_user' in session:
        return redirect(url_for('index'))
    return render_template('signin.html')


@app.route('/login', methods=['POST'])
def login():
    """Handle user login with JSON response for AJAX - UPDATED with specific error messages"""
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'

        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required'})

        # First check predefined admin/employee accounts
        # Check admin account
        if email == PREDEFINED_ACCOUNTS['admin']['email']:
            if password == PREDEFINED_ACCOUNTS['admin']['password']:
                # Set session for predefined admin
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
                # Admin email found but wrong password
                return jsonify({
                    'success': False,
                    'error_type': 'wrong_password',
                    'message': 'Wrong password'
                })

        # Check employee accounts
        for employee in PREDEFINED_ACCOUNTS['employees']:
            if email == employee['email']:
                if password == employee['password']:
                    # Set session for predefined employee
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
                    # Employee email found but wrong password
                    return jsonify({
                        'success': False,
                        'error_type': 'wrong_password',
                        'message': 'Wrong password'
                    })

        # If not found in predefined, check database
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT id, username, email, password, role FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if not user:
                cursor.close()
                conn.close()
                # Email not found in database either
                return jsonify({
                    'success': False,
                    'error_type': 'email_not_found',
                    'message': 'Email does not exist. Please check your email or sign up.'
                })

            # Check password
            if check_password_hash(user['password'], password):
                # Set session for database user
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['email'] = user['email']
                session['role'] = user.get('role', 'user')

                if remember:
                    session.permanent = True

                # Update last login
                cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))
                conn.commit()

                cursor.close()
                conn.close()

                # Check for next parameter
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
                # Email exists but wrong password
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
    """Handle user registration with JSON response for AJAX"""
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        terms = request.form.get('terms')

        # Validation
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

        # Email validation
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return jsonify({'success': False, 'message': 'Invalid email format'})

        # Check if email belongs to predefined account (prevent duplication)
        if email == PREDEFINED_ACCOUNTS['admin']['email']:
            return jsonify({'success': False, 'message': 'This email is reserved for admin use'})

        for employee in PREDEFINED_ACCOUNTS['employees']:
            if email == employee['email']:
                return jsonify({'success': False, 'message': 'This email is reserved for employee use'})

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)

            # Check email
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Email already registered'})

            # Check username
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'success': False, 'message': 'Username already taken'})

            # Hash password and create user
            hashed_password = generate_password_hash(password)

            cursor.execute("""
                INSERT INTO users (username, email, password, role, is_verified) 
                VALUES (%s, %s, %s, %s, %s)
            """, (username, email, hashed_password, 'user', True))  # Set verified to True for now

            conn.commit()

            # Get the newly created user
            cursor.execute("SELECT id, username, email FROM users WHERE email = %s", (email,))
            new_user = cursor.fetchone()

            if new_user:
                # Set session
                session['user_id'] = new_user['id']
                session['username'] = new_user['username']
                session['email'] = new_user['email']
                session['role'] = 'user'
                session.permanent = True

                # Update last login
                cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (new_user['id'],))
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
    """Handle password reset request"""
    try:
        email = request.form.get('email')

        if not email:
            return jsonify({'success': False, 'message': 'Email is required'})

        # Check if email is predefined (can't reset predefined passwords)
        if email == PREDEFINED_ACCOUNTS['admin']['email']:
            return jsonify({
                'success': True,
                'message': 'If your email is registered, you will receive a password reset link'
            })

        for employee in PREDEFINED_ACCOUNTS['employees']:
            if email == employee['email']:
                return jsonify({
                    'success': True,
                    'message': 'If your email is registered, you will receive a password reset link'
                })

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user:
                # Generate reset token
                reset_token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                expiry = datetime.now() + timedelta(hours=1)

                cursor.execute("""
                    UPDATE users 
                    SET reset_token = %s, reset_token_expiry = %s 
                    WHERE id = %s
                """, (reset_token, expiry, user['id']))
                conn.commit()

                # Here you would send an email with the reset link
                print(f"Reset token for {email}: {reset_token}")

            cursor.close()
            conn.close()

            # Always return success to prevent email enumeration
            return jsonify({
                'success': True,
                'message': 'If your email is registered, you will receive a password reset link'
            })
        else:
            return jsonify({'success': False, 'message': 'Database connection error'})

    except Exception as e:
        print(f"Reset password error: {e}")
        return jsonify({'success': False, 'message': 'An error occurred'})


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))


# Admin and Employee Dashboard Routes
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard"""
    return render_template('admin_dashboard.html',
                           user=session,
                           predefined_accounts=PREDEFINED_ACCOUNTS)


@app.route('/manager/dashboard')
@admin_required
def manager_dashboard():
    """Manager dashboard"""
    return render_template('manager_dashboard.html', user=session)


@app.route('/employee/dashboard')
@employee_required
def employee_dashboard():
    """Employee dashboard"""
    return render_template('employee_dashboard.html', user=session)


# ==================== ADMIN DASHBOARD API ROUTES ====================

@app.route('/admin/stats')
@admin_required
def admin_stats():
    """Get dashboard statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor(dictionary=True)

        # Total sales (from paid bookings)
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0) as total FROM bookings WHERE payment_status = 'paid'")
        total_sales = cursor.fetchone()['total']

        # Total movies
        cursor.execute("SELECT COUNT(*) as count FROM movies")
        total_movies = cursor.fetchone()['count']

        # Total tickets sold
        cursor.execute(
            "SELECT COALESCE(SUM(number_of_tickets), 0) as total FROM bookings WHERE payment_status = 'paid'")
        total_tickets = cursor.fetchone()['total']

        # Total bookings
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
    """Get all movies for admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM movies ORDER BY id DESC")
        movies = cursor.fetchall()

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
    """Get a single movie for editing"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
        movie = cursor.fetchone()

        cursor.close()
        conn.close()

        if not movie:
            return jsonify({'success': False, 'message': 'Movie not found'}), 404

        return jsonify({
            'success': True,
            'movie': movie
        })

    except Exception as e:
        print(f"Error in admin_get_movie: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/admin/movie', methods=['POST'])
@admin_required
def admin_add_movie():
    """Add a new movie"""
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
            VALUES (%s, %s, %s, %s, %s, %s, %s)
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
    """Update an existing movie"""
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
            SET title = %s, rating = %s, duration = %s, poster = %s, 
                director = %s, description = %s, is_now_showing = %s
            WHERE id = %s
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
    """Delete a movie"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor()

        # Check if movie has bookings
        cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE movie_id = %s", (movie_id,))
        booking_count = cursor.fetchone()[0]

        if booking_count > 0:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': f'Cannot delete movie with {booking_count} existing bookings. Please cancel bookings first.'
            }), 400

        cursor.execute("DELETE FROM movies WHERE id = %s", (movie_id,))
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
    """Get all bookings for admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM bookings 
            ORDER BY booking_date DESC
        """)
        bookings = cursor.fetchall()

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
    """Get analytics data"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor(dictionary=True)

        # Today's sales
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as total 
            FROM bookings 
            WHERE payment_status = 'paid' AND DATE(paid_at) = CURDATE()
        """)
        today_sales = cursor.fetchone()['total']

        # This week's sales
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as total 
            FROM bookings 
            WHERE payment_status = 'paid' AND YEARWEEK(paid_at) = YEARWEEK(CURDATE())
        """)
        week_sales = cursor.fetchone()['total']

        # This month's sales
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as total 
            FROM bookings 
            WHERE payment_status = 'paid' AND MONTH(paid_at) = MONTH(CURDATE()) 
            AND YEAR(paid_at) = YEAR(CURDATE())
        """)
        month_sales = cursor.fetchone()['total']

        # Average ticket price
        cursor.execute("""
            SELECT COALESCE(AVG(total_amount / number_of_tickets), 0) as avg_price 
            FROM bookings 
            WHERE payment_status = 'paid' AND number_of_tickets > 0
        """)
        avg_ticket_price = cursor.fetchone()['avg_price']

        # Most popular movie
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

        # Peak showtime
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
            'avg_ticket_price': f"{float(avg_ticket_price):.2f}",
            'most_popular_movie': most_popular_movie,
            'peak_time': peak_time
        })

    except Exception as e:
        print(f"Error in admin_analytics: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ==================== SHOWTIME MANAGEMENT ROUTES ====================

@app.route('/admin/showtimes', methods=['GET'])
@admin_required
def admin_showtimes():
    """Get all showtimes for admin"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, m.title as movie_title 
            FROM showtimes s
            JOIN movies m ON s.movie_id = m.id
            ORDER BY s.show_date DESC, s.show_time ASC
        """)
        showtimes = cursor.fetchall()

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
    """Add multiple showtimes for a movie"""
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
            # Check if showtime already exists
            cursor.execute("""
                SELECT id FROM showtimes 
                WHERE movie_id = %s AND show_date = %s AND show_time = %s
            """, (movie_id, show_date, show_time))

            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO showtimes (movie_id, show_time, show_date, price)
                    VALUES (%s, %s, %s, %s)
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
    """Delete a showtime"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor()

        # Check if showtime has any bookings
        cursor.execute("""
            SELECT COUNT(*) as count FROM bookings 
            WHERE movie_id = (SELECT movie_id FROM showtimes WHERE id = %s)
            AND showtime = (SELECT show_time FROM showtimes WHERE id = %s)
            AND show_date = (SELECT show_date FROM showtimes WHERE id = %s)
        """, (showtime_id, showtime_id, showtime_id))

        booking_count = cursor.fetchone()[0]

        if booking_count > 0:
            cursor.close()
            conn.close()
            return jsonify({
                'success': False,
                'message': f'Cannot delete showtime with {booking_count} existing bookings'
            }), 400

        cursor.execute("DELETE FROM showtimes WHERE id = %s", (showtime_id,))
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


# ==================== API ROUTES ====================

@app.route('/api/showtimes')
def api_showtimes():
    """API endpoint to get showtimes for a specific date or movie"""
    try:
        date_param = request.args.get('date')
        movie_id = request.args.get('movie_id')

        print(f"=== API SHOWTIMES CALL ===")
        print(f"Date parameter: {date_param}")
        print(f"Movie ID parameter: {movie_id}")

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'message': 'Database connection error'}), 500

        cursor = conn.cursor(dictionary=True)

        # Build query based on parameters
        query = """
            SELECT 
                s.id,
                s.movie_id,
                s.show_time,
                s.show_date,
                s.price,
                m.title as movie_title,
                m.rating as movie_rating,
                m.duration as movie_duration,
                m.poster as movie_poster,
                m.description as movie_description,
                'Cinemax Mall' as cinema_name,
                '2D' as format
            FROM showtimes s
            JOIN movies m ON s.movie_id = m.id
            WHERE 1=1
        """
        params = []

        if date_param:
            query += " AND s.show_date = %s"
            params.append(date_param)
            print(f"Filtering by date: {date_param}")

        if movie_id:
            query += " AND s.movie_id = %s"
            params.append(movie_id)
            print(f"Filtering by movie_id: {movie_id}")

        query += " ORDER BY s.show_date ASC, s.show_time ASC"

        print(f"Executing query: {query}")
        print(f"With params: {params}")

        cursor.execute(query, params)
        showtimes = cursor.fetchall()

        # Format the dates to YYYY-MM-DD string
        for st in showtimes:
            if st['show_date']:
                # Check if it's a date object by checking for strftime method
                if hasattr(st['show_date'], 'strftime'):
                    # It's a date/datetime object
                    st['show_date'] = st['show_date'].strftime('%Y-%m-%d')
                else:
                    # It's already a string, extract the first 10 characters (YYYY-MM-DD)
                    st['show_date'] = str(st['show_date'])[:10]

        print(f"Query returned {len(showtimes)} showtimes")
        for st in showtimes:
            print(f"  Result: ID={st['id']}, Date={st['show_date']}, Time={st['show_time']}, Price={st['price']}")

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

# User Profile Route (protected)
@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    try:
        # Check if predefined user
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
            cursor = conn.cursor(dictionary=True)

            # Get user details
            cursor.execute("""
                SELECT username, email, role, created_at, last_login 
                FROM users WHERE id = %s
            """, (session['user_id'],))
            user = cursor.fetchone()

            # Get user's bookings
            cursor.execute("""
                SELECT * FROM bookings 
                WHERE user_id = %s 
                ORDER BY booking_date DESC 
                LIMIT 10
            """, (session['user_id'],))
            bookings = cursor.fetchall()

            cursor.close()
            conn.close()

            return render_template('profile.html', user=user, bookings=bookings)
    except Exception as e:
        print(f"Profile error: {e}")
        flash('Error loading profile', 'error')
        return redirect(url_for('index'))


# My Bookings Route (protected)
@app.route('/my-bookings')
@login_required
def my_bookings():
    """View user's bookings"""
    try:
        # Check if predefined user
        if session.get('predefined_user'):
            return render_template('my_bookings.html', bookings=[])

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT * FROM bookings 
                WHERE user_id = %s 
                ORDER BY booking_date DESC
            """, (session['user_id'],))
            bookings = cursor.fetchall()
            cursor.close()
            conn.close()

            return render_template('my_bookings.html', bookings=bookings)
    except Exception as e:
        print(f"My bookings error: {e}")
        flash('Error loading bookings', 'error')
        return redirect(url_for('index'))


# Test route for PayMongo
@app.route('/test-paymongo')
def test_paymongo():
    """Test route to verify PayMongo connection"""
    try:
        # Test creating a simple source
        test_payload = {
            "data": {
                "attributes": {
                    "type": "gcash",
                    "amount": 10000,
                    "currency": "PHP",
                    "redirect": {
                        "success": "https://example.com/success",
                        "failed": "https://example.com/failed"
                    }
                }
            }
        }

        response = paymongo.sources.create(test_payload)

        return jsonify({
            'success': True,
            'message': 'PayMongo connection successful',
            'response': response
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/paymongo_checkout')
def paymongo_checkout():
    """
    Handle PayMongo checkout redirect
    PayMongo redirects to this URL after GCash payment
    """
    ref = request.args.get('ref')

    print(f"=== PAYMONGO CHECKOUT CALLBACK ===")
    print(f"Reference received: {ref}")
    print(f"Full URL: {request.url}")
    print(f"All args: {request.args}")

    if not ref:
        return "No reference provided", 400

    # Try to find the booking - ref might be the source ID or payment intent ID
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)

            # Try to find booking by paymongo_source_id first
            cursor.execute("""
                SELECT booking_reference FROM bookings 
                WHERE paymongo_source_id = %s
            """, (ref,))

            booking = cursor.fetchone()

            if booking:
                booking_ref = booking['booking_reference']
                print(f"Found booking by source ID: {booking_ref}")
            else:
                # If not found, assume ref is the booking reference
                booking_ref = ref
                print(f"Using ref as booking reference: {booking_ref}")

            cursor.close()
            conn.close()

            # Update payment status
            update_booking_payment_status(booking_ref, 'paid')

            # Redirect to your success page
            return redirect(url_for('payment_success', booking_ref=booking_ref))

    except Exception as e:
        print(f"Error in paymongo_checkout: {e}")
        import traceback
        traceback.print_exc()

    # If all else fails, redirect to the success page anyway
    return redirect(url_for('payment_success', booking_ref=ref))


@app.route('/paymongo_checkout', methods=['POST'])
def paymongo_webhook_checkout():
    """
    Handle PayMongo webhooks sent to /paymongo_checkout
    This matches your PayMongo dashboard configuration
    """
    payload = request.json

    print("=== PAYMONGO WEBHOOK RECEIVED ===")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    if payload and 'data' in payload:
        event_type = payload['data']['attributes']['type']
        event_data = payload['data']['attributes']['data']

        print(f"Event Type: {event_type}")

        # Extract booking reference from metadata
        booking_ref = None
        if 'attributes' in event_data and 'metadata' in event_data['attributes']:
            booking_ref = event_data['attributes']['metadata'].get('booking_reference')

        print(f"Booking Reference: {booking_ref}")

        if event_type == 'source.chargeable':
            # Source is ready to be charged
            source_id = event_data['id']
            amount = event_data['attributes']['amount']

            if booking_ref:
                # Complete the payment
                result = process_payment_completion(
                    source_id=source_id,
                    amount=amount,
                    description=f"Cinemax Booking {booking_ref}",
                    booking_ref=booking_ref
                )

                if result['success']:
                    update_booking_payment_status(booking_ref, 'paid')
                    print(f"Payment completed for booking {booking_ref}")
                else:
                    print(f"Payment completion failed: {result.get('error')}")

        elif event_type == 'payment.paid':
            # Payment succeeded
            payment_id = event_data['id']
            if booking_ref:
                update_booking_payment_status(booking_ref, 'paid')
                print(f"Payment successful: {payment_id} for booking {booking_ref}")

        elif event_type == 'payment.failed':
            # Payment failed
            payment_id = event_data['id']
            if booking_ref:
                update_booking_payment_status(booking_ref, 'failed')
                print(f"Payment failed: {payment_id} for booking {booking_ref}")

        elif event_type == 'source.failed':
            # Source creation failed
            if booking_ref:
                update_booking_payment_status(booking_ref, 'failed')
                print(f"Source failed for booking {booking_ref}")

    # Return 200 OK to acknowledge receipt
    return jsonify({"status": "received"}), 200


# Also add a GET handler for redirects (if PayMongo redirects here)
@app.route('/paymongo_checkout', methods=['GET'])
def paymongo_checkout_redirect():
    """
    Handle PayMongo redirects after payment
    """
    ref = request.args.get('ref')
    payment_intent_id = request.args.get('payment_intent_id')
    source_id = request.args.get('source_id')

    print("=== PAYMONGO REDIRECT RECEIVED ===")
    print(f"Ref: {ref}")
    print(f"Payment Intent ID: {payment_intent_id}")
    print(f"Source ID: {source_id}")
    print(f"All args: {request.args}")

    # Try to find the booking
    booking_ref = None

    if ref:
        # Try to find booking by reference
        booking_ref = ref
    elif payment_intent_id or source_id:
        # Try to find booking by payment/source ID
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)

                if payment_intent_id:
                    cursor.execute("""
                        SELECT booking_reference FROM bookings 
                        WHERE paymongo_payment_id = %s
                    """, (payment_intent_id,))
                elif source_id:
                    cursor.execute("""
                        SELECT booking_reference FROM bookings 
                        WHERE paymongo_source_id = %s
                    """, (source_id,))

                booking = cursor.fetchone()
                if booking:
                    booking_ref = booking['booking_reference']

                cursor.close()
                conn.close()
        except Exception as e:
            print(f"Error finding booking: {e}")

    if booking_ref:
        # Update payment status
        update_booking_payment_status(booking_ref, 'paid')

        # Redirect to success page
        return redirect(url_for('payment_success', booking_ref=booking_ref))
    else:
        # If we can't find the booking, redirect to home with error
        flash('Payment completed but we could not verify your booking. Please contact support.', 'warning')
        return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)