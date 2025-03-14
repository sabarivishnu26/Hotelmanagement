from flask import Flask
from flask import render_template, request, redirect, url_for, session, flash,jsonify
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from functools import wraps

app = Flask(__name__)
app.secret_key = '1234567890'

mysql = MySQL(app)
login_manager = LoginManager(app)


app.config['MYSQL_HOST'] = '127.0.0.1'  
app.config['MYSQL_USER'] = 'newuser'       
app.config['MYSQL_PASSWORD'] = 'newuser'  
app.config['MYSQL_DB'] = 'hotel'

class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT UsersID, Username, Role FROM users WHERE UsersID = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    if user:
        return User(user[0], user[1], user[2])
    return None

# Role-based access decorator


def admin_required(f):
    @wraps(f)  # This preserves the function name
    def wrapper(*args, **kwargs):
        if current_user.is_authenticated and current_user.role == 'admin':
            return f(*args, **kwargs)
        return jsonify({"error": "Unauthorized"}), 403
    return wrapper

@app.route("/login", methods=['POST','GET'])
def login():
    if request.method == 'POST':
        username = request.form.get('Username')
        password = request.form.get('password')

        if not username or not password:
            flash("Username and password required", "danger")
            return redirect(url_for("login"))

        cur = mysql.connection.cursor()
        cur.execute("SELECT UsersID, Username, Password, Role FROM users WHERE Username = %s", (username,))
        user = cur.fetchone()
        print(user[2])
        print(password)
        cur.close()

        if user[2]==password:
            user_obj = User(user[0], user[1], user[3])  
            print("u")
            login_user(user_obj)
            return redirect(url_for('home'))  

        flash("Invalid username or password", "danger")
        return redirect(url_for('login'))  # Stay on login page if failed

    return render_template('login.html')


@app.route('/home')
def home():
    return render_template('index.html')

@app.route("/signup", methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        username = request.form.get("Username")
        password = request.form.get("password")
        role = request.form.get("role")  # Default role selection

        if not username or not password:
            flash("Username and password required", "danger")
            return redirect(url_for("signup"))

        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO users (Username, Password, Role) VALUES (%s, %s, %s)",
                (username, password, role),
            )
            mysql.connection.commit()
            cur.close()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            flash("Username already exists or error in signup.", "danger")
            return redirect(url_for("signup"))

    return render_template("register.html")

@app.route('/roombooking/customer',methods=['GET','POST'])
@login_required
def roombooking():
    if request.method == 'POST':
        session['Name'] = request.form.get('Name')
        session['CustomerContact'] = request.form.get('ContactNumber')
        session['Email'] = request.form.get('Email')
        session['Address'] = request.form.get('Address')

        return redirect(url_for('room_availability'))
    
    return render_template('customer.html')

@app.route('/roombooking/customer/room_availability', methods=['GET', 'POST'])
@login_required
def room_availability():
    if request.method == 'POST':
        room_type = request.form.get('RoomType')
        checkin_date = request.form.get('CheckinDate')
        checkout_date = request.form.get('CheckoutDate')

        if not room_type or not checkin_date or not checkout_date:
            flash("Please fill in all required fields.")
            return redirect(url_for('room_availability'))

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT PricePerNight FROM rooms WHERE RoomType = %s", (room_type,))
            price_per_night = cur.fetchone()

            if price_per_night:
                price_per_night = price_per_night[0]
                total_days = (datetime.strptime(checkout_date, '%Y-%m-%d') - datetime.strptime(checkin_date, '%Y-%m-%d')).days
                if total_days <= 0:
                    flash("Checkout date must be after check-in date.")
                    return redirect(url_for('room_availability'))

                total_amount = total_days * float(price_per_night)
                session['TotalAmount'] = total_amount  # ✅ Set TotalAmount before redirecting
                print(session['TotalAmount'])
                flash(f"Total amount calculated: {total_amount}")
            else:
                flash("Room type not found. Please select a valid room type.")
                return redirect(url_for('room_availability'))

            cur.close()

        except Exception as e:
            flash("Database error occurred while fetching room price.")
            print(f"Error: {e}")
            return redirect(url_for('room_availability'))

        return redirect(url_for('payment'))  # Redirect to payment

    return render_template('rooms.html')


@app.route('/roombooking/customer/room_availability/payment', methods=['GET', 'POST'])
@login_required
def payment():
    if request.method == 'POST':
        amount_paid = session.get('TotalAmount')  # Fetch total amount from session
        payment_mode = request.form.get('PaymentMode')
        payment_date = request.form.get('PaymentDate')
        payment_status = request.form.get('PaymentStatus')

        # Ensure all required fields are present
        if not amount_paid or not payment_mode or not payment_date or not payment_status:
            flash("Please fill in all payment details.")
            return redirect(url_for('payment'))

        try:
            cur = mysql.connection.cursor()
            cur.execute("""
                CALL Roombooking(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, @confirmation_message)
            """, (
                session['Name'], 
                session['CustomerContact'],
                session['Email'],
                session['Address'],
                session['RoomType'],
                5,  # Assuming this is some constant related to room booking
                datetime.date.today(),
                session['CheckinDate'],
                session['CheckoutDate'],
                session['Status'],
                amount_paid,
                payment_mode,
                payment_date,
                payment_status
            ))

            cur.execute("SELECT @confirmation_message;")
            confirmation_message = cur.fetchone()[0]
            flash(confirmation_message)

        except Exception as e:
            flash("An error occurred during payment processing.")
            print(e)
        finally:
            cur.close()

        customer_name = session.get('customer_name')
        session.clear()  # Clear session after booking confirmation

        return f"Thank you, {customer_name}! Your booking is confirmed."

    # Pass total amount to the template for display
    total_amount = session.get('TotalAmount', 0)
    return render_template('payment.html', total_amount=total_amount)


@app.route('/paymentstatus', methods=['GET', 'POST'])
@login_required
def payment_status():
    if request.method == 'POST':
        booking_id = request.form.get('BookingID')
        print(booking_id)
        if not booking_id:
            flash("Booking ID is required!", "danger")
            return redirect(url_for("payment_status"))

        cur = mysql.connection.cursor()

        # Fetch CustomerID from the booking table
        cur.execute("SELECT CustomerID FROM bookings WHERE BookingID = %s", (booking_id,))
        customer_id = cur.fetchone()


        if not customer_id:
            flash("Invalid Booking ID. No booking found.", "warning")
            return redirect(url_for("payment_status"))

        customer_id = customer_id[0]

        # Fetch Room Payment using BookingID
        cur.execute("""
            SELECT PaymentDate, PaymentMode,  AmountPaid, PaymentStatus
            FROM payment
            WHERE BookingID = %s
        """, (booking_id,))
        room_payment = cur.fetchone()
        print("roompay",room_payment)

        # Fetch Additional Service Payments using CustomerID
        cur.execute("""
            SELECT PaymentDate, PaymentMode,AmountPaid, PaymentStatus
            FROM additionalservicepayment
            WHERE CustomerID = %s
        """, (customer_id,))
        additional_payments = cur.fetchall()
        cur.close()

        # Calculate Total Payment
        total_amount = room_payment[2] if room_payment else 0
        for service in additional_payments:
            total_amount += service[2]  # Additional Service Payment Amount

        return render_template(
            "payment_summary.html",
            room_payment=room_payment,
            additional_payments=additional_payments,
            total_amount=total_amount
        )

    return render_template("payment_summary.html")


@app.route('/checkroomavailability', methods=['GET', 'POST'])
@login_required
def checkroom_availability():
    if request.method == 'POST':
        # Get input from the form
        room_type = request.form.get('RoomType')
        check_in = request.form.get('CheckinDate')
        check_out = request.form.get('CheckoutDate')

        # Store the values in session (optional, you can use them directly in the query as well)
        session['RoomType'] = room_type
        session['CheckinDate'] = check_in
        session['CheckoutDate'] = check_out

        # Query the database for room availability
        cur = mysql.connection.cursor()
        try:
            # SQL query to check for available rooms
            cur.execute("""
                SELECT COUNT(*) 
                FROM rooms 
                WHERE RoomType = %s 
                  AND RoomID NOT IN (
                      SELECT RoomID 
                      FROM bookings 
                      WHERE NOT (CheckoutDate <= %s OR CheckinDate >= %s)
                  )
            """, (room_type, check_in, check_out))

            available_rooms = cur.fetchone()[0]

            if available_rooms > 0:
                flash(f"Rooms are available for the selected type and dates.")
            else:
                flash(f"No rooms are available for the selected type and dates.")
        except Exception as e:
            flash(f"An error occurred: {str(e)}")
        finally:
            cur.close()

    return render_template('checkroom.html')


@app.route('/update/customer', methods=['GET', 'POST'])
@login_required
@admin_required
def updatecustomerdetails():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        fields_to_update = {}
        if 'UpdateName' in request.form:
            fields_to_update['Name'] = request.form.get('Name')
        if 'update_contact' in request.form:
            fields_to_update['Contact'] = request.form.get('Contact')
        if 'update_email' in request.form:
            fields_to_update['Email'] = request.form.get('Email')
        if 'update_address' in request.form:
            fields_to_update['Address'] = request.form.get('Address')

        if fields_to_update:
            conn = mysql.connection.cursor()
            query = "UPDATE Customers SET "
            query += ", ".join(f"{key} = ?" for key in fields_to_update.keys())
            query += " WHERE id = ?"
            values = list(fields_to_update.values()) + [customer_id]
            conn.execute(query, values)

            return flash(f"Customer {customer_id} updated successfully!")
        else:
            return flash("No fields selected for update!")
    return render_template('update_customer.html')

@app.route('/update/staff', methods=['GET', 'POST'])
@login_required
@admin_required
def updatestaffdetails():
    if request.method == 'POST':
        Staff_id = request.form.get('Staff_id')
        fields_to_update = {}
        if 'UpdateName' in request.form:
            fields_to_update['Name'] = request.form.get('Name')
        if 'UpdateRole' in request.form:
            fields_to_update['Role'] = request.form.get('Role')
        if 'UpdateContact' in request.form:
            fields_to_update['Contact'] = request.form.get('Contact')
        if 'UpdateSalary' in request.form:
            fields_to_update['Salary'] = request.form.get('Salary')
        if 'UpdateShiftTiming' in request.form:
            fields_to_update['ShiftTiming'] = request.form.get('ShiftTiming')

        if fields_to_update:
            conn = mysql.connection.cursor()
            query = "UPDATE Staff SET "
            query += ", ".join(f"{key} = ?" for key in fields_to_update.keys())
            query += " WHERE id = ?"
            values = list(fields_to_update.values()) + [Staff_id]
            conn.execute(query, values)

            return flash(f"Staff {Staff_id} updated successfully!")
        else:
            return flash("No fields selected for update!")
    return render_template('update_staff.html')

@app.route('/add/staff', methods=['GET', 'POST'])
@login_required
@admin_required
def addstaffdetails():
    if request.method == 'POST':
        session['Name'] = request.form.get('Name')
        session['Role'] = request.form.get('Role')
        session['ContactNumber'] = request.form.get('ContactNumber')
        session['Salary'] = request.form.get('Salary')
        session['ShiftTiming'] = request.form.get('ShiftTiming')
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO STAFF (Name,Role,ContactNumber,Salary,ShiftTiming) VALUES(session['Name'],session['Role']),session['ContactNumber'],session['Salary'],session['ShiftTiming']")
        session.clear()
        flash(f"Staff details inserted sucssesfully")

@app.route('/add/user', methods=['GET', 'POST'])
@login_required
@admin_required
def adduserdetails():
    if request.method == 'POST':
        session['Username'] = request.form.get('Username')
        session['Email'] = request.form.get('Email')
        session['Password'] = request.form.get('Password')
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO User (Username,Email,Password) VALUES(session['Username'],session['Email']),session['Password']")
        session.clear()
        flash(f"User details inserted sucssesfully")

@app.route('/additionalservices', methods=['GET', 'POST'])
@login_required
def additionalservices():
    staff_info = None
    message = ""
    total_cost = 0
    selected_services = []
    service_date = None

    if request.method == 'POST':
        booking_id = request.form.get('BookingID')
        service_date = request.form.get('ServiceDate')
        payment_mode = request.form.get('PaymentMode')

        # Fetch the CustomerID from BookingID
        cur = mysql.connection.cursor()
        cur.execute("SELECT CustomerID FROM bookings WHERE BookingID = %s", (booking_id,))
        customer_result = cur.fetchone()
        if not customer_result:
            flash("Invalid Booking ID")
            return redirect(url_for('additionalservices'))
        customer_id = customer_result[0]

        # Get selected services
        services = ['Gym', 'Spa', 'Laundry']
        for service in services:
            if service in request.form:
                selected_services.append(service)

        # Fetch price and service ID for selected services
        for service in selected_services:
            cur.execute("SELECT ServiceID, ServiceCharge FROM AdditionalServices WHERE ServiceName = %s", (service,))
            result = cur.fetchone()
            service_id = result[0]
            service_charge = result[1]
            total_cost += service_charge

            # Check staff availability (Max 10 per day logic)
            cur.execute("""
                SELECT StaffID FROM Staff
                WHERE Role = %s AND StaffID NOT IN (
                    SELECT StaffID FROM ServiceBooking
                    WHERE ServiceDate = %s
                    GROUP BY StaffID
                    HAVING COUNT(ServiceBookingID) >= 10
                )
                LIMIT 1
            """, (service, service_date))
            
            staff_result = cur.fetchone()

            if staff_result:
                # Assign the staff and insert into ServiceBooking table
                staff_id = staff_result[0]
                cur.execute("""
                    INSERT INTO ServiceBooking (CustomerID, ServiceID, StaffID, ServiceDate)
                    VALUES (%s, %s, %s, %s)
                """, (customer_id, service_id, staff_id, service_date))

                # Fetch the staff information
                cur.execute("SELECT Name, Role FROM Staff WHERE StaffID = %s", (staff_id,))
                staff_info = cur.fetchone()

                # Handle payment status based on Prepaid or Postpaid
                payment_status = "Paid" if payment_mode == "Prepaid" else "Unpaid"

                # Insert into AdditionalServicePayment
                cur.execute("""
                    INSERT INTO AdditionalServicePayment (CustomerID, ServiceBookingID, AmountPaid, PaymentMode, PaymentDate, PaymentStatus)
                    VALUES (%s, LAST_INSERT_ID(), %s, %s, %s, %s)
                """, (customer_id, service_charge, payment_mode, datetime.date.today(), payment_status))

                mysql.connection.commit()

            else:
                message = f"No staff is available for {service} on {service_date}."
                return render_template('services.html', message=message)

        if not message:
            message = f"Services successfully booked. Total Amount Paid: ₹{total_cost}"

    return render_template('services.html', staff_info=staff_info, message=message, total_cost=total_cost, payment_status=payment_status)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully"})


if __name__ == '__main__':
    app.run(debug=True)