from flask import Flask, jsonify,render_template,request,redirect,session
from database import get_db_connection
from flask import redirect
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY is missing from .env")
@app.route("/")
def home():
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT plan_id, plan_name, duration_days, price
        FROM pass_plans
        WHERE is_active = TRUE
    """)

    plans = cursor.fetchall()

    cursor.close()
    connection.close()
    
    return render_template(
        "index.html",
        plans=plans,
        logged_in=("user_id" in session)
    )
@app.route("/test-db")
def test_db():
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        database_name = cursor.fetchone()[0]
        cursor.close()

        return jsonify({
            "status": "success",
            "database": database_name
        })

    except Exception as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 500

    finally:
        if connection and connection.is_connected():
            connection.close()

@app.route("/plans")
def plans():
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT plan_id, plan_name, duration_days, price
            FROM pass_plans
            WHERE is_active = TRUE
        """)

        plans = cursor.fetchall()
        cursor.close()

        return jsonify(plans)

    except Exception as error:
        return jsonify({"error": str(error)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()

@app.route("/booking")
def booking():
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT plan_id, plan_name, duration_days, price
            FROM pass_plans
            WHERE is_active = TRUE
        """)

        plans = cursor.fetchall()
        cursor.close()

        return render_template("booking.html", plans=plans)

    except Exception as error:
        return jsonify({"error": str(error)}), 500

    finally:
        if connection and connection.is_connected():
            connection.close()

import secrets
from datetime import date, timedelta
from werkzeug.security import generate_password_hash


@app.route("/book", methods=["POST"])
def book():
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    start_date_text = request.form.get("start_date", "")
    plan_id = request.form.get("plan_id", "")

    if not full_name or not email or not start_date_text:
        return "Please fill in all required fields.", 400

    try:
        start_date = date.fromisoformat(start_date_text)
        plan_id = int(plan_id)

        if start_date < date.today():
            return "Start date cannot be in the past.", 400
    except ValueError:
        return "Invalid date or pass plan.", 400

    connection = None

    try:
        connection = get_db_connection()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            "SELECT plan_name, duration_days, price "
            "FROM pass_plans WHERE plan_id = %s AND is_active = TRUE",
            (plan_id,)
        )
        plan = cursor.fetchone()

        if not plan:
            connection.rollback()
            return "Selected pass plan is unavailable.", 400

        cursor.execute("SELECT user_id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            user_id = user["user_id"]
        else:
            # Temporary password: account registration/login will be added later.
            temporary_password = secrets.token_urlsafe(32)
            password_hash = generate_password_hash(temporary_password)

            cursor.execute(
                "INSERT INTO users (full_name, email, password_hash) "
                "VALUES (%s, %s, %s)",
                (full_name, email, password_hash)
            )
            user_id = cursor.lastrowid

        end_date = start_date + timedelta(days=plan["duration_days"] - 1)
        pass_code = "CP-" + secrets.token_hex(6).upper()

        cursor.execute("""
            INSERT INTO bus_passes
                (pass_code, user_id, plan_id, start_date, end_date, amount_paid)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            pass_code, user_id, plan_id, start_date,
            end_date, plan["price"]
        ))

        connection.commit()

        return render_template(
            "pass.html",
            pass_code=pass_code,
            full_name=full_name,
            email=email,
            plan_name=plan["plan_name"],
            start_date=start_date,
            end_date=end_date,
            amount_paid=plan["price"]
        )

    except Exception:
        if connection and connection.is_connected():
            connection.rollback()
        app.logger.exception("Booking failed")
        return "Booking could not be completed. Please try again.", 500

    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

@app.route("/my-passes", methods=["GET"])
def my_passes():
    if "user_id" not in session:
        return "Please log in first. <a href='/login'>Login</a>", 401

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                bp.pass_code,
                bp.start_date,
                bp.end_date,
                bp.amount_paid,
                bp.status,
                pp.plan_name
            FROM bus_passes bp
            JOIN pass_plans pp ON bp.plan_id = pp.plan_id
            WHERE bp.user_id = %s
            ORDER BY bp.created_at DESC
        """, (session["user_id"],))

        passes = cursor.fetchall()

        return render_template(
            "my_passes.html",
            passes=passes,
            email=""
        )

    except Exception:
        app.logger.exception("Could not retrieve passes")
        return "Unable to retrieve passes right now.", 500

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not full_name or not email or not password:
            return "All fields are required.", 400

        if len(password) < 8:
            return "Password must contain at least 8 characters.", 400

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO users (full_name, email, password_hash)
                VALUES (%s, %s, %s)
                """,
                (full_name, email, generate_password_hash(password))
            )

            connection.commit()
            return "Registration successful!"

        except Exception:
            if connection and connection.is_connected():
                connection.rollback()

            return "Registration failed. The email may already be registered.", 400

        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    return render_template("register.html")

from flask import session
from werkzeug.security import check_password_hash



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        connection = None
        cursor = None

        try:
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                "SELECT user_id, full_name, password_hash FROM users WHERE email = %s",
                (email,)
            )
            user = cursor.fetchone()

            if user and check_password_hash(user["password_hash"], password):
                session["user_id"] = user["user_id"]
                session["full_name"] = user["full_name"]
                
                return redirect("/")
            return "Invalid email or password.", 401

        except Exception:
            app.logger.exception("Login failed")
            return "Unable to log in right now.", 500

        finally:
            if cursor:
                cursor.close()
            if connection and connection.is_connected():
                connection.close()

    return render_template("login.html")
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
if __name__ == "__main__":
    app.run(debug=True)