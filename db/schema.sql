-- db/schema.sql
-- Cinemax Database Schema

-- Users table
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
);

-- Movies table
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
);

-- Showtimes table
CREATE TABLE IF NOT EXISTS showtimes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id INTEGER NOT NULL,
    show_time VARCHAR(20) NOT NULL,
    show_date DATE NOT NULL,
    price DECIMAL(8,2) DEFAULT 350.00,
    FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
);

-- Bookings table
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
);

-- Payments table
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
);

-- Movie Notifications table
CREATE TABLE IF NOT EXISTS movie_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id INTEGER,
    movie_title TEXT,
    email TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);