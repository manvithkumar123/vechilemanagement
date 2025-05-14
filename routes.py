import os
import logging
from flask import render_template, redirect, url_for, request, flash, session, jsonify
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
import tempfile
import base64
import re

from app import app, db
from models import User, Vehicle, Fine
from ocr_utils import process_image
from state_detection import detect_state_from_plate

# Define employee credentials
EMPLOYEE_USERNAME = "manager"
EMPLOYEE_PASSWORD = "123456"

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_type = request.form.get('login_type')
        username = request.form.get('username')
        
        if not username:
            flash('Username is required', 'danger')
            return redirect(url_for('login'))
        
        # Check if user exists, if not create a new user
        user = User.query.filter_by(username=username).first()
        
        if login_type == 'employee':
            password = request.form.get('password')
            
            if username == EMPLOYEE_USERNAME and password == EMPLOYEE_PASSWORD:
                if not user:
                    # Create employee user if doesn't exist
                    user = User()
                    user.username = username
                    user.is_employee = True
                    db.session.add(user)
                    db.session.commit()
                
                session['user_id'] = user.id
                session['is_employee'] = True
                flash('Login successful!', 'success')
                return redirect(url_for('employee_dashboard'))
            else:
                flash('Invalid credentials', 'danger')
                return redirect(url_for('login'))
        else:  # User login
            if not user:
                # Create new regular user
                user = User()
                user.username = username
                user.is_employee = False
                db.session.add(user)
                db.session.commit()
            
            session['user_id'] = user.id
            session['is_employee'] = False
            flash('Login successful!', 'success')
            return redirect(url_for('user_dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_employee', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('home'))

@app.route('/user/dashboard')
def user_dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    # Get all vehicles and fines for this user
    vehicles = Vehicle.query.filter_by(user_id=user_id).all()
    fines = Fine.query.filter_by(user_id=user_id).all()
    
    return render_template('user_dashboard.html', user=user, vehicles=vehicles, fines=fines)

@app.route('/employee/dashboard')
def employee_dashboard():
    if not session.get('user_id') or not session.get('is_employee'):
        return redirect(url_for('login'))
    
    # Get all fines for the employee to manage
    fines = Fine.query.all()
    return render_template('employee_dashboard.html', fines=fines)

@app.route('/employee/fine/new', methods=['GET', 'POST'])
def new_fine():
    if not session.get('user_id') or not session.get('is_employee'):
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        plate_number = request.form.get('plate_number')
        reason = request.form.get('reason')
        amount = request.form.get('amount')
        location = request.form.get('location')
        proof_image = request.form.get('proof_image')  # Get the base64 image data
        
        if not plate_number or not reason or not amount or not location:
            flash('All fields are required', 'danger')
            return redirect(url_for('new_fine'))
        
        # Detect state from plate number
        state = detect_state_from_plate(plate_number)
        
        # Check if vehicle exists, if not create it
        vehicle = Vehicle.query.filter_by(plate_number=plate_number).first()
        
        if not vehicle:
            # Find or create user for this vehicle
            # For simplicity, create a default user with the same name as the plate number
            user = User.query.filter_by(username=plate_number).first()
            if not user:
                user = User()
                user.username = plate_number
                user.is_employee = False
                db.session.add(user)
                db.session.commit()
            
            vehicle = Vehicle()
            vehicle.plate_number = plate_number
            vehicle.state = state
            vehicle.user_id = user.id
            db.session.add(vehicle)
            db.session.commit()
        
        # Create new fine
        fine = Fine()
        fine.reason = reason
        fine.amount = float(amount)
        fine.location = location
        fine.vehicle_id = vehicle.id
        fine.user_id = vehicle.user_id
        fine.created_by = session['user_id']
        fine.proof_image = proof_image
        
        db.session.add(fine)
        db.session.commit()
        
        flash('Fine successfully added', 'success')
        return redirect(url_for('employee_dashboard'))
    
    return render_template('fine_entry.html')

@app.route('/process_image', methods=['POST'])
def process_image_route():
    if not session.get('user_id') or not session.get('is_employee'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        # Check if we have a manually entered plate number
        manual_plate = None
        if request.json and 'manual_plate' in request.json:
            manual_plate = request.json['manual_plate']
        
        if manual_plate:
            # Just detect state from the manually entered plate
            state = detect_state_from_plate(manual_plate)
            return jsonify({
                'success': True, 
                'plate_number': manual_plate,
                'state': state
            })
            
        # Get the image data from the request
        image_data = request.json['image_data'] if request.json and 'image_data' in request.json else ''
        
        if not image_data:
            return jsonify({'success': False, 'error': 'No image data provided'}), 400
        
        # Remove the prefix from the base64 data
        if 'base64,' in image_data:
            image_data = image_data.split('base64,')[1]
        
        # Convert base64 to image file
        image_bytes = base64.b64decode(image_data)
        
        # Save to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
        
        try:
            # Process the image with OCR
            plate_number = process_image(temp_file_path)
        finally:
            # Always remove temporary file
            os.unlink(temp_file_path)
        
        if plate_number:
            # Clean up plate number - remove any non-alphanumeric characters
            plate_number = re.sub(r'[^A-Za-z0-9]', '', plate_number)
            
            # Detect state from plate number
            state = detect_state_from_plate(plate_number)
            
            return jsonify({
                'success': True, 
                'plate_number': plate_number,
                'state': state
            })
        else:
            # If OCR failed, extract any visible text from the image
            # This will be an empty string or just the text found in the image
            # Let the user edit it completely
            return jsonify({
                'success': True,
                'plate_number': 'No text detected - please enter manually',
                'state': 'Unknown',
                'ocr_failed': True
            })
        
    except Exception as e:
        logging.error(f"Error processing image: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/view_fines')
def view_fines():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    is_employee = session.get('is_employee', False)
    
    if is_employee:
        # Employees can see all fines
        fines = Fine.query.all()
    else:
        # Users can only see their own fines
        fines = Fine.query.filter_by(user_id=user_id).all()
    
    return render_template('view_fines.html', fines=fines, is_employee=is_employee)

@app.route('/toggle_theme', methods=['POST'])
def toggle_theme():
    current_theme = session.get('theme', 'dark')
    new_theme = 'light' if current_theme == 'dark' else 'dark'
    session['theme'] = new_theme
    return jsonify({'success': True, 'theme': new_theme})

@app.route('/toggle_payment/<int:fine_id>', methods=['POST'])
def toggle_payment(fine_id):
    # Check if user is logged in
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    fine = Fine.query.get_or_404(fine_id)
    
    # Check if this is the user's fine or the user is an employee
    if fine.user_id != session.get('user_id') and not session.get('is_employee'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    try:
        # Toggle the payment status
        fine.paid = not fine.paid
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'paid': fine.paid,
            'message': 'Payment status updated successfully'
        })
    except Exception as e:
        logging.error(f"Error toggling payment: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.context_processor
def inject_theme():
    return {'theme': session.get('theme', 'dark')}
