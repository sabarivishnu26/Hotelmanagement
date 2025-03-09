from flask import Flask
from flask import render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime



app = Flask(__name__)
app.secret_key = 'your_secret_key'

mysql = MySQL(app)

app.config['MYSQL_HOST'] = '127.0.0.1'  
app.config['MYSQL_USER'] = 'newuser'       
app.config['MYSQL_PASSWORD'] = 'newuser'  
app.config['MYSQL_DB'] = 'hotel'

@app.route('/home')
def home():
    return render_template('index.html')

   
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", [email])
        user = cur.fetchone()
        cur.close()

        if user and check_password_hash(user[3], password): 
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            flash(f"Welcome, {user[1]}!", "success")
            return redirect(url_for('home'))
        else:
            flash("Invalid email or password. Please try again.", "danger")
            return redirect(url_for('login')) 
    

    return render_template('login.html')


@app.route('/register',methods=['POST'])
def register():
    if request.method == 'POST':
        name = request.form['UserName']
        email = request.form['Email']
        password = request.form['Password']
        hashed_password = generate_password_hash(password)  

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (UserName, Email, Password) VALUES (%s, %s, %s)", 
                    (name, email, hashed_password))
        mysql.connection.commit()
        cur.close()
        flash("Registration Successful! You can now log in.", "success")
        return redirect(url_for('login'))

@app.route('/customer', methods=['GET', 'POST'])
def roombooking():
    if request.method == 'POST':
        session['Name'] = request.form.get('Name')
        session['CustomerContact'] = request.form.get('CustomerContact')  # Correct field name
        session['Email'] = request.form.get('Email')
        session['Address'] = request.form.get('Address')
        print(session['Name'])
        print(session['CustomerContact'])
        print(session['Email'])
        print(session['Address'])
        
        return redirect(url_for('room_availability'))
    
    return render_template('customer.html')


@app.route('/room_availability', methods=['GET', 'POST'])
def room_availability():
    if request.method == 'POST':
        session['Status'] = 'BOOKED'

        room_type = request.form.get('RoomType')
        check_in = request.form.get('CheckinDate')
        check_out = request.form.get('CheckoutDate')

        session['RoomType'] = room_type
        session['CheckinDate'] = check_in
        session['CheckoutDate'] = check_out
        print(session['RoomType'])
        print(session['CheckinDate'])
        print(session['CheckoutDate'])
        available_rooms = 0
        cur = mysql.connection.cursor()
        try:
            # SQL query to check for available rooms
            cur.execute("""SELECT RoomID FROM rooms WHERE RoomType = %s AND RoomID NOT IN (SELECT RoomID FROM bookings WHERE NOT CheckoutDate <= %s OR CheckinDate >= %s)LIMIT 1 """, (room_type, check_in, check_out))
            room = cur.fetchone()
            print(room)
            if room:
            # Store the first available room's RoomID in the session
                session['roomid'] = room[0]
                print("roomid",session['roomid'])
                flash("Rooms are available for the selected type and dates.")
                session['RoomAvailable'] = True
            else:
                flash("No rooms are available for the selected type and dates.")
                session['RoomAvailable'] = False
        except Exception as e:
            flash("An error occurred while checking room availability.")
        finally:
            cur.close()

        # Redirect to payment if rooms are available
        if session.get('RoomAvailable'):
            return redirect(url_for('payment'))

    return render_template('rooms.html')

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    amtpaid = 0  # Initialize amtpaid for GET requests
    if request.method == 'POST':
        cur = mysql.connection.cursor()
        # Fetch the price per night
        query = "SELECT PricePerNight FROM rooms WHERE RoomID = %s"
        cur.execute(query, (session['roomid'],))
        result = cur.fetchone()
        print(result)
        if result:
            price_per_night = result[0]
        else:
            flash("Invalid Room ID.")
            return render_template('payment.html', amtpaid=amtpaid)
        # Calculate the number of days
        query_days = "SELECT DATEDIFF(%s, %s)"
        values = (session['CheckoutDate'], session['CheckinDate'])
        cur.execute(query_days, values)
        days = cur.fetchone()
        print(days)
        days = days[0] if days else 1  # Default to 1 day if calculation fails

        # Calculate total amount
        amtpaid = float(price_per_night) * days
        print(amtpaid)
        # Get form values and validate
        payment_mode = request.form.get('PaymentMode')
        payment_date = request.form.get('PaymentDate')
        payment_status = request.form.get('PaymentStatus')

        # Check for missing required fields
        if not payment_mode or not payment_date or not payment_status:
            flash("All fields are required.")
            return render_template('payment.html', amtpaid=amtpaid)

        # Store in session for later use
        session['AmountPaid'] = amtpaid
        session['PaymentMode'] = payment_mode
        session['PaymentDate'] = payment_date
        session['PaymentStatus'] = payment_status

        # Insert data into the customer table
        cur.execute("""
            INSERT INTO customer (Name, ContactNumber, Email, Address)
            VALUES (%s, %s, %s, %s)
        """, (session['Name'], session['CustomerContact'], session['Email'], session['Address']))

        # Insert booking details
        cur.execute("""
            INSERT INTO bookings (CustomerID, RoomID, BookingDate, CheckinDate, CheckoutDate, Status)
            VALUES ((SELECT MAX(CustomerID) FROM customer), %s, %s, %s, %s, %s)
        """, (session['roomid'], datetime.today().strftime('%Y-%m-%d'), session['CheckinDate'], session['CheckoutDate'], session['Status']))

        # Update room status
        cur.execute("""
            UPDATE rooms
            SET Status = 'Booked'
            WHERE RoomID = %s
        """, (session['roomid'],))

        # Insert payment details
        cur.execute("""
            INSERT INTO payment (BookingID, AmountPaid, PaymentMode, PaymentDate, PaymentStatus)
            VALUES ((SELECT MAX(BookingID) FROM bookings), %s, %s, %s, %s)
        """, (amtpaid, session['PaymentMode'], session['PaymentDate'], session['PaymentStatus']))

        # Commit and close
        mysql.connection.commit()
        cur.close()

        flash("Booking Successful")
        customer_name = session.get('Name', 'Customer')  # Use 'Customer' if name not in session
        session.clear()
        return f"Thank you, {customer_name}! Your booking is confirmed."

    # Render the template for GET request, passing amtpaid
    return render_template('payment.html', amtpaid=amtpaid)


@app.route('/checkroomavailability', methods=['GET', 'POST'])
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



@app.route('/update/customer', methods=['GET','POST'])
def updatecustomerdetails():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        fields_to_update = {}
        if 'Name' in request.form:
            fields_to_update['Name'] = request.form.get('Name')
        if 'Contact' in request.form:
            fields_to_update['Contact'] = request.form.get('Contact')
        if 'Email' in request.form:
            fields_to_update['Email'] = request.form.get('Email')
        if 'Address' in request.form:
            fields_to_update['Address'] = request.form.get('Address')

        print(customer_id)
        print(fields_to_update)

        if fields_to_update:
            try:
                conn = mysql.connection.cursor()
                query = "UPDATE customer SET "
                query += ", ".join(f"{key} = %s" for key in fields_to_update.keys())
                query += " WHERE CustomerID = %s"
                values = list(fields_to_update.values()) + [customer_id]
                conn.execute(query, values)
                mysql.connection.commit()
                flash(f"Customer {customer_id} updated successfully!")
            except Exception as e:
                flash(f"An error occurred: {e}")
            return redirect(url_for('updatecustomerdetails'))
        else:
            flash("No fields selected for update!")
            return redirect(url_for('updatecustomerdetails'))
    return render_template('update_customer.html')

@app.route('/update/staff', methods=['GET', 'POST'])
def updatestaffdetails():
    if request.method == 'POST':
        Staff_id = request.form.get('staff_id')  # Ensure this matches your form's input name
        fields_to_update = {}

        # Collect fields to update from the form
        if request.form.get('Name'):
            fields_to_update['Name'] = request.form.get('Name')
        if request.form.get('Role'):
            fields_to_update['Role'] = request.form.get('Role')
        if request.form.get('Contact'):
            fields_to_update['Contact'] = request.form.get('Contact')
        if request.form.get('Salary'):
            fields_to_update['Salary'] = request.form.get('Salary')
        if request.form.get('ShiftTiming'):
            fields_to_update['ShiftTiming'] = request.form.get('ShiftTiming')

        print(fields_to_update)  # Debugging: Print the fields to update
        print(Staff_id)         # Debugging: Print the staff ID

        if fields_to_update:
            try:
                conn = mysql.connection.cursor()

                # Construct the query using MySQL placeholders
                query = "UPDATE Staff SET "
                query += ", ".join(f"{key} = %s" for key in fields_to_update.keys())
                query += " WHERE StaffID = %s"
                values = list(fields_to_update.values()) + [Staff_id]

                # Execute the query
                conn.execute(query, values)
                mysql.connection.commit()
                flash(f"Staff {Staff_id} updated successfully!", "success")
            except Exception as e:
                flash(f"An error occurred: {e}", "error")
            finally:
                conn.close()
        else:
            flash("No fields selected for update!", "warning")
            return redirect(url_for('updatestaffdetails'))

    return render_template('update_staff.html')


@app.route('/add/staff', methods=['GET', 'POST'])
def addstaffdetails():
    if request.method == 'POST':
        session['Name'] = request.form.get('Name')
        session['Role'] = request.form.get('Role')
        session['ContactNumber'] = request.form.get('ContactNumber')
        session['Salary'] = request.form.get('Salary')
        session['ShiftTiming'] = request.form.get('ShiftTiming')
        print(session['Name'])
        print(session['ShiftTiming'])
        cur = mysql.connection.cursor()
        cur.execute(
            """INSERT INTO staff (Name, Role, Contactnumber, Salary, ShiftTiming) VALUES (%s, %s, %s, %s, %s)""",
            (session['Name'], session['Role'], session['ContactNumber'], session['Salary'], session['ShiftTiming']))
        mysql.connection.commit()  # Commit the transaction
        cur.close()

        session.clear()
        flash(f"Staff details inserted sucssesfully")
    return render_template('staff.html')

@app.route('/add/user', methods=['GET', 'POST'])
def adduserdetails():
    if request.method == 'POST':
        session['Username'] = request.form.get('Username')
        session['Email'] = request.form.get('Email')
        session['Password'] = request.form.get('Password')
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO User (Username,Email,Password) VALUES(session['Username'],session['Email']),session['Password']")
        session.clear()
        flash(f"User details inserted sucssesfully")

@app.route('/addtionalservices',methods=['GET','POST'])
def addtionalservices():
    if request.method == 'POST':
        session['BookingID'] = request.form.get('BookingID')
        additonalservices = {}
        Quantity_additonalservices={}
        if 'Gym' in request.form:
            additonalservices['Gym'] = request.form.get('Gym')
            Quantity_additonalservices['Gym'] = request.form.get('Gym_Quantity_additionalservices')
        if 'Room Service' in request.form:
            additonalservices['Room Service'] = request.form.get('Room Service')
            Quantity_additonalservices['Room Service'] = request.form.get('Room Service_Quantity_additionalservices')
        if 'Spa' in request.form:
            additonalservices['Spa'] = request.form.get('Spa')
            Quantity_additonalservices['Spa'] = request.form.get('Spa_Quantity_additionalservices')
        if 'Laundry Service' in request.form:
            additonalservices['Laundry Service'] = request.form.get('Laundry Service')
            Quantity_additonalservices['Laundry Service'] = request.form.get('Laundry Service_Quantity_additionalservices')

        price={}
        id={}
        Totalcost={}
        cur = mysql.connection.cursor()
        for service in addtionalservices:
            price[service]=cur.execute("SELECT Price FROM additionalservices WHERE ServicesName ="+ service)
            id[service]=cur.execute("SELECT ServiceID FROM additionalservices WHERE ServicesName ="+ service)
            Totalcost[service]=Quantity_additonalservices[service]*price[service]
        for service in additonalservices:
            cur.execute(f"INSERT INTO serviceusage (ServiceID,BookingID,Quantity,TotalCost) VALUES({id[service]},session['BookingID'],{Quantity_additonalservices[service]},{Totalcost[service]})")
        cur.execute("SELECT SUM(TotalCost) FROM serviceusage WHERE BookingID="+str(session['BookingID']))
        cur.execute("UPDATE payment SET AmountPaid="+(("SELECT AmountPaid FROM payment WHERE BookingID="+session['BookingID']) + cur.fetchone()))
        session.clear()

        flash("sucssesfuly completed additionalservies")
    return render_template('services.html')

#email part

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)