from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from sqlalchemy import text
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_from_directory, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from sqlalchemy import text
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
from werkzeug.security import generate_password_hash
import pytz
import os
import json
from functools import wraps
import pandas as pd
from io import BytesIO
from decimal import Decimal
import random
import time

import re

def is_strong_password(password):
    pattern = r'^(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&]).{6,}$'
    return re.match(pattern, password)

# Timezone setup
IST = pytz.timezone('Asia/Kolkata')


from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)



def calculate_age(dob):
    if not dob:
        return None

    today = date.today()

    years = today.year - dob.year
    months = today.month - dob.month
    days = today.day - dob.day

    if days < 0:
        months -= 1
        prev_month = today.month - 1 or 12
        prev_year = today.year if today.month > 1 else today.year - 1
        days += (date(prev_year, prev_month % 12 + 1, 1) - date(prev_year, prev_month, 1)).days

    if months < 0:
        years -= 1
        months += 12

    return {
        "years": years,
        "months": months,
        "days": days
    }

@app.context_processor
def inject_helpers():
    return dict(calculate_age=calculate_age, user_role=session.get('user_role'))




def get_ist_now():
    """Get current time in IST timezone"""
    return datetime.now(IST)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///medical_system.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Session Configuration
app.config['SESSION_TYPE'] = os.environ.get('SESSION_TYPE', 'filesystem')
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'medsys:'
app.config['SESSION_FILE_DIR'] = os.path.join(app.root_path, 'instance', 'flask_session')

# Email Configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')
 
from extensions import db, mail
mail.init_app(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx'}
UPI_ID = "medical-system@upi"
SECURITY_IMAGE_OPTIONS = ['heart', 'shield', 'star', 'leaf', 'moon', 'sun']


db.init_app(app)
if app.config['SESSION_TYPE'] == 'sqlalchemy':
    app.config['SESSION_SQLALCHEMY'] = db

from flask_session import Session
Session(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'aadhaar'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'reports'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'bills'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'payments'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'treatment_reports'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'patient_images'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'medical_reports'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'qr_codes'), exist_ok=True)

# Database Models moved to models.py
from models import (Patient, Disease, Hospital, PatientRequest, 
                    TreatmentReport, AccidentCase, PatientClaim, 
                    Notification, Doctor, Admin, HospitalDisease, get_ist_now)

# Helper Functions



def patient_login_required(f):
    """Decorator to protect patient routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('patient_logged_in'):
            flash('Please login to access this page', 'warning')
            return redirect(url_for('patient_login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_notification(user_type, user_id, title, message, notification_type=None, related_id=None):
    """Create a notification for admin or hospital"""
    notification = Notification(
        user_type=user_type,
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_id=related_id
    )
    db.session.add(notification)
    db.session.commit()
    return notification

def notify_admin(title, message, notification_type=None, related_id=None):
    """Notify all admins"""
    admins = Admin.query.all()
    for admin in admins:
        create_notification('admin', admin.admin_id, title, message, notification_type, related_id)

def notify_hospital(hospital_id, title, message, notification_type=None, related_id=None):
    """Notify a specific hospital"""
    create_notification('hospital', hospital_id, title, message, notification_type, related_id)

def notify_patient(patient_id, title, message, notification_type=None, related_id=None):
    """Notify a specific patient"""
    create_notification('patient', patient_id, title, message, notification_type, related_id)

def generate_patient_serial_number():
    """Generate next patient serial number starting from 101"""
    # Get the highest serial number from all patient requests
    last_request = PatientRequest.query.filter(
        PatientRequest.patient_serial_number.isnot(None),
        PatientRequest.patient_serial_number != ''
    ).order_by(PatientRequest.request_id.desc()).first()
    
    # Also check accident cases
    last_accident = AccidentCase.query.filter(
        AccidentCase.patient_serial_number.isnot(None),
        AccidentCase.patient_serial_number != ''
    ).order_by(AccidentCase.accident_id.desc()).first()
    
    # Find the highest number from both sources
    max_number = 0
    if last_request and last_request.patient_serial_number:
        try:
            max_number = max(max_number, int(last_request.patient_serial_number))
        except (ValueError, TypeError):
            pass
    
    if last_accident and last_accident.patient_serial_number:
        try:
            max_number = max(max_number, int(last_accident.patient_serial_number))
        except (ValueError, TypeError):
            pass
    
    if max_number > 0:
        next_number = max_number + 1
    else:
        # First patient, start from 101
        next_number = 101
    
    return str(next_number)

def login_required_hospital(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'hospital_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('hospital_login'))
        return f(*args, **kwargs)
    return decorated_function

def login_required_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ========== ROLE-BASED ACCESS CONTROL DECORATOR ==========
def role_required(*allowed_roles):
    """
    Decorator to check user role and grant access accordingly.
    Usage: @role_required('patient'), @role_required('hospital', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('user_role')
            
            if not user_role or user_role not in allowed_roles:
                flash('Access denied. You do not have permission to access this page.', 'danger')
                
                # Redirect based on current logged-in status
                if session.get('patient_logged_in'):
                    return redirect(url_for('patient_panel'))
                elif session.get('hospital_id'):
                    return redirect(url_for('hospital_dashboard'))
                elif session.get('admin_id'):
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Routes - Patient Side
@app.route('/')
def index():
    if 'lang' not in session:
        session['lang'] = 'en'   # default English
    
    # ✅ ROLE-AWARE REDIRECT
    user_role = session.get('user_role')
    if user_role == 'patient' and session.get('patient_logged_in'):
        return redirect(url_for('patient_panel'))
    elif user_role == 'hospital' and session.get('hospital_id'):
        return redirect(url_for('hospital_dashboard'))
    elif user_role == 'admin' and session.get('admin_id'):
        return redirect(url_for('admin_dashboard'))
    
    # Show public landing page
    return render_template('patient/index.html')


# ========== PATIENT ACCOUNT: REGISTER + LOGIN ==========

@app.route('/patient/register', methods=['GET', 'POST'])
def patient_register():
    """Create patient account with username + password + basic details + captcha."""
    # Generate simple 5-digit captcha for display
    if request.method == 'GET':
        session['patient_captcha'] = str(random.randint(10000, 99999))
        return render_template(
            'patient/register.html',
            captcha=session['patient_captcha'],
            security_image_options=SECURITY_IMAGE_OPTIONS
        )

    # POST – handle form submit
    name = request.form.get('name', '').strip()
    dob_str = request.form.get('dob', '').strip()
    gender = request.form.get('gender', '').strip()
    phone = request.form.get('phone', '').strip()
    email = request.form.get('email', '').strip().lower()
    address = request.form.get('address', '').strip()
    username = request.form.get('username', '').strip()
    security_image = request.form.get('security_image', '').strip().lower()
    password = request.form.get('password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()
    captcha_input = request.form.get('captcha', '').strip()

    # Basic validations
    if not all([name, dob_str, gender, phone, email, address, username, security_image, password, confirm_password, captcha_input]):
        flash("कृपया सभी आवश्यक जानकारी भरें", "danger")
        return redirect(url_for('patient_register'))

    if security_image not in SECURITY_IMAGE_OPTIONS:
        flash("कृपया वैध सुरक्षा इमेज चुनें", "danger")
        return redirect(url_for('patient_register'))

    # Captcha check
    expected_captcha = session.get('patient_captcha')
    if not expected_captcha or captcha_input != expected_captcha:
        flash("Captcha गलत है, कृपया दोबारा प्रयास करें", "danger")
        return redirect(url_for('patient_register'))

    # Password match
    if password != confirm_password:
        flash("Password और Confirm Password एक जैसे होने चाहिए", "danger")
        return redirect(url_for('patient_register'))

    # Username unique
    existing_username = Patient.query.filter_by(username=username).first()
    if existing_username:
        flash("यह Username पहले से मौजूद है, कृपया दूसरा Username चुनें", "danger")
        return redirect(url_for('patient_register'))

    # Email optional-unique check (simple)
    existing_email = Patient.query.filter_by(email=email).first()
    if existing_email:
        flash("इस Email से पहले से account बना है, कृपया Login करें", "warning")
        return redirect(url_for('patient_login'))

    # Parse DOB
    try:
        from datetime import datetime as dt
        dob = dt.strptime(dob_str, '%Y-%m-%d').date()
    except Exception:
        dob = None

    # NOTE: aadhar_no is required by DB, so here we store a generated placeholder
    # for accounts created only for portal login.
    auto_aadhar = str(random.randint(10**11, 10**12 - 1))

    patient = Patient(
        name=name,
        username=username,
        password_hash=generate_password_hash(password),
        security_image=security_image,
        gender=gender,
        phone=phone,
        email=email,
        address=address,
        dob=dob,
        aadhar_no=auto_aadhar
    )
    db.session.add(patient)
    db.session.commit()

    flash("Account सफलतापूर्वक बन गया। अब Login करें।", "success")
    return redirect(url_for('patient_login'))


@app.route('/patient/login', methods=['GET', 'POST'])
def patient_login():
    """
    Patient login with:
    - username
    - security image
    - password
    and then direct dashboard login.
    """
    # Already logged in
    if session.get('patient_logged_in') and session.get('user_role') == 'patient':
        return redirect(url_for('patient_panel'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        security_image = request.form.get('security_image', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not username or not security_image or not password:
            flash("Username, Security Image और Password सभी आवश्यक हैं", "danger")
            return redirect(url_for('patient_login'))

        # Find patient by username
        patient = Patient.query.filter_by(username=username).first()
        if not patient:
            flash("Account नहीं मिला। पहले account create करें।", "danger")
            return redirect(url_for('patient_register'))

        if security_image not in SECURITY_IMAGE_OPTIONS or patient.security_image != security_image:
            flash("Security Image गलत है", "danger")
            return redirect(url_for('patient_login'))

        # Password check
        if not patient.password_hash or not check_password_hash(patient.password_hash, password):
            flash("Password गलत है", "danger")
            return redirect(url_for('patient_login'))

        # Direct login (OTP removed)
        session['patient_logged_in'] = True
        session['patient_id'] = patient.patient_id
        session['patient_name'] = patient.name
        session['user_role'] = 'patient'
        flash(f"स्वागत है {patient.name}! आप सफलतापूर्वक लॉगिन हो गए हैं।", "success")
        return redirect(url_for('patient_panel'))

    return render_template('patient/panel_login.html')


@app.route('/patient/logout')
def patient_logout():
    """Logout patient"""
    session.clear()
    flash("आप logout हो गए हैं", "success")
    return redirect(url_for('patient_login'))


@app.route('/patient/panel')
@patient_login_required
@role_required('patient')
def patient_panel():
    """Patient dashboard - Protected route"""
    patient_id = session.get('patient_id')
    patient = Patient.query.get(patient_id)
    
    if not patient:
        session.clear()
        flash("Patient not found", "danger")
        return redirect(url_for('patient_login'))
    
    # Get patient requests with treatment reports
    requests = PatientRequest.query.filter_by(patient_id=patient_id).order_by(PatientRequest.created_at.desc()).all()
    
    # Get accident cases
    accident_cases = AccidentCase.query.filter_by(patient_id=patient_id).order_by(AccidentCase.created_at.desc()).all()
    
    # Get treatment reports for accident cases
    accident_ids = [case.accident_id for case in accident_cases]
    accident_treatment_reports = {}
    if accident_ids:
        reports = TreatmentReport.query.filter(TreatmentReport.accident_id.in_(accident_ids)).all()
        for report in reports:
            if report.accident_id:
                if report.accident_id not in accident_treatment_reports:
                    accident_treatment_reports[report.accident_id] = []
                accident_treatment_reports[report.accident_id].append(report)
    
    # Get unread notifications
    unread_notifications = Notification.query.filter_by(
        user_type='patient',
        user_id=patient_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    return render_template('patient/panel.html', 
                         patient=patient,
                         requests=requests,
                         accident_cases=accident_cases,
                         accident_treatment_reports=accident_treatment_reports,
                         unread_notifications=unread_notifications)


@app.route('/accident-select-hospital')
def accident_select_hospital():
    """Show list of hospitals for accident case"""
    hospitals = Hospital.query.all()
    return render_template('patient/accident_select_hospital.html', hospitals=hospitals)

@app.route('/accident-register/<int:hospital_id>', methods=['GET', 'POST'])
def accident_register(hospital_id):
    """Accident case registration form"""
    hospital = Hospital.query.get_or_404(hospital_id)
    
    if request.method == 'POST':
        from datetime import datetime as dt
        
        # Get form data
        case_type = request.form.get('case_type')
        patient_name = request.form.get('patient_name')
        gender = request.form.get('gender')
        patient_mobile = request.form.get('patient_mobile')
        email = request.form.get('email')
        date_of_birth_str = request.form.get('date_of_birth')
        aadhar_no = request.form.get('aadhar_no')
        has_ayushman = request.form.get('has_ayushman')  # yes / no

        accident_description = request.form.get('accident_description')
        accident_date_str = request.form.get('accident_date')
        accident_location = request.form.get('accident_location')
        current_condition = request.form.get('current_condition')
        
        # Parse dates
        date_of_birth = None
        accident_date = None
        if date_of_birth_str:
            date_of_birth = dt.strptime(date_of_birth_str, '%Y-%m-%d').date()
        if accident_date_str:
            accident_date = dt.strptime(accident_date_str, '%Y-%m-%d').date()
        
        # Check if patient exists, if not create new
        patient = Patient.query.filter_by(aadhar_no=aadhar_no).first()
        if not patient:
            # Create new patient with minimal info (will be updated later)
            patient = Patient(
                name=patient_name,
                phone=patient_mobile,
                address='Accident Case',
                aadhar_no=aadhar_no
            )
            db.session.add(patient)
            db.session.flush()

        # Handle patient image upload (Jan Aadhaar image)
        patient_image_url = None
        patient_image = request.files.get('patient_image')
        if patient_image and allowed_file(patient_image.filename):
            filename = secure_filename(f"patient_{patient.patient_id}_{patient_image.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'patient_images', filename)
            patient_image.save(filepath)
            patient_image_url = f"uploads/patient_images/{filename}"
        
        # Handle Ayushman Card upload (optional)
        ayushman_card_url = None
        if has_ayushman == 'yes':
            ayushman_file = request.files.get('ayushman_card_image')
            if ayushman_file and allowed_file(ayushman_file.filename):
                filename = secure_filename(f"ayushman_{patient.patient_id}_{ayushman_file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'patient_images', filename)
                ayushman_file.save(filepath)
                ayushman_card_url = f"uploads/patient_images/{filename}"
        
        # Handle patient condition image upload (optional)
        patient_condition_image_url = None
        patient_condition_image = request.files.get('patient_condition_image')
        if patient_condition_image and allowed_file(patient_condition_image.filename):
            filename = secure_filename(f"condition_{patient.patient_id}_{patient_condition_image.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'patient_images', filename)
            patient_condition_image.save(filepath)
            patient_condition_image_url = f"uploads/patient_images/{filename}"
        
        accident_case = AccidentCase(
    patient_id=patient.patient_id,
    hospital_id=hospital_id,

    # 🔥 REQUIRED MISSING FIELDS
    case_type=case_type,
    gender=gender,
    email=email,

    patient_name=patient_name,
    patient_mobile=patient_mobile,
    date_of_birth=date_of_birth,
    aadhar_no=aadhar_no,

    patient_image_url=patient_image_url,
    ayushman_card_url=ayushman_card_url,

    accident_description=accident_description,
    accident_date=accident_date,
    accident_location=accident_location,
    current_condition=current_condition,
    patient_condition_image_url=patient_condition_image_url,

    status='pending'
)

        db.session.add(accident_case)
        db.session.flush()
        
        # Notify hospital
        notify_hospital(
            hospital_id=hospital_id,
            title='New Accident Case Received',
            message=f'New accident case received from patient {patient_name}. Condition: {current_condition[:100]}...',
            notification_type='accident_case',
            related_id=accident_case.accident_id
        )
        
        # Notify admin
        notify_admin(
            title='New Accident Case',
            message=f'Patient {patient_name} has submitted an accident case at {hospital.name}',
            notification_type='accident_case',
            related_id=accident_case.accident_id
        )
        
        db.session.commit()
        
        flash(f'Accident case submitted successfully! Hospital {hospital.name} will review your request.', 'success')
        return redirect(url_for('accident_success', accident_id=accident_case.accident_id))
    
    return render_template('patient/accident_register.html', hospital=hospital)




@app.route('/set-language/<lang>')
def set_language(lang):
    if lang in ['en', 'hi']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

# Static Pages
@app.route('/about')
def about():
    return render_template('about.html')


@app.route("/faqs")
def faqs():
    return render_template("FAQS.html")

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')





@app.route('/hospital_terms')
def hospital_terms():
    return render_template('hospital_terms.html')



@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/accident-success/<int:accident_id>')
def accident_success(accident_id):
    """Success page after accident case submission"""
    accident_case = AccidentCase.query.get_or_404(accident_id)
    return render_template('patient/accident_success.html', accident_case=accident_case)

@app.route('/accident-case-detail/<int:accident_id>')
def accident_case_detail(accident_id):
    """Patient view accident case details"""
    accident_case = AccidentCase.query.get_or_404(accident_id)
    return render_template('patient/accident_case_detail.html', accident_case=accident_case)

@app.route('/patient-claim/<int:treatment_report_id>', methods=['GET', 'POST'])
def patient_claim_form(treatment_report_id):
    """Unified patient claim form (works for both normal and accident cases)"""
    treatment_report = TreatmentReport.query.get_or_404(treatment_report_id)
    
    # Check if claim already submitted (one-time submission)
    existing_claim = PatientClaim.query.filter_by(treatment_report_id=treatment_report_id).first()
    if existing_claim:
        flash('Claim form already submitted for this treatment report.', 'info')
        return redirect(url_for('patient_claim_success', claim_id=existing_claim.claim_id))
    
    # Get case details
    if treatment_report.case_source == 'normal':
        request_obj = treatment_report.request
        case_obj = request_obj
        case_type_display = 'Normal Case'
    else:
        case_obj = treatment_report.accident_case
        request_obj = None
        case_type_display = 'Accident Case'
    
    if request.method == 'POST':
        from datetime import datetime as dt
        
        # Get form data
        patient_serial_number = request.form.get('patient_serial_number')
        patient_name = request.form.get('patient_name')
        address = request.form.get('address')
        disease_injury = request.form.get('disease_injury')
        treatment_from_date_str = request.form.get('treatment_from_date')
        treatment_to_date_str = request.form.get('treatment_to_date')
        current_condition = request.form.get('current_condition')
        claim_type = request.form.get('claim_type')  # 'paisa_claim' or 'samaan_claim'
        
        # Validate that only one claim type is selected
        if claim_type not in ['paisa_claim', 'samaan_claim']:
            flash('Please select a claim type.', 'danger')
            return render_template('patient/patient_claim_form.html', 
                                 treatment_report=treatment_report,
                                 case_obj=case_obj,
                                 case_type_display=case_type_display)
        
        # Parse dates
        treatment_from_date = None
        treatment_to_date = None
        if treatment_from_date_str:
            treatment_from_date = dt.strptime(treatment_from_date_str, '%Y-%m-%d').date()
        if treatment_to_date_str:
            treatment_to_date = dt.strptime(treatment_to_date_str, '%Y-%m-%d').date()
        
        # Handle medical report upload
        medical_report_url = None
        medical_report = request.files.get('medical_report')
        if medical_report and allowed_file(medical_report.filename):
            filename = secure_filename(f"claim_medical_{treatment_report_id}_{medical_report.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'medical_reports', filename)
            medical_report.save(filepath)
            medical_report_url = f"uploads/medical_reports/{filename}"
        
        # Get claim type specific details
        payment_method = None
        bank_name = None
        account_holder_name = None
        account_number = None
        ifsc_code = None
        upi_id = None
        upi_name = None
        qr_code_url = None
        receiver_name = None
        receiver_mobile = None
        delivery_address = None
        pincode = None
        
        if claim_type == 'paisa_claim':
            # Only one payment method allowed
            payment_method = request.form.get('payment_method')  # 'bank', 'upi', or 'qr_code'
            
            if payment_method == 'bank':
                bank_name = request.form.get('bank_name')
                account_holder_name = request.form.get('account_holder_name')
                account_number = request.form.get('account_number')
                ifsc_code = request.form.get('ifsc_code')
            elif payment_method == 'upi':
                upi_id = request.form.get('upi_id')
                upi_name = request.form.get('upi_name')
            elif payment_method == 'qr_code':
                qr_file = request.files.get('qr_code')
                if qr_file and allowed_file(qr_file.filename):
                    filename = secure_filename(f"qr_code_{treatment_report_id}_{qr_file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'qr_codes', filename)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    qr_file.save(filepath)
                    qr_code_url = f"uploads/qr_codes/{filename}"
        elif claim_type == 'samaan_claim':
            receiver_name = request.form.get('receiver_name')
            receiver_mobile = request.form.get('receiver_mobile')
            delivery_address = request.form.get('delivery_address')
            pincode = request.form.get('pincode')
        
        # Create patient claim
        patient_claim = PatientClaim(
            request_id=treatment_report.request_id,
            accident_id=treatment_report.accident_id,
            treatment_report_id=treatment_report_id,
            patient_id=treatment_report.patient_id,
            hospital_id=treatment_report.hospital_id,
            case_source=treatment_report.case_source,
            patient_serial_number=patient_serial_number,
            patient_name=patient_name,
            address=address,
            disease_injury=disease_injury,
            medical_report_url=medical_report_url,
            treatment_from_date=treatment_from_date,
            treatment_to_date=treatment_to_date,
            current_condition=current_condition,
            claim_type=claim_type,
            payment_method=payment_method,
            bank_name=bank_name,
            account_holder_name=account_holder_name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            upi_id=upi_id,
            upi_name=upi_name,
            qr_code_url=qr_code_url,
            receiver_name=receiver_name,
            receiver_mobile=receiver_mobile,
            delivery_address=delivery_address,
            pincode=pincode,
            status='pending'
        )
        db.session.add(patient_claim)
        db.session.flush()
        
        # Notify admin (patient notification type)
        claim_type_text = 'Paisa Claim (Financial Help)' if claim_type == 'paisa_claim' else 'Samaan Claim (Food/Essentials)'
        notify_admin(
            title='New Patient Claim Submitted',
            message=f'Patient {patient_name} has submitted a {claim_type_text}. Serial Number: {patient_serial_number}',
            notification_type='patient_claim',
            related_id=patient_claim.claim_id
        )
        
        db.session.commit()
        
        flash('Claim form submitted successfully! Admin will review your request.', 'success')
        return redirect(url_for('patient_claim_success', claim_id=patient_claim.claim_id))
    
    return render_template('patient/patient_claim_form.html', 
                         treatment_report=treatment_report,
                         case_obj=case_obj,
                         case_type_display=case_type_display)

@app.route('/patient-claim-success/<int:claim_id>')
def patient_claim_success(claim_id):
    """Success page after claim submission"""
    claim = PatientClaim.query.get_or_404(claim_id)
    return render_template('patient/patient_claim_success.html', claim=claim)

@app.route('/search-disease', methods=['GET', 'POST'])
def search_disease():
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            # Get unique diseases from HospitalDisease mapping (selected by approved hospitals)
            hospital_diseases = db.session.query(HospitalDisease.disease_name).join(
                Hospital, HospitalDisease.hospital_id == Hospital.id
            ).filter(
                Hospital.admin_approved == True,
                HospitalDisease.disease_name.ilike(f'%{query}%')
            ).distinct().all()
            
            # Get Disease objects for these disease names
            disease_names = [hd[0] for hd in hospital_diseases]
            diseases = Disease.query.filter(
                Disease.name.in_(disease_names),
                Disease.admin_approved == True
            ).all()
            return render_template('patient/disease_results.html', diseases=diseases, query=query)
    # Handle GET request with query parameter (for popular diseases links)
    query = request.args.get('query', '').strip()
    if query:
        # Get unique diseases from HospitalDisease mapping
        hospital_diseases = db.session.query(HospitalDisease.disease_name).join(
            Hospital, HospitalDisease.hospital_id == Hospital.id
        ).filter(
            Hospital.admin_approved == True,
            HospitalDisease.disease_name.ilike(f'%{query}%')
        ).distinct().all()
        
        disease_names = [hd[0] for hd in hospital_diseases]
        diseases = Disease.query.filter(
            Disease.name.in_(disease_names),
            Disease.admin_approved == True
        ).all()
        return render_template('patient/disease_results.html', diseases=diseases, query=query)
    # Show all available diseases (selected by approved hospitals)
    all_hospital_diseases = db.session.query(HospitalDisease.disease_name).join(
        Hospital, HospitalDisease.hospital_id == Hospital.id
    ).filter(
        Hospital.admin_approved == True
    ).distinct().all()
    
    disease_names = [hd[0] for hd in all_hospital_diseases]
    all_diseases = Disease.query.filter(
        Disease.name.in_(disease_names),
        Disease.admin_approved == True
    ).all() if disease_names else []
    
    return render_template('patient/search_disease.html', all_diseases=all_diseases)

@app.route('/api/disease-suggestions')
def disease_suggestions():
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify([])
    
    # Get unique diseases from HospitalDisease mapping (selected by approved hospitals)
    hospital_diseases = db.session.query(HospitalDisease.disease_name).join(
        Hospital, HospitalDisease.hospital_id == Hospital.id
    ).filter(
        Hospital.admin_approved == True,
        HospitalDisease.disease_name.ilike(f'%{query}%')
    ).distinct().limit(10).all()
    
    # Get Disease objects
    disease_names = [hd[0] for hd in hospital_diseases]
    diseases = Disease.query.filter(
        Disease.name.in_(disease_names),
        Disease.admin_approved == True
    ).all()
    
    suggestions = [{'id': d.disease_id, 'name': d.name} for d in diseases]
    return jsonify(suggestions)

@app.route('/disease/<int:disease_id>')
def disease_detail(disease_id):
    disease = Disease.query.get_or_404(disease_id)
    # Only show disease if approved
    if not disease.admin_approved:
        flash('This disease is not yet approved by admin.', 'warning')
        return redirect(url_for('search_disease'))
    
    # Find hospitals that selected this disease during registration (via HospitalDisease mapping)
    hospital_disease_mappings = HospitalDisease.query.filter_by(
        disease_name=disease.name
    ).all()
    
    hospital_ids = [hd.hospital_id for hd in hospital_disease_mappings]
    
    # Get approved hospitals that selected this disease
    hospitals = Hospital.query.filter(
        Hospital.id.in_(hospital_ids),
        Hospital.admin_approved == True
    ).all()
    
    # Get doctors for each hospital
    hospital_doctors = {}
    for hospital in hospitals:
        doctors = Doctor.query.filter_by(hospital_id=hospital.hospital_id).all()
        hospital_doctors[hospital.hospital_id] = doctors
    
    return render_template('patient/disease_detail.html', 
                         disease=disease, 
                         hospitals=hospitals,
                         hospital_doctors=hospital_doctors)

@app.route('/patient-register/<int:disease_id>/<int:hospital_id>', methods=['GET', 'POST'])
def patient_disease_register(disease_id, hospital_id):
    disease = Disease.query.get_or_404(disease_id)
    hospital = Hospital.query.get_or_404(hospital_id)

    if request.method == 'POST':
        from datetime import datetime

        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        gender = request.form.get('gender')
        dob_str = request.form.get('dob')
        address = request.form.get('address')
        aadhar_no = request.form.get('aadhar_no')
        disease_duration = request.form.get('disease_duration')
        current_condition = request.form.get('current_condition')
        problem_description = request.form.get('problem_description')
        symptoms = request.form.get('symptoms')
        has_ayushman = request.form.get('has_ayushman', 'no')

        dob = None
        if dob_str:
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()

        # Check patient
        patient = Patient.query.filter_by(aadhar_no=aadhar_no).first()

        if not patient:
            # Aadhaar upload
            aadhar_file = request.files.get('aadhar_document')
            aadhar_url = None
            if aadhar_file and allowed_file(aadhar_file.filename):
                filename = secure_filename(f"{aadhar_no}_{aadhar_file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'aadhaar', filename)
                aadhar_file.save(filepath)
                aadhar_url = f"uploads/aadhaar/{filename}"

            patient = Patient(
                name=name,
                phone=phone,
                email=email,
                address=address,
                aadhar_no=aadhar_no,
                dob=dob,
                gender=gender,
                has_ayushman=has_ayushman,
                aadhar_document_url=aadhar_url
            )
            db.session.add(patient)
            db.session.flush()
        else:
            # ✅ UPDATE existing patient
            patient.name = name
            patient.phone = phone
            patient.email = email
            patient.address = address
            patient.gender = gender
            patient.dob = dob
            patient.has_ayushman = has_ayushman

        # Create patient request
        serial_number = generate_patient_serial_number()

        patient_request = PatientRequest(
            patient_id=patient.patient_id,
            disease_id=disease_id,
            hospital_id=hospital_id,
            problem_description=problem_description,
            symptoms=symptoms,
            disease_duration=disease_duration,
            current_condition=current_condition,
            patient_serial_number=serial_number,
            status='pending'
        )

        db.session.add(patient_request)
        db.session.commit()

        flash('Request submitted successfully!', 'success')
        return redirect(url_for('request_success', request_id=patient_request.request_id))

    return render_template('patient/patient_register.html', disease=disease, hospital=hospital)




@app.route('/request-success/<int:request_id>')
def request_success(request_id):
    request_obj = PatientRequest.query.get_or_404(request_id)
    return render_template('patient/request_success.html', request=request_obj)

@app.route('/patient/panel-old')
def patient_panel_old():
    """Patient Panel - View all their requests (OLD - DEPRECATED)"""
    aadhar_no = request.args.get('aadhar_no', '')
    if not aadhar_no:
        return render_template('patient/panel_login.html')
    
    patient = Patient.query.filter_by(aadhar_no=aadhar_no).first()
    if not patient:
        flash('Patient not found with this Aadhaar number', 'danger')
        return render_template('patient/panel_login.html')
    
    # Get all requests for this patient
    patient_requests = PatientRequest.query.filter_by(patient_id=patient.patient_id).order_by(PatientRequest.created_at.desc()).all()
    
    # Get all accident cases for this patient
    accident_cases = AccidentCase.query.filter_by(patient_id=patient.patient_id).order_by(AccidentCase.created_at.desc()).all()
    
    # Get unread notifications for this patient
    unread_notifications = Notification.query.filter_by(
        user_type='patient',
        user_id=patient.patient_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    return render_template('patient/panel.html', 
                         patient=patient, 
                         requests=patient_requests,
                         accident_cases=accident_cases,
                         unread_notifications=unread_notifications)

@app.route('/api/patient-requests')
def api_patient_requests():
    """API endpoint for real-time patient requests (for Admin)"""
    requests = PatientRequest.query.order_by(PatientRequest.created_at.desc()).limit(50).all()
    return jsonify([{
        'request_id': r.request_id,
        'patient_name': r.patient.name,
        'disease': r.disease.name,
        'hospital': r.hospital.name,
        'status': r.status,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for r in requests])

@app.route('/api/treatment-reports')
def api_treatment_reports():
    """API endpoint for real-time treatment reports (for Admin)"""
    reports = TreatmentReport.query.order_by(TreatmentReport.created_at.desc()).limit(50).all()
    return jsonify([{
        'report_id': r.report_id,
        'patient_name': r.patient.name,
        'hospital': r.hospital.name,
        'total_expense': str(r.total_expense) if r.total_expense else None,
        'payment_status': r.payment_status,
        'status': r.status,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for r in reports])

@app.route('/api/notifications/<user_type>/<int:user_id>')
def api_notifications(user_type, user_id):
    """API endpoint for real-time notifications"""
    notifications = Notification.query.filter_by(
        user_type=user_type,
        user_id=user_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(20).all()
    
    return jsonify([{
        'notification_id': n.notification_id,
        'title': n.title,
        'message': n.message,
        'type': n.notification_type,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for n in notifications])

@app.route('/api/mark-notification-read/<int:notification_id>', methods=['POST'])
def mark_notification_read(notification_id):
    """Mark notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/delete-notification/<int:notification_id>', methods=['POST'])
def delete_notification(notification_id):
    """Delete a single notification"""
    notification = Notification.query.get_or_404(notification_id)
    db.session.delete(notification)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/clear-all-notifications', methods=['POST'])
def clear_all_notifications():
    """Clear all notifications for a user"""
    user_type = request.json.get('user_type')  # admin, hospital, patient
    user_id = request.json.get('user_id')
    
    if not user_type or not user_id:
        return jsonify({'error': 'Missing parameters'}), 400
    
    notifications = Notification.query.filter_by(
        user_type=user_type,
        user_id=user_id,
        is_read=False
    ).all()
    
    for notification in notifications:
        db.session.delete(notification)
    
    db.session.commit()
    return jsonify({'success': True, 'deleted': len(notifications)})

# Routes - Hospital Side
@app.route('/hospital/register', methods=['GET', 'POST'])
def hospital_register():

    if request.method == 'POST':

        # -------- BASIC DATA --------
        name = request.form.get('name')
        address = request.form.get('address')
        contact = request.form.get('contact')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        hospital_specialities = request.form.getlist('Specialities')

        agreement = request.form.get('agreement')
        captcha = request.form.get('captcha', '').strip().upper()
        captcha_answer = request.form.get('captcha_answer', '').strip().upper()

        # -------- VALIDATION --------
        if not all([name, address, contact, email, password, confirm_password]):
            flash('Please fill all required fields', 'danger')
            return render_template('hospital/register.html')

        if not agreement:
            flash('Please accept the Terms & Conditions', 'danger')
            return render_template('hospital/register.html')

        if captcha != captcha_answer:
            flash('Invalid captcha code. Please try again.', 'danger')
            return render_template('hospital/register.html')

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('hospital/register.html')

        if not is_strong_password(password):
            flash(
                'Password must contain at least 1 Capital letter, 1 Number, and 1 Special character',
                'danger'
            )
            return render_template('hospital/register.html')

        # -------- EMAIL CHECK --------
        if Hospital.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('hospital/register.html')

        # -------- GET DISEASES SELECTED BY HOSPITAL --------
        hospital_diseases = request.form.getlist('diseases[]')  # Diseases selected by hospital

        # -------- CREATE HOSPITAL --------
        
        hospital = Hospital(
    name=name,
    address=address,
    contact=contact,
    email=email,
    password_hash=generate_password_hash(password),
    speciality=",".join(hospital_specialities),
    admin_approved=False
)

       
        db.session.add(hospital)
        db.session.flush()   # hospital.id available

        # -------- SAVE HOSPITAL-DISEASE MAPPING --------
        for disease_name in hospital_diseases:
            if disease_name.strip():
                # Create or get disease
                disease = Disease.query.filter_by(name=disease_name.strip()).first()
                if not disease:
                    # Create new disease (will be auto-approved when hospital is approved)
                    try:
                        disease = Disease(
                            name=disease_name.strip(),
                            admin_approved=False,  # Will be approved when hospital is approved
                            hospital_id=hospital.hospital_id
                        )
                        db.session.add(disease)
                        db.session.flush()
                    except Exception as e:
                        # Disease with same name might already exist, just use it
                        disease = Disease.query.filter_by(name=disease_name.strip()).first()
                
                # Create hospital-disease mapping (even if disease already exists)
                hospital_disease = HospitalDisease(
                    hospital_id=hospital.id,
                    disease_name=disease_name.strip()
                )
                db.session.add(hospital_disease)

        # -------- ADD DOCTORS --------
        doctor_names = request.form.getlist('doctor_name[]')
        doctor_qualifications = request.form.getlist('doctor_qualification[]')
        doctor_specializations = request.form.getlist('doctor_specialization[]')
        doctor_images = request.files.getlist('doctor_image[]')

        for i in range(len(doctor_names)):
            if doctor_names[i].strip():
                image_url = None

                if (
                    i < len(doctor_images)
                    and doctor_images[i]
                    and allowed_file(doctor_images[i].filename)
                ):
                    filename = secure_filename(
                        f"doctor_{hospital.id}_{i}_{doctor_images[i].filename}"
                    )
                    folder = os.path.join(app.config['UPLOAD_FOLDER'], 'doctors')
                    os.makedirs(folder, exist_ok=True)
                    doctor_images[i].save(os.path.join(folder, filename))
                    image_url = f"uploads/doctors/{filename}"

                doctor = Doctor(
                     hospital_id=hospital.hospital_id,
                    name=doctor_names[i].strip(),
                    qualification=doctor_qualifications[i] if i < len(doctor_qualifications) else '',
                    specialization=doctor_specializations[i] if i < len(doctor_specializations) else '',
                    image_url=image_url
                )
                db.session.add(doctor)

        db.session.commit()

        # -------- ADMIN NOTIFICATION --------
        notify_admin(
            title='New Hospital Registration',
            message=f'Hospital "{name}" has registered and is pending approval.',
            notification_type='hospital_registration',
            related_id=hospital.id
        )

        flash(
            'Hospital registration submitted successfully! Pending admin approval.',
            'success'
        )
        return redirect(url_for('hospital_login'))

    # -------- GET REQUEST --------
    return render_template('hospital/register.html')



@app.route('/hospital/login', methods=['GET', 'POST'])
def hospital_login():
    # ✅ Redirect if already logged in
    if session.get('hospital_id') and session.get('user_role') == 'hospital':
        return redirect(url_for('hospital_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        hospital = Hospital.query.filter_by(email=email).first()
        if hospital and hospital.password_hash and check_password_hash(hospital.password_hash, password):
            # Check if hospital is approved by admin
            if not hospital.admin_approved:
                flash('Your hospital registration is pending admin approval. Please wait for approval.', 'warning')
                return render_template('hospital/login.html')
            session['hospital_id'] = hospital.hospital_id
            session['hospital_name'] = hospital.name
            session['user_role'] = 'hospital'  # ✅ ADD ROLE
            flash('Login successful!', 'success')
            return redirect(url_for('hospital_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('hospital/login.html')

@app.route('/hospital/logout')
def hospital_logout():
    session.pop('hospital_id', None)
    session.pop('hospital_name', None)
    session.pop('user_role', None)  # ✅ CLEAR ROLE
    flash('Logged out successfully', 'info')
    return redirect(url_for('hospital_login'))

@app.route('/hospital/info', methods=['GET', 'POST'])
@login_required_hospital
@role_required('hospital')
def hospital_info():
    hospital_id = session.get('hospital_id')
    hospital = Hospital.query.get_or_404(hospital_id)
    doctors = Doctor.query.filter_by(hospital_id=hospital_id).all()
    
    if request.method == 'POST':
        # Update hospital info
        hospital.name = request.form.get('name', hospital.name)
        hospital.address = request.form.get('address', hospital.address)
        hospital.speciality = request.form.get('speciality', hospital.speciality)
        hospital.contact = request.form.get('contact', hospital.contact)
        hospital.email = request.form.get('email', hospital.email)
        
        # Update password if provided
        new_password = request.form.get('new_password')
        if new_password and len(new_password) >= 6:
            hospital.password_hash = generate_password_hash(new_password)
        
        db.session.commit()
        flash('Hospital information updated successfully!', 'success')
        return redirect(url_for('hospital_info'))
    
    return render_template('hospital/info.html', hospital=hospital, doctors=doctors)

@app.route('/hospital/dashboard')
@login_required_hospital
@role_required('hospital')
def hospital_dashboard():
    hospital_id = session.get('hospital_id')
    hospital = Hospital.query.get_or_404(hospital_id)
    
    # Get hospital diseases (selected during registration)
    hospital_diseases = HospitalDisease.query.filter_by(hospital_id=hospital.id).all()
    selected_diseases = [hd.disease_name for hd in hospital_diseases]
    
    # Get hospital specialties
    specialties = hospital.speciality.split(',') if hospital.speciality else []
    
    # Get doctors
    doctors = Doctor.query.filter_by(hospital_id=hospital_id).all()
    
    # Get pending requests
    pending_requests = PatientRequest.query.filter_by(
        hospital_id=hospital_id,
        status='pending'
    ).order_by(PatientRequest.created_at.desc()).all()
    
    # Get all requests (including completed - not deleted)
    all_requests = PatientRequest.query.filter(
        PatientRequest.hospital_id == hospital_id
    ).order_by(PatientRequest.created_at.desc()).all()
    
    # Get completed requests (for history)
    completed_requests = PatientRequest.query.filter(
        PatientRequest.hospital_id == hospital_id,
        PatientRequest.status.in_(['treatment_submitted', 'completed', 'closed'])
    ).order_by(PatientRequest.created_at.desc()).all()
    
    # Get pending accident cases
    pending_accident_cases = AccidentCase.query.filter_by(
        hospital_id=hospital_id,
        status='pending'
    ).order_by(AccidentCase.created_at.desc()).all()
    
    # Get all accident cases
    all_accident_cases = AccidentCase.query.filter_by(
        hospital_id=hospital_id
    ).order_by(AccidentCase.created_at.desc()).limit(20).all()
    
    # Get unread notifications
    unread_notifications = Notification.query.filter_by(
        user_type='hospital',
        user_id=hospital_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    # Get treatment reports for all requests
    request_ids = [req.request_id for req in all_requests]
    treatment_reports = {}
    if request_ids:
        reports = TreatmentReport.query.filter(
            TreatmentReport.request_id.in_(request_ids)
        ).all()
        for report in reports:
            treatment_reports[report.request_id] = report
    
    return render_template('hospital/dashboard.html',
                         hospital=hospital,
                         selected_diseases=selected_diseases,
                         specialties=specialties,
                         doctors=doctors,
                         pending_requests=pending_requests,
                         all_requests=all_requests,
                         completed_requests=completed_requests,
                         pending_accident_cases=pending_accident_cases,
                         all_accident_cases=all_accident_cases,
                         unread_notifications=unread_notifications,
                         treatment_reports=treatment_reports)

@app.route('/hospital/history')
@login_required_hospital
@role_required('hospital')
def hospital_history():
    """View history of all past patients, treatments, and requests"""
    hospital_id = session.get('hospital_id')
    
    # Get all completed requests (not deleted - saved in history)
    completed_requests = PatientRequest.query.filter(
        PatientRequest.hospital_id == hospital_id,
        PatientRequest.status.in_(['treatment_submitted', 'completed', 'closed', 'approved'])
    ).order_by(PatientRequest.created_at.desc()).all()
    
    # Get all completed accident cases
    completed_accidents = AccidentCase.query.filter(
        AccidentCase.hospital_id == hospital_id,
        AccidentCase.status.in_(['treatment_complete', 'discharged', 'approved'])
    ).order_by(AccidentCase.created_at.desc()).all()
    
    # Get all treatment reports
    treatment_reports = TreatmentReport.query.filter_by(
        hospital_id=hospital_id
    ).order_by(TreatmentReport.created_at.desc()).all()
    
    # Get unique patients from requests
    patient_ids = set()
    for req in completed_requests:
        patient_ids.add(req.patient_id)
    for acc in completed_accidents:
        patient_ids.add(acc.patient_id)
    
    patients = Patient.query.filter(Patient.patient_id.in_(patient_ids)).all() if patient_ids else []
    
    return render_template('hospital/history.html',
                         completed_requests=completed_requests,
                         completed_accidents=completed_accidents,
                         treatment_reports=treatment_reports,
                         patients=patients)

@app.route('/hospital/accident-case/<int:accident_id>')
@login_required_hospital
@role_required('hospital')
def hospital_accident_case_detail(accident_id):
    """Hospital view accident case details"""
    hospital_id = session.get('hospital_id')
    accident_case = AccidentCase.query.get_or_404(accident_id)
    
    if accident_case.hospital_id != hospital_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('hospital_dashboard'))
    
    return render_template('hospital/accident_case_detail.html', accident_case=accident_case)

@app.route('/hospital/accident-case/<int:accident_id>/update-status', methods=['POST'])
@login_required_hospital
@role_required('hospital')
def update_accident_case_status(accident_id):
    """Hospital accept/reject accident case"""
    hospital_id = session.get('hospital_id')
    accident_case = AccidentCase.query.get_or_404(accident_id)
    
    if accident_case.hospital_id != hospital_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    new_status = request.form.get('status')
    patient_serial_number = request.form.get('patient_serial_number', '').strip()
    
    if new_status in ['approved', 'rejected']:
        accident_case.status = new_status
        # Auto-generate serial number if not provided and status is approved
        if new_status == 'approved' and not patient_serial_number:
            # Use the same function as disease cases for consistency
            patient_serial_number = generate_patient_serial_number()
        if patient_serial_number:
            accident_case.patient_serial_number = patient_serial_number
        
        # Notify patient
        if new_status == 'approved':
            notify_patient(
                patient_id=accident_case.patient_id,
                title='Accident Case Accepted',
                message=f'Your accident case has been accepted by {session.get("hospital_name")}. You can visit the hospital.',
                notification_type='accident_case',
                related_id=accident_id
            )
            flash('Accident case accepted! Patient has been notified.', 'success')
        elif new_status == 'rejected':
            notify_patient(
                patient_id=accident_case.patient_id,
                title='Accident Case Rejected',
                message=f'Your accident case has been rejected by {session.get("hospital_name")}.',
                notification_type='accident_case',
                related_id=accident_id
            )
            flash('Accident case rejected! Patient has been notified.', 'info')
        
        db.session.commit()
        return redirect(url_for('hospital_accident_case_detail', accident_id=accident_id))
    
    flash('Invalid status', 'danger')
    return redirect(url_for('hospital_accident_case_detail', accident_id=accident_id))

@app.route('/hospital/accident-case/<int:accident_id>/submit-treatment', methods=['GET', 'POST'])
@login_required_hospital
@role_required('hospital')
def submit_accident_treatment_report(accident_id):
    """Submit treatment report for accident case (unified form)"""
    hospital_id = session.get('hospital_id')
    accident_case = AccidentCase.query.get_or_404(accident_id)
    
    if accident_case.hospital_id != hospital_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('hospital_dashboard'))
    
    # Check if report already exists
    existing_report = TreatmentReport.query.filter_by(accident_id=accident_id).first()
    
    if request.method == 'POST':
        from datetime import datetime as dt
        
        # Get unified form data
        patient_serial_number = request.form.get('patient_serial_number')
        patient_name = request.form.get('patient_name')
        disease_injury = request.form.get('disease_injury')
        treatment_details = request.form.get('treatment_details')
        work_done = request.form.get('work_done')
        admission_date_str = request.form.get('admission_date')
        discharge_date_str = request.form.get('discharge_date')
        final_treatment_report = request.form.get('final_treatment_report')
        case_type = request.form.get('case_type')  # Government or Private
        
        # Financial Details Validation
        payment_method = request.form.get('payment_method')  # 'upi' or 'qr_code'
        payment_receipt = request.files.get('payment_receipt')
        
        # Validate case type selection
        if not case_type:
            flash('❌ Error: Please select case type (Government or Private) before submitting.', 'danger')
            return render_template('hospital/submit_treatment.html', 
                                 request=None,
                                 accident_case=accident_case, 
                                 existing_report=existing_report,
                                 upi_id=UPI_ID)
        
        # Validate based on case type
        if case_type == 'Government':
            # Government case validation
            total_expense = request.form.get('total_expense')
            bill_file = request.files.get('bill_document')
            
            if not total_expense or float(total_expense) <= 0:
                flash('❌ Error: Please enter total treatment amount before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=None,
                                     accident_case=accident_case, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not bill_file or not allowed_file(bill_file.filename):
                flash('❌ Error: Please upload bill document before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=None,
                                     accident_case=accident_case, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
        
        elif case_type == 'Private':
            # Private case validation
            hospital_bill = request.files.get('hospital_bill')
            hospital_bill_amount = request.form.get('hospital_bill_amount')
            test_bill = request.files.get('test_bill')
            test_bill_amount = request.form.get('test_bill_amount')
            medical_bill = request.files.get('medical_bill')
            medical_bill_amount = request.form.get('medical_bill_amount')
            
            if not hospital_bill or not allowed_file(hospital_bill.filename):
                flash('❌ Error: Please upload hospital bill before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=None,
                                     accident_case=accident_case, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not hospital_bill_amount or float(hospital_bill_amount) <= 0:
                flash('❌ Error: Please enter hospital bill amount before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=None,
                                     accident_case=accident_case, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not test_bill or not allowed_file(test_bill.filename):
                flash('❌ Error: Please upload test bill before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=None,
                                     accident_case=accident_case, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not test_bill_amount or float(test_bill_amount) <= 0:
                flash('❌ Error: Please enter test bill amount before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=None,
                                     accident_case=accident_case, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not medical_bill or not allowed_file(medical_bill.filename):
                flash('❌ Error: Please upload medical bill before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=None,
                                     accident_case=accident_case, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not medical_bill_amount or float(medical_bill_amount) <= 0:
                flash('❌ Error: Please enter medical bill amount before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=None,
                                     accident_case=accident_case, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
        
        # Common validation
        if not payment_method:
            flash('❌ Error: Please select a payment option (UPI or QR Code) before submitting.', 'danger')
            return render_template('hospital/submit_treatment.html', 
                                 request=None,
                                 accident_case=accident_case, 
                                 existing_report=existing_report,
                                 upi_id=UPI_ID)
        
        if not payment_receipt or not allowed_file(payment_receipt.filename):
            flash('❌ Error: Please upload payment receipt before submitting.', 'danger')
            return render_template('hospital/submit_treatment.html', 
                                 request=None,
                                 accident_case=accident_case, 
                                 existing_report=existing_report,
                                 upi_id=UPI_ID)
        
        # Parse dates
        admission_date = None
        discharge_date = None
        if admission_date_str:
            admission_date = dt.strptime(admission_date_str, '%Y-%m-%d').date()
            accident_case.admission_date = admission_date
        if discharge_date_str:
            discharge_date = dt.strptime(discharge_date_str, '%Y-%m-%d').date()
            accident_case.discharge_date = discharge_date
            accident_case.status = 'discharged'
        
        # Handle medical report upload
        medical_report_url = None
        medical_report = request.files.get('medical_report')
        if medical_report and allowed_file(medical_report.filename):
            filename = secure_filename(f"medical_report_acc_{accident_id}_{medical_report.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'medical_reports', filename)
            medical_report.save(filepath)
            medical_report_url = f"uploads/medical_reports/{filename}"
        
        # Handle payment receipt upload (mandatory)
        payment_receipt_url = None
        if payment_receipt and allowed_file(payment_receipt.filename):
            filename = secure_filename(f"payment_acc_{accident_id}_{payment_receipt.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'payments', filename)
            payment_receipt.save(filepath)
            payment_receipt_url = f"uploads/payments/{filename}"
        
        # Handle case type specific fields
        total_expense = None
        bill_url = None
        hospital_bill_url = None
        hospital_bill_amount_val = None
        test_bill_url = None
        test_bill_amount_val = None
        medical_bill_url = None
        medical_bill_amount_val = None
        net_amount = None
        payment_amount_10_percent = None
        
        if case_type == 'Government':
            # Government case processing
            total_expense = request.form.get('total_expense')
            bill_file = request.files.get('bill_document')
            if bill_file and allowed_file(bill_file.filename):
                filename = secure_filename(f"bill_acc_{accident_id}_{bill_file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'bills', filename)
                bill_file.save(filepath)
                bill_url = f"uploads/bills/{filename}"
            
            # Calculate 10% of total expense
            if total_expense:
                payment_amount_10_percent = Decimal(total_expense) * Decimal('0.10')
        
        elif case_type == 'Private':
            # Private case processing
            hospital_bill = request.files.get('hospital_bill')
            hospital_bill_amount_val = Decimal(request.form.get('hospital_bill_amount'))
            test_bill = request.files.get('test_bill')
            test_bill_amount_val = Decimal(request.form.get('test_bill_amount'))
            medical_bill = request.files.get('medical_bill')
            medical_bill_amount_val = Decimal(request.form.get('medical_bill_amount'))
            
            # Upload bills
            if hospital_bill and allowed_file(hospital_bill.filename):
                filename = secure_filename(f"hospital_bill_acc_{accident_id}_{hospital_bill.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'bills', filename)
                hospital_bill.save(filepath)
                hospital_bill_url = f"uploads/bills/{filename}"
            
            if test_bill and allowed_file(test_bill.filename):
                filename = secure_filename(f"test_bill_acc_{accident_id}_{test_bill.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'bills', filename)
                test_bill.save(filepath)
                test_bill_url = f"uploads/bills/{filename}"
            
            if medical_bill and allowed_file(medical_bill.filename):
                filename = secure_filename(f"medical_bill_acc_{accident_id}_{medical_bill.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'bills', filename)
                medical_bill.save(filepath)
                medical_bill_url = f"uploads/bills/{filename}"
            
            # Calculate: Total = Hospital + Test + Medical
            total_bills = hospital_bill_amount_val + test_bill_amount_val + medical_bill_amount_val
            
            # Net Amount = Total - Medical Bill
            net_amount = total_bills - medical_bill_amount_val
            
            # 10% of Net Amount
            payment_amount_10_percent = net_amount * Decimal('0.10')
            
            # Store total expense for display (optional)
            total_expense = total_bills
        
        if existing_report:
            # Update existing report
            existing_report.patient_serial_number = patient_serial_number
            existing_report.patient_name = patient_name
            existing_report.disease_injury = disease_injury
            existing_report.treatment_details = treatment_details
            existing_report.work_done = work_done
            existing_report.admission_date = admission_date
            existing_report.discharge_date = discharge_date
            existing_report.final_treatment_report = final_treatment_report
            existing_report.case_type = case_type
            existing_report.payment_amount = payment_amount_10_percent
            existing_report.payment_method = payment_method
            if medical_report_url:
                existing_report.medical_report_url = medical_report_url
            if payment_receipt_url:
                existing_report.payment_screenshot_url = payment_receipt_url
            existing_report.payment_status = 'paid'
            existing_report.status = 'submitted'
            existing_report.updated_at = datetime.utcnow()
            
            # Case type specific updates
            if case_type == 'Government':
                existing_report.total_expense = total_expense if total_expense else None
                if bill_url:
                    existing_report.bill_document_url = bill_url
            elif case_type == 'Private':
                existing_report.hospital_bill_url = hospital_bill_url
                existing_report.hospital_bill_amount = hospital_bill_amount_val
                existing_report.test_bill_url = test_bill_url
                existing_report.test_bill_amount = test_bill_amount_val
                existing_report.medical_bill_url = medical_bill_url
                existing_report.medical_bill_amount = medical_bill_amount_val
                existing_report.net_amount = net_amount
                existing_report.total_expense = total_expense
        else:
            # Create new report
            treatment_report = TreatmentReport(
                request_id=None,  # Accident case
                accident_id=accident_id,
                hospital_id=hospital_id,
                patient_id=accident_case.patient_id,
                case_source='accident',
                patient_serial_number=patient_serial_number or accident_case.patient_serial_number,
                patient_name=patient_name or accident_case.patient_name,
                disease_injury=disease_injury or accident_case.current_condition,
                treatment_details=treatment_details,
                work_done=work_done,
                admission_date=admission_date,
                discharge_date=discharge_date,
                final_treatment_report=final_treatment_report,
                case_type=case_type,
                medical_report_url=medical_report_url,
                payment_amount=payment_amount_10_percent,
                payment_screenshot_url=payment_receipt_url,
                payment_method=payment_method,
                payment_status='paid',
                status='submitted'
            )
            
            # Case type specific fields
            if case_type == 'Government':
                treatment_report.total_expense = total_expense if total_expense else None
                treatment_report.bill_document_url = bill_url
            elif case_type == 'Private':
                treatment_report.hospital_bill_url = hospital_bill_url
                treatment_report.hospital_bill_amount = hospital_bill_amount_val
                treatment_report.test_bill_url = test_bill_url
                treatment_report.test_bill_amount = test_bill_amount_val
                treatment_report.medical_bill_url = medical_bill_url
                treatment_report.medical_bill_amount = medical_bill_amount_val
                treatment_report.net_amount = net_amount
                treatment_report.total_expense = total_expense
            
            db.session.add(treatment_report)
            db.session.flush()  # Get the report_id
        
        # Get report_id for notifications
        report_id = treatment_report.report_id if 'treatment_report' in locals() else existing_report.report_id if existing_report else accident_id
        
        # Notify admin (hospital notification type)
        notify_admin(
            title='Treatment Report Submitted',
            message=f'Hospital {session.get("hospital_name")} has submitted treatment report for patient {patient_name or accident_case.patient_name}. Serial Number: {patient_serial_number or "N/A"}',
            notification_type='hospital_treatment_report',
            related_id=report_id
        )
        
        # Notify patient about treatment submission
        notify_patient(
            patient_id=accident_case.patient_id,
            title='Treatment Report Submitted',
            message=f'Your treatment report has been submitted by {session.get("hospital_name")}. You can now submit a claim form.',
            notification_type='treatment_submitted',
            related_id=report_id
        )
        
        db.session.commit()
        flash('Treatment report submitted successfully to Admin! Patient has been notified.', 'success')
        return redirect(url_for('hospital_accident_case_detail', accident_id=accident_id))
    
    return render_template('hospital/submit_treatment.html', 
                         request=None,  # For accident cases, request is None
                         accident_case=accident_case,
                         existing_report=existing_report,
                         upi_id=UPI_ID)

@app.route('/hospital/accident-case/<int:accident_id>/update-treatment', methods=['POST'])
@login_required_hospital
@role_required('hospital')
def update_accident_treatment(accident_id):
    """Hospital update admission/discharge dates (DEPRECATED - use submit-treatment instead)"""
    hospital_id = session.get('hospital_id')
    accident_case = AccidentCase.query.get_or_404(accident_id)
    
    if accident_case.hospital_id != hospital_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    from datetime import datetime as dt
    
    admission_date_str = request.form.get('admission_date')
    discharge_date_str = request.form.get('discharge_date')
    
    if admission_date_str:
        accident_case.admission_date = dt.strptime(admission_date_str, '%Y-%m-%d').date()
    
    if discharge_date_str:
        accident_case.discharge_date = dt.strptime(discharge_date_str, '%Y-%m-%d').date()
        accident_case.status = 'discharged'
        
        # Notify patient about discharge
        notify_patient(
            patient_id=accident_case.patient_id,
            title='Treatment Completed - Discharged',
            message=f'Your treatment at {session.get("hospital_name")} is completed. You can now submit a claim form.',
            notification_type='accident_case',
            related_id=accident_id
        )
    
    db.session.commit()
    flash('Treatment details updated successfully!', 'success')
    return redirect(url_for('hospital_accident_case_detail', accident_id=accident_id))

@app.route('/hospital/request/<int:request_id>')
@login_required_hospital
@role_required('hospital')
def hospital_request_detail(request_id):
    hospital_id = session.get('hospital_id')
    request_obj = PatientRequest.query.get_or_404(request_id)
    
    if request_obj.hospital_id != hospital_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('hospital_dashboard'))
    
    # Get treatment report if exists
    treatment_report = TreatmentReport.query.filter_by(request_id=request_id).first()

    # Calculate 10% amount safely (Decimal)
    amount_10_percent = None
    if treatment_report and treatment_report.total_expense:
        amount_10_percent = treatment_report.total_expense * Decimal('0.10')

    return render_template(
        'hospital/request_detail.html',
        request=request_obj,
        treatment_report=treatment_report,
        upi_id=UPI_ID,
        amount_10_percent=amount_10_percent
    )


@app.route('/hospital/request/<int:request_id>/update-status', methods=['POST'])
@login_required_hospital
@role_required('hospital')
def update_request_status(request_id):
    hospital_id = session.get('hospital_id')
    request_obj = PatientRequest.query.get_or_404(request_id)
    
    if request_obj.hospital_id != hospital_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    new_status = request.form.get('status')
    if new_status in ['approved', 'rejected', 'pending']:
        request_obj.status = new_status
        
        # Notify patient when hospital accepts or rejects
        if new_status == 'approved':
            notify_patient(
                patient_id=request_obj.patient_id,
                title='Request Accepted',
                message=f'Your request has been accepted by {session.get("hospital_name")}. You can visit the hospital.',
                notification_type='request_accepted',
                related_id=request_id
            )
            flash('Request accepted! Patient has been notified.', 'success')
        elif new_status == 'rejected':
            notify_patient(
                patient_id=request_obj.patient_id,
                title='Request Rejected',
                message=f'Your request has been rejected by {session.get("hospital_name")}.',
                notification_type='request_rejected',
                related_id=request_id
            )
            flash('Request rejected! Patient has been notified.', 'info')
        
        db.session.commit()
        return redirect(url_for('hospital_request_detail', request_id=request_id))
    
    flash('Invalid status', 'danger')
    return redirect(url_for('hospital_request_detail', request_id=request_id))

@app.route('/hospital/request/<int:request_id>/submit-treatment', methods=['GET', 'POST'])
@login_required_hospital
@role_required('hospital')
def submit_treatment_report(request_id):
    hospital_id = session.get('hospital_id')
    request_obj = PatientRequest.query.get_or_404(request_id)
    
    if request_obj.hospital_id != hospital_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('hospital_dashboard'))
    
    # Check if report already exists
    existing_report = TreatmentReport.query.filter_by(request_id=request_id).first()
    
    if request.method == 'POST':
        from datetime import datetime as dt
        
        # Get unified form data
        # Use serial number from PatientRequest if not provided in form (should match the auto-generated one)
        patient_serial_number = request.form.get('patient_serial_number') or request_obj.patient_serial_number
        patient_name = request.form.get('patient_name')
        disease_injury = request.form.get('disease_injury')
        treatment_details = request.form.get('treatment_details')
        work_done = request.form.get('work_done')
        admission_date_str = request.form.get('admission_date')
        discharge_date_str = request.form.get('discharge_date')
        final_treatment_report = request.form.get('final_treatment_report')
        case_type = request.form.get('case_type')  # Government or Private
        
        # Financial Details Validation
        payment_method = request.form.get('payment_method')  # 'upi' or 'qr_code'
        payment_receipt = request.files.get('payment_receipt')
        
        # Validate case type selection
        if not case_type:
            flash('❌ Error: Please select case type (Government or Private) before submitting.', 'danger')
            return render_template('hospital/submit_treatment.html', 
                                 request=request_obj, 
                                 existing_report=existing_report,
                                 upi_id=UPI_ID)
        
        # Validate based on case type
        if case_type == 'Government':
            # Government case validation
            total_expense = request.form.get('total_expense')
            bill_file = request.files.get('bill_document')
            
            if not total_expense or float(total_expense) <= 0:
                flash('❌ Error: Please enter total treatment amount before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=request_obj, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not bill_file or not allowed_file(bill_file.filename):
                flash('❌ Error: Please upload bill document before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=request_obj, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
        
        elif case_type == 'Private':
            # Private case validation
            hospital_bill = request.files.get('hospital_bill')
            hospital_bill_amount = request.form.get('hospital_bill_amount')
            test_bill = request.files.get('test_bill')
            test_bill_amount = request.form.get('test_bill_amount')
            medical_bill = request.files.get('medical_bill')
            medical_bill_amount = request.form.get('medical_bill_amount')
            
            if not hospital_bill or not allowed_file(hospital_bill.filename):
                flash('❌ Error: Please upload hospital bill before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=request_obj, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not hospital_bill_amount or float(hospital_bill_amount) <= 0:
                flash('❌ Error: Please enter hospital bill amount before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=request_obj, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not test_bill or not allowed_file(test_bill.filename):
                flash('❌ Error: Please upload test bill before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=request_obj, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not test_bill_amount or float(test_bill_amount) <= 0:
                flash('❌ Error: Please enter test bill amount before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=request_obj, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not medical_bill or not allowed_file(medical_bill.filename):
                flash('❌ Error: Please upload medical bill before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=request_obj, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
            
            if not medical_bill_amount or float(medical_bill_amount) <= 0:
                flash('❌ Error: Please enter medical bill amount before submitting.', 'danger')
                return render_template('hospital/submit_treatment.html', 
                                     request=request_obj, 
                                     existing_report=existing_report,
                                     upi_id=UPI_ID)
        
        # Common validation
        if not payment_method:
            flash('❌ Error: Please select a payment option (UPI or QR Code) before submitting.', 'danger')
            return render_template('hospital/submit_treatment.html', 
                                 request=request_obj, 
                                 existing_report=existing_report,
                                 upi_id=UPI_ID)
        
        if not payment_receipt or not allowed_file(payment_receipt.filename):
            flash('❌ Error: Please upload payment receipt before submitting.', 'danger')
            return render_template('hospital/submit_treatment.html', 
                                 request=request_obj, 
                                 existing_report=existing_report,
                                 upi_id=UPI_ID)
        
        # Parse dates
        admission_date = None
        discharge_date = None
        if admission_date_str:
            admission_date = dt.strptime(admission_date_str, '%Y-%m-%d').date()
        if discharge_date_str:
            discharge_date = dt.strptime(discharge_date_str, '%Y-%m-%d').date()
        
        # Handle medical report upload
        medical_report_url = None
        medical_report = request.files.get('medical_report')
        if medical_report and allowed_file(medical_report.filename):
            filename = secure_filename(f"medical_report_{request_id}_{medical_report.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'medical_reports', filename)
            medical_report.save(filepath)
            medical_report_url = f"uploads/medical_reports/{filename}"
        
        # Handle payment receipt upload (mandatory)
        payment_receipt_url = None
        if payment_receipt and allowed_file(payment_receipt.filename):
            filename = secure_filename(f"payment_{request_id}_{payment_receipt.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'payments', filename)
            payment_receipt.save(filepath)
            payment_receipt_url = f"uploads/payments/{filename}"
        
        # Handle case type specific fields
        total_expense = None
        bill_url = None
        hospital_bill_url = None
        hospital_bill_amount_val = None
        test_bill_url = None
        test_bill_amount_val = None
        medical_bill_url = None
        medical_bill_amount_val = None
        net_amount = None
        payment_amount_10_percent = None
        
        if case_type == 'Government':
            # Government case processing
            total_expense = request.form.get('total_expense')
            bill_file = request.files.get('bill_document')
            if bill_file and allowed_file(bill_file.filename):
                filename = secure_filename(f"bill_{request_id}_{bill_file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'bills', filename)
                bill_file.save(filepath)
                bill_url = f"uploads/bills/{filename}"
            
            # Calculate 10% of total expense
            if total_expense:
                payment_amount_10_percent = Decimal(total_expense) * Decimal('0.10')
        
        elif case_type == 'Private':
            # Private case processing
            hospital_bill = request.files.get('hospital_bill')
            hospital_bill_amount_val = Decimal(request.form.get('hospital_bill_amount'))
            test_bill = request.files.get('test_bill')
            test_bill_amount_val = Decimal(request.form.get('test_bill_amount'))
            medical_bill = request.files.get('medical_bill')
            medical_bill_amount_val = Decimal(request.form.get('medical_bill_amount'))
            
            # Upload bills
            if hospital_bill and allowed_file(hospital_bill.filename):
                filename = secure_filename(f"hospital_bill_{request_id}_{hospital_bill.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'bills', filename)
                hospital_bill.save(filepath)
                hospital_bill_url = f"uploads/bills/{filename}"
            
            if test_bill and allowed_file(test_bill.filename):
                filename = secure_filename(f"test_bill_{request_id}_{test_bill.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'bills', filename)
                test_bill.save(filepath)
                test_bill_url = f"uploads/bills/{filename}"
            
            if medical_bill and allowed_file(medical_bill.filename):
                filename = secure_filename(f"medical_bill_{request_id}_{medical_bill.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'bills', filename)
                medical_bill.save(filepath)
                medical_bill_url = f"uploads/bills/{filename}"
            
            # Calculate: Total = Hospital + Test + Medical
            total_bills = hospital_bill_amount_val + test_bill_amount_val + medical_bill_amount_val
            
            # Net Amount = Total - Medical Bill
            net_amount = total_bills - medical_bill_amount_val
            
            # 10% of Net Amount
            payment_amount_10_percent = net_amount * Decimal('0.10')
            
            # Store total expense for display (optional)
            total_expense = total_bills
        
        if existing_report:
            # Update existing report
            existing_report.patient_serial_number = patient_serial_number
            existing_report.patient_name = patient_name
            existing_report.disease_injury = disease_injury
            existing_report.treatment_details = treatment_details
            existing_report.work_done = work_done
            existing_report.admission_date = admission_date
            existing_report.discharge_date = discharge_date
            existing_report.final_treatment_report = final_treatment_report
            existing_report.case_type = case_type
            existing_report.payment_amount = payment_amount_10_percent
            existing_report.payment_method = payment_method
            if medical_report_url:
                existing_report.medical_report_url = medical_report_url
            if payment_receipt_url:
                existing_report.payment_screenshot_url = payment_receipt_url
            existing_report.payment_status = 'paid'
            existing_report.status = 'submitted'
            existing_report.updated_at = datetime.utcnow()
            
            # Case type specific updates
            if case_type == 'Government':
                existing_report.total_expense = total_expense if total_expense else None
                if bill_url:
                    existing_report.bill_document_url = bill_url
            elif case_type == 'Private':
                existing_report.hospital_bill_url = hospital_bill_url
                existing_report.hospital_bill_amount = hospital_bill_amount_val
                existing_report.test_bill_url = test_bill_url
                existing_report.test_bill_amount = test_bill_amount_val
                existing_report.medical_bill_url = medical_bill_url
                existing_report.medical_bill_amount = medical_bill_amount_val
                existing_report.net_amount = net_amount
                existing_report.total_expense = total_expense
        else:
            # Create new report
            treatment_report = TreatmentReport(
                request_id=request_id,
                accident_id=None,  # Normal case
                hospital_id=hospital_id,
                patient_id=request_obj.patient_id,
                case_source='normal',
                patient_serial_number=patient_serial_number,
                patient_name=patient_name,
                disease_injury=disease_injury,
                treatment_details=treatment_details,
                work_done=work_done,
                admission_date=admission_date,
                discharge_date=discharge_date,
                final_treatment_report=final_treatment_report,
                case_type=case_type,
                medical_report_url=medical_report_url,
                payment_amount=payment_amount_10_percent,
                payment_screenshot_url=payment_receipt_url,
                payment_method=payment_method,
                payment_status='paid',
                status='submitted'
            )
            
            # Case type specific fields
            if case_type == 'Government':
                treatment_report.total_expense = total_expense if total_expense else None
                treatment_report.bill_document_url = bill_url
            elif case_type == 'Private':
                treatment_report.hospital_bill_url = hospital_bill_url
                treatment_report.hospital_bill_amount = hospital_bill_amount_val
                treatment_report.test_bill_url = test_bill_url
                treatment_report.test_bill_amount = test_bill_amount_val
                treatment_report.medical_bill_url = medical_bill_url
                treatment_report.medical_bill_amount = medical_bill_amount_val
                treatment_report.net_amount = net_amount
                treatment_report.total_expense = total_expense
            
            db.session.add(treatment_report)
            db.session.flush()  # Get the report_id
        
        # Update request status
        request_obj.status = 'treatment_submitted'
        
        # Get report_id for notifications
        report_id = treatment_report.report_id if 'treatment_report' in locals() else existing_report.report_id if existing_report else request_id
        
        # Notify admin (hospital notification type)
        notify_admin(
            title='Treatment Report Submitted',
            message=f'Hospital {session.get("hospital_name")} has submitted treatment report for patient {patient_name}. Serial Number: {patient_serial_number}',
            notification_type='hospital_treatment_report',
            related_id=report_id
        )
        
        # Notify patient about treatment submission
        notify_patient(
            patient_id=request_obj.patient_id,
            title='Treatment Report Submitted',
            message=f'Your treatment report has been submitted by {session.get("hospital_name")}. You can now submit a claim form.',
            notification_type='treatment_submitted',
            related_id=report_id
        )
        
        db.session.commit()
        flash('Treatment report submitted successfully to Admin! Patient has been notified.', 'success')
        return redirect(url_for('hospital_request_detail', request_id=request_id))
    
    return render_template('hospital/submit_treatment.html', 
                         request=request_obj, 
                         existing_report=existing_report,
                         upi_id=UPI_ID)

@app.route('/hospital/request/<int:request_id>/submit-payment', methods=['POST'])
@login_required_hospital
@role_required('hospital')
def submit_payment(request_id):
    hospital_id = session.get('hospital_id')
    request_obj = PatientRequest.query.get_or_404(request_id)
    
    if request_obj.hospital_id != hospital_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    treatment_report = TreatmentReport.query.filter_by(request_id=request_id).first()
    if not treatment_report:
        flash('Please submit treatment report first', 'warning')
        return redirect(url_for('submit_treatment_report', request_id=request_id))
    
    # Get payment data
    payment_amount = request.form.get('payment_amount')
    payment_screenshot = request.files.get('payment_screenshot')
    
    if not payment_screenshot or not allowed_file(payment_screenshot.filename):
        flash('Please upload a valid payment screenshot', 'danger')
        return redirect(url_for('hospital_request_detail', request_id=request_id))
    
    # Save payment screenshot
    filename = secure_filename(f"payment_{request_id}_{payment_screenshot.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'payments', filename)
    payment_screenshot.save(filepath)
    payment_url = f"uploads/payments/{filename}"
    
    # Update treatment report
    treatment_report.payment_amount = payment_amount if payment_amount else None
    treatment_report.payment_screenshot_url = payment_url
    treatment_report.upi_id = UPI_ID
    treatment_report.payment_status = 'paid'
    treatment_report.updated_at = datetime.utcnow()
    
    # Notify admin
    notify_admin(
        title='Payment Proof Uploaded',
        message=f'Hospital {session.get("hospital_name")} has uploaded payment proof (10%) for patient {request_obj.patient.name}. Amount: ₹{payment_amount}',
        notification_type='payment',
        related_id=request_id
    )
    
    db.session.commit()
    flash('Payment screenshot uploaded successfully!', 'success')
    return redirect(url_for('hospital_request_detail', request_id=request_id))

# Routes - Admin Side
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    # ✅ Redirect if already logged in
    if session.get('admin_id') and session.get('user_role') == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(username=username).first()
        if admin and check_password_hash(admin.password_hash, password):
            session['admin_id'] = admin.admin_id
            session['admin_username'] = username
            session['user_role'] = 'admin'  # ✅ ADD ROLE
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('user_role', None)  # ✅ CLEAR ROLE
    flash('Logged out successfully', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@login_required_admin
@role_required('admin')
def admin_dashboard():
    admin_id = session.get('admin_id')
    hospitals_count = Hospital.query.count()
    patients_count = Patient.query.count()
    diseases_count = Disease.query.count()
    requests_count = PatientRequest.query.count()
    claims_count = PatientClaim.query.filter_by(status='pending').count()
    
    # Get all hospitals for display
    all_hospitals = Hospital.query.order_by(Hospital.created_at.desc()).limit(10).all()
    
    # Get recent patient requests
    recent_requests = PatientRequest.query.order_by(PatientRequest.created_at.desc()).limit(10).all()
    
    # Get recent treatment reports
    recent_reports = TreatmentReport.query.order_by(TreatmentReport.created_at.desc()).limit(10).all()
    
    # Get pending patient claims
    pending_claims = PatientClaim.query.filter_by(status='pending').order_by(PatientClaim.created_at.desc()).limit(10).all()
    
    # Get unread notifications - separate by type
    all_unread_notifications = Notification.query.filter_by(
        user_type='admin',
        user_id=admin_id,
        is_read=False
    ).order_by(Notification.created_at.desc()).all()
    
    # Separate hospital and patient notifications
    hospital_notifications = [n for n in all_unread_notifications if n.notification_type in ['hospital_treatment_report', 'admin_message']]
    patient_notifications = [n for n in all_unread_notifications if n.notification_type in ['patient_claim', 'treatment_submitted', 'patient_request']]
    
    return render_template('admin/dashboard.html',
                         hospitals_count=hospitals_count,
                         patients_count=patients_count,
                         diseases_count=diseases_count,
                         requests_count=requests_count,
                         claims_count=claims_count,
                         all_hospitals=all_hospitals,
                         recent_requests=recent_requests,
                         recent_reports=recent_reports,
                         pending_claims=pending_claims,
                         hospital_notifications=hospital_notifications[:10],
                         patient_notifications=patient_notifications[:10],
                         unread_notifications=all_unread_notifications[:10])

@app.route('/admin/hospitals')
@login_required_admin
@role_required('admin')
def admin_hospitals():
    # Get all hospitals with status
    all_hospitals = Hospital.query.order_by(Hospital.created_at.desc()).all()
    pending_hospitals = Hospital.query.filter_by(admin_approved=False, rejected_at=None).all()
    approved_hospitals = Hospital.query.filter_by(admin_approved=True).all()
    rejected_hospitals = Hospital.query.filter(Hospital.rejected_at.isnot(None)).all()
    
    return render_template('admin/hospitals.html', 
                         all_hospitals=all_hospitals,
                         hospitals=approved_hospitals,  # For backward compatibility
                         pending_hospitals=pending_hospitals,
                         approved_hospitals=approved_hospitals,
                         rejected_hospitals=rejected_hospitals)

@app.route('/admin/hospital/<int:hospital_id>/view')
@login_required_admin
@role_required('admin')
def admin_view_hospital(hospital_id):
    """Admin view complete hospital registration data"""
    hospital = Hospital.query.get_or_404(hospital_id)
    
    # Get hospital diseases
    hospital_diseases = HospitalDisease.query.filter_by(hospital_id=hospital.id).all()
    selected_diseases = [hd.disease_name for hd in hospital_diseases]
    
    # Get hospital specialties
    specialties = hospital.speciality.split(',') if hospital.speciality else []
    
    # Get doctors
    doctors = Doctor.query.filter_by(hospital_id=hospital.hospital_id).all()
    
    # Get admin who approved/rejected
    approved_by_admin = None
    rejected_by_admin = None
    if hospital.admin_approved_by:
        approved_by_admin = Admin.query.get(hospital.admin_approved_by)
    if hospital.rejected_by:
        rejected_by_admin = Admin.query.get(hospital.rejected_by)
    
    return render_template('admin/hospital_view.html',
                         hospital=hospital,
                         selected_diseases=selected_diseases,
                         specialties=specialties,
                         doctors=doctors,
                         approved_by_admin=approved_by_admin,
                         rejected_by_admin=rejected_by_admin)

@app.route('/admin/hospital/<int:hospital_id>/approve', methods=['POST'])
@login_required_admin
@role_required('admin')
def admin_approve_hospital(hospital_id):
    hospital = Hospital.query.get_or_404(hospital_id)
    admin_id = session.get('admin_id')
    
    hospital.admin_approved = True
    hospital.admin_approved_by = admin_id
    hospital.admin_approved_at = get_ist_now()
    # Clear rejection fields if was previously rejected
    hospital.rejection_reason = None
    hospital.rejected_at = None
    hospital.rejected_by = None
    
    # Also approve all diseases selected by this hospital
    hospital_diseases = HospitalDisease.query.filter_by(hospital_id=hospital.id).all()
    for hd in hospital_diseases:
        # Get or create disease
        disease = Disease.query.filter_by(name=hd.disease_name).first()
        if disease:
            disease.admin_approved = True
            disease.admin_approved_by = admin_id
            disease.admin_approved_at = get_ist_now()
        else:
            # Create disease if it doesn't exist
            disease = Disease(
                name=hd.disease_name,
                admin_approved=True,
                admin_approved_by=admin_id,
                admin_approved_at=get_ist_now(),
                hospital_id=hospital.hospital_id
            )
            db.session.add(disease)
    
    db.session.commit()
    
    # Notify hospital
    notify_hospital(
        hospital_id=hospital_id,
        title='Hospital Registration Approved',
        message=f'Your hospital registration has been approved by admin. You can now login.',
        notification_type='hospital_approved',
        related_id=None
    )
    
    # Log action
    create_notification(
        user_type='admin',
        user_id=admin_id,
        title=f'Hospital Approved: {hospital.name}',
        message=f'Hospital "{hospital.name}" approved by admin',
        notification_type='admin_action',
        related_id=hospital_id
    )
    
    flash(f'Hospital "{hospital.name}" has been approved successfully!', 'success')
    return redirect(url_for('admin_hospitals'))

@app.route('/admin/hospital/<int:hospital_id>/reject', methods=['POST'])
@login_required_admin
@role_required('admin')
def admin_reject_hospital(hospital_id):
    hospital = Hospital.query.get_or_404(hospital_id)
    admin_id = session.get('admin_id')
    rejection_reason = request.form.get('rejection_reason', 'Registration rejected by admin')
    
    if not rejection_reason or not rejection_reason.strip():
        flash('Please provide a rejection reason', 'warning')
        return redirect(url_for('admin_view_hospital', hospital_id=hospital_id))
    
    # Mark as rejected (don't delete - keep for records)
    hospital.admin_approved = False
    hospital.rejection_reason = rejection_reason.strip()
    hospital.rejected_at = get_ist_now()
    hospital.rejected_by = admin_id
    hospital.admin_approved_by = None  # Clear approval if was previously approved
    hospital.admin_approved_at = None
    
    db.session.commit()
    
    # Notify hospital
    notify_hospital(
        hospital_id=hospital_id,
        title='Hospital Registration Rejected',
        message=f'Your hospital registration has been rejected. Reason: {rejection_reason}',
        notification_type='hospital_rejected',
        related_id=None
    )
    
    # Log action
    create_notification(
        user_type='admin',
        user_id=admin_id,
        title=f'Hospital Rejected: {hospital.name}',
        message=f'Hospital "{hospital.name}" rejected. Reason: {rejection_reason}',
        notification_type='admin_action',
        related_id=hospital_id
    )
    
    flash(f'Hospital "{hospital.name}" has been rejected. Reason: {rejection_reason}', 'warning')
    return redirect(url_for('admin_hospitals'))

@app.route('/admin/hospital/<int:hospital_id>/send-message', methods=['POST'])
@login_required_admin
@role_required('admin')
def admin_send_message_to_hospital(hospital_id):
    hospital = Hospital.query.get_or_404(hospital_id)
    message_title = request.form.get('message_title')
    message_content = request.form.get('message_content')
    
    if not message_title or not message_content:
        flash('Please fill all fields', 'danger')
        return redirect(url_for('admin_hospitals'))
    
    # Create notification for hospital
    notify_hospital(
        hospital_id=hospital_id,
        title=f'Admin Message: {message_title}',
        message=message_content,
        notification_type='admin_message',
        related_id=None
    )
    
    flash(f'Message sent successfully to {hospital.name}!', 'success')
    return redirect(url_for('admin_hospitals'))

@app.route('/admin/hospitals/add', methods=['GET', 'POST'])
@login_required_admin
@role_required('admin')
def admin_add_hospital():
    if request.method == 'POST':
        admin_id = session.get('admin_id')
        hospital = Hospital(
            name=request.form.get('name'),
            address=request.form.get('address'),
            speciality=request.form.get('speciality'),
            contact=request.form.get('contact'),
            email=request.form.get('email'),
            password_hash=generate_password_hash(request.form.get('password')),
            admin_approved=True,  # Auto-approve when admin adds directly
            admin_approved_by=admin_id,
            admin_approved_at=get_ist_now()
        )
        db.session.add(hospital)
        db.session.commit()
        flash('Hospital added successfully!', 'success')
        return redirect(url_for('admin_hospitals'))
    
    return render_template('admin/add_hospital.html')

@app.route('/admin/diseases')
@login_required_admin
@role_required('admin')
def admin_diseases():
    diseases = Disease.query.all()
    pending_diseases = Disease.query.filter_by(admin_approved=False).all()
    approved_diseases = Disease.query.filter_by(admin_approved=True).all()
    return render_template('admin/diseases.html', 
                         diseases=diseases,
                         pending_diseases=pending_diseases,
                         approved_diseases=approved_diseases)

@app.route('/admin/disease/<int:disease_id>/approve', methods=['POST'])
@login_required_admin
@role_required('admin')
def admin_approve_disease(disease_id):
    disease = Disease.query.get_or_404(disease_id)
    admin_id = session.get('admin_id')
    
    disease.admin_approved = True
    disease.admin_approved_by = admin_id
    disease.admin_approved_at = get_ist_now()
    
    db.session.commit()
    
    flash(f'Disease "{disease.name}" has been approved successfully!', 'success')
    return redirect(url_for('admin_diseases'))

@app.route('/admin/disease/<int:disease_id>/reject', methods=['POST'])
@login_required_admin
@role_required('admin')
def admin_reject_disease(disease_id):
    disease = Disease.query.get_or_404(disease_id)
    disease_name = disease.name
    
    # Delete disease
    db.session.delete(disease)
    db.session.commit()
    
    flash(f'Disease "{disease_name}" has been rejected and removed.', 'info')
    return redirect(url_for('admin_diseases'))

@app.route('/admin/diseases/add', methods=['GET', 'POST'])
@login_required_admin
@role_required('admin')
def admin_add_disease():
    # Admin should NOT add diseases - diseases are added by hospitals during registration
    flash('Diseases are added by hospitals during registration. Admin cannot add diseases directly.', 'warning')
    return redirect(url_for('admin_diseases'))

@app.route('/admin/patient-requests')
@login_required_admin
@role_required('admin')
def admin_patient_requests():
    # Get all patient requests
    all_requests = PatientRequest.query.order_by(PatientRequest.created_at.desc()).all()
    return render_template('admin/patient_requests.html', requests=all_requests)

@app.route('/admin/patient-request/<int:request_id>')
@login_required_admin
@role_required('admin')
def admin_patient_request_detail(request_id):
    request_obj = PatientRequest.query.get_or_404(request_id)
    treatment_report = TreatmentReport.query.filter_by(request_id=request_id).first()
    return render_template('admin/patient_request_detail.html', 
                         request=request_obj,
                         treatment_report=treatment_report)

@app.route('/admin/treatment-reports')
@login_required_admin
@role_required('admin')
def admin_treatment_reports():
    # Get all treatment reports
    all_reports = TreatmentReport.query.order_by(TreatmentReport.created_at.desc()).all()
    return render_template('admin/treatment_reports.html', reports=all_reports)

@app.route('/admin/treatment-report/<int:report_id>')
@login_required_admin
@role_required('admin')
def admin_treatment_report_detail(report_id):
    report = TreatmentReport.query.get_or_404(report_id)
    return render_template('admin/treatment_report_detail.html', report=report)

@app.route('/admin/treatment-report/<int:report_id>/update-status', methods=['POST'])
@login_required_admin
def admin_update_report_status(report_id):
    report = TreatmentReport.query.get_or_404(report_id)
    new_status = request.form.get('status')
    admin_notes = request.form.get('admin_notes')
    
    if new_status in ['approved', 'rejected', 'closed']:
        report.status = new_status
        if admin_notes:
            report.admin_notes = admin_notes
        report.updated_at = datetime.utcnow()
        
        # Notify hospital
        notify_hospital(
            hospital_id=report.hospital_id,
            title=f'Report {new_status.title()}',
            message=f'Admin has {new_status} your treatment report for patient {report.patient.name}',
            notification_type='treatment_report',
            related_id=report.report_id
        )
        
        db.session.commit()
        flash(f'Report status updated to {new_status}', 'success')
        return redirect(url_for('admin_treatment_report_detail', report_id=report_id))
    
    flash('Invalid status', 'danger')
    return redirect(url_for('admin_treatment_report_detail', report_id=report_id))

@app.route('/admin/patient-claims')
@login_required_admin
@role_required('admin')
def admin_patient_claims():
    """Admin view all patient claims"""
    all_claims = PatientClaim.query.order_by(PatientClaim.created_at.desc()).all()
    return render_template('admin/patient_claims.html', claims=all_claims)

@app.route('/admin/patient-claim/<int:claim_id>')
@login_required_admin
@role_required('admin')
def admin_patient_claim_detail(claim_id):
    """Admin view patient claim details"""
    claim = PatientClaim.query.get_or_404(claim_id)
    return render_template('admin/patient_claim_detail.html', claim=claim)

@app.route('/admin/patient-claim/<int:claim_id>/process', methods=['POST'])
@login_required_admin
def admin_process_claim(claim_id):
    """Admin process claim (payment or order)"""
    claim = PatientClaim.query.get_or_404(claim_id)
    action = request.form.get('action')  # payment or order
    transaction_id = request.form.get('transaction_id', '').strip()
    order_id = request.form.get('order_id', '').strip()
    admin_notes = request.form.get('admin_notes', '').strip()
    
    if action == 'payment' and claim.claim_type == 'paisa_claim':
        claim.admin_action = 'payment'
        claim.transaction_id = transaction_id if transaction_id else None
        claim.status = 'payment_sent'
        
        # Notify patient
        notify_patient(
            patient_id=claim.patient_id,
            title='Payment Sent',
            message=f'Your paisa claim (financial help) has been processed. Transaction ID: {transaction_id if transaction_id else "Processing"}',
            notification_type='patient_claim',
            related_id=claim_id
        )
        
        flash('Payment processed successfully! Patient has been notified.', 'success')
    
    elif action == 'order' and claim.claim_type == 'samaan_claim':
        claim.admin_action = 'order'
        claim.order_id = order_id if order_id else None
        claim.status = 'order_placed'
        
        # Notify patient
        notify_patient(
            patient_id=claim.patient_id,
            title='Order Placed',
            message=f'Your samaan claim (food/essentials order) has been placed. Order ID: {order_id if order_id else "Processing"}',
            notification_type='patient_claim',
            related_id=claim_id
        )
        
        flash('Order placed successfully! Patient has been notified.', 'success')
    else:
        flash('Invalid action for this claim type.', 'danger')
    
    if admin_notes:
        claim.admin_notes = admin_notes
    
    claim.updated_at = datetime.utcnow()
    db.session.commit()
    
    return redirect(url_for('admin_patient_claim_detail', claim_id=claim_id))

# API Routes for Real-time Updates (already defined above, keeping for compatibility)

# Excel Export Routes
@app.route('/admin/export/patients')
@login_required_admin
def export_patients_excel():
    """Export all patients data to Excel"""
    patients = Patient.query.all()
    
    data = []
    for p in patients:
        data.append({
            'Patient ID': p.patient_id,
            'Name': p.name,
            'Phone': p.phone,
            'Address': p.address,
            'Aadhaar Number': p.aadhar_no,
            'Created Date': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else ''
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Patients', index=False)
    
    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename=patients_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return response

@app.route('/admin/export/requests')
@login_required_admin
def export_requests_excel():
    """Export all patient requests to Excel"""
    requests = PatientRequest.query.all()
    
    data = []
    for r in requests:
        data.append({
            'Request ID': r.request_id,
            'Patient Name': r.patient.name,
            'Patient Phone': r.patient.phone,
            'Disease': r.disease.name,
            'Hospital': r.hospital.name,
            'Status': r.status,
            'Problem Description': r.problem_description or '',
            'Symptoms': r.symptoms or '',
            'Created Date': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else ''
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Patient Requests', index=False)
    
    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename=patient_requests_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return response

@app.route('/admin/export/reports')
@login_required_admin
def export_reports_excel():
    """Export all treatment reports to Excel"""
    reports = TreatmentReport.query.all()
    
    data = []
    for r in reports:
        data.append({
            'Report ID': r.report_id,
            'Request ID': r.request_id,
            'Patient Name': r.patient.name,
            'Hospital': r.hospital.name,
            'Treatment Details': r.treatment_details or '',
            'Work Done': r.work_done or '',
            'Admission Date': r.admission_date.strftime('%Y-%m-%d') if r.admission_date else '',
            'Discharge Date': r.discharge_date.strftime('%Y-%m-%d') if r.discharge_date else '',
            'Total Expense (₹)': float(r.total_expense) if r.total_expense else 0,
            'Payment Amount (10%)': float(r.payment_amount) if r.payment_amount else 0,
            'Payment Status': r.payment_status or 'pending',
            'Case Type': r.case_type or '',
            'Report Status': r.status,
            'Created Date': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else ''
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Treatment Reports', index=False)
    
    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename=treatment_reports_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return response

@app.route('/admin/export/all')
@login_required_admin
def export_all_excel():
    """Export all data to Excel with multiple sheets"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Patients Sheet
        patients = Patient.query.all()
        patients_data = [{
            'Patient ID': p.patient_id,
            'Name': p.name,
            'Phone': p.phone,
            'Address': p.address,
            'Aadhaar Number': p.aadhar_no,
            'Created Date': p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else ''
        } for p in patients]
        pd.DataFrame(patients_data).to_excel(writer, sheet_name='Patients', index=False)
        
        # Requests Sheet
        requests = PatientRequest.query.all()
        requests_data = [{
            'Request ID': r.request_id,
            'Patient Name': r.patient.name,
            'Disease': r.disease.name,
            'Hospital': r.hospital.name,
            'Status': r.status,
            'Created Date': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else ''
        } for r in requests]
        pd.DataFrame(requests_data).to_excel(writer, sheet_name='Patient Requests', index=False)
        
        # Treatment Reports Sheet
        reports = TreatmentReport.query.all()
        reports_data = [{
            'Report ID': r.report_id,
            'Patient Name': r.patient.name,
            'Hospital': r.hospital.name,
            'Total Expense (₹)': float(r.total_expense) if r.total_expense else 0,
            'Payment Status': r.payment_status or 'pending',
            'Status': r.status,
            'Created Date': r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else ''
        } for r in reports]
        pd.DataFrame(reports_data).to_excel(writer, sheet_name='Treatment Reports', index=False)
        
        # Hospitals Sheet
        hospitals = Hospital.query.all()
        hospitals_data = [{
            'Hospital ID': h.hospital_id,
            'Name': h.name,
            'Address': h.address,
            'Speciality': h.speciality or '',
            'Contact': h.contact,
            'Email': h.email or '',
            'Created Date': h.created_at.strftime('%Y-%m-%d %H:%M:%S') if h.created_at else ''
        } for h in hospitals]
        pd.DataFrame(hospitals_data).to_excel(writer, sheet_name='Hospitals', index=False)
    
    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.headers['Content-Disposition'] = f'attachment; filename=complete_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    return response

# Serve uploaded files
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Database migration function to add missing columns
def migrate_database():
    """Add missing columns to existing database tables"""
    with app.app_context():
        try:
            inspector = db.inspect(db.engine)

            # ================= accident_cases =================
            if 'accident_cases' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('accident_cases')]

                with db.engine.connect() as conn:

                    def add_column(name, sql):
                        if name not in columns:
                            conn.execute(text(sql))
                            conn.commit()
                            print(f"✓ {name} column added")

                    add_column(
                        'case_type',
                        "ALTER TABLE accident_cases ADD COLUMN case_type VARCHAR(20)"
                    )

                    add_column(
                        'gender',
                        "ALTER TABLE accident_cases ADD COLUMN gender VARCHAR(10)"
                    )

                    add_column(
                        'patient_mobile',
                        "ALTER TABLE accident_cases ADD COLUMN patient_mobile VARCHAR(15)"
                    )

                    add_column(
                        'email',
                        "ALTER TABLE accident_cases ADD COLUMN email VARCHAR(120)"
                    )

                    add_column(
                        'date_of_birth',
                        "ALTER TABLE accident_cases ADD COLUMN date_of_birth DATE"
                    )

                    add_column(
                        'aadhar_no',
                        "ALTER TABLE accident_cases ADD COLUMN aadhar_no VARCHAR(20)"
                    )

                    add_column(
                        'patient_image_url',
                        "ALTER TABLE accident_cases ADD COLUMN patient_image_url VARCHAR(255)"
                    )

                    add_column(
                        'ayushman_card_url',
                        "ALTER TABLE accident_cases ADD COLUMN ayushman_card_url VARCHAR(255)"
                    )

                    add_column(
                        'accident_description',
                        "ALTER TABLE accident_cases ADD COLUMN accident_description TEXT"
                    )

                    add_column(
                        'accident_date',
                        "ALTER TABLE accident_cases ADD COLUMN accident_date DATE"
                    )

                    add_column(
                        'accident_location',
                        "ALTER TABLE accident_cases ADD COLUMN accident_location VARCHAR(255)"
                    )

                    add_column(
                        'current_condition',
                        "ALTER TABLE accident_cases ADD COLUMN current_condition TEXT"
                    )

                    add_column(
                        'patient_condition_image_url',
                        "ALTER TABLE accident_cases ADD COLUMN patient_condition_image_url VARCHAR(255)"
                    )

                    add_column(
                        'patient_serial_number',
                        "ALTER TABLE accident_cases ADD COLUMN patient_serial_number INTEGER"
                    )

                    add_column(
                        'admission_date',
                        "ALTER TABLE accident_cases ADD COLUMN admission_date DATE"
                    )

                    add_column(
                        'discharge_date',
                        "ALTER TABLE accident_cases ADD COLUMN discharge_date DATE"
                    )

            # ================= treatment_reports =================
            if 'treatment_reports' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('treatment_reports')]

                with db.engine.connect() as conn:

                    if 'hospital_bill_url' not in columns:
                        conn.execute(text(
                            "ALTER TABLE treatment_reports ADD COLUMN hospital_bill_url VARCHAR(255)"
                        ))
                        conn.commit()

                    if 'hospital_bill_amount' not in columns:
                        conn.execute(text(
                            "ALTER TABLE treatment_reports ADD COLUMN hospital_bill_amount NUMERIC(10,2)"
                        ))
                        conn.commit()

                    if 'test_bill_url' not in columns:
                        conn.execute(text(
                            "ALTER TABLE treatment_reports ADD COLUMN test_bill_url VARCHAR(255)"
                        ))
                        conn.commit()

                    if 'test_bill_amount' not in columns:
                        conn.execute(text(
                            "ALTER TABLE treatment_reports ADD COLUMN test_bill_amount NUMERIC(10,2)"
                        ))
                        conn.commit()

                    if 'medical_bill_url' not in columns:
                        conn.execute(text(
                            "ALTER TABLE treatment_reports ADD COLUMN medical_bill_url VARCHAR(255)"
                        ))
                        conn.commit()

                    if 'medical_bill_amount' not in columns:
                        conn.execute(text(
                            "ALTER TABLE treatment_reports ADD COLUMN medical_bill_amount NUMERIC(10,2)"
                        ))
                        conn.commit()

                    if 'net_amount' not in columns:
                        conn.execute(text(
                            "ALTER TABLE treatment_reports ADD COLUMN net_amount NUMERIC(10,2)"
                        ))
                        conn.commit()

            # ================= patient_requests =================
            if 'patient_requests' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('patient_requests')]

                with db.engine.connect() as conn:

                    if 'disease_duration' not in columns:
                        conn.execute(text(
                            "ALTER TABLE patient_requests ADD COLUMN disease_duration VARCHAR(100)"
                        ))
                        conn.commit()

                    if 'current_condition' not in columns:
                        conn.execute(text(
                            "ALTER TABLE patient_requests ADD COLUMN current_condition TEXT"
                        ))
                        conn.commit()

            # ================= patients =================
            if 'patients' in inspector.get_table_names():
                columns = [col['name'] for col in inspector.get_columns('patients')]

                with db.engine.connect() as conn:

                    if 'email_verified' not in columns:
                        conn.execute(text(
                            "ALTER TABLE patients ADD COLUMN email_verified BOOLEAN DEFAULT 0"
                        ))
                        conn.commit()

                    if 'security_image' not in columns:
                        conn.execute(text(
                            "ALTER TABLE patients ADD COLUMN security_image VARCHAR(50)"
                        ))
                        conn.commit()
                    conn.execute(text(
                        "UPDATE patients SET security_image = 'heart' WHERE security_image IS NULL OR security_image = ''"
                    ))
                    conn.commit()

        except Exception as e:
            print(f"Migration error: {e}")

           

            # Don't raise, just log - allow app to continue

# Initialize database and seed data
def init_db():
    with app.app_context():
        # Run migration first to add missing columns
        migrate_database()
        
        # Create all tables (for new installations)
        db.create_all()
        
        # Create default admin
        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(
                username='admin',
                password_hash=generate_password_hash('admin123')
            )
            db.session.add(admin)
        
        # Seed sample diseases
        if Disease.query.count() == 0:
            diseases = [
                Disease(name='Dengue', symptoms='High fever, Severe headache, Pain behind eyes, Joint and muscle pain', 
                       treatment='Rest, Hydration, Pain relievers', speciality='Physician'),
                Disease(name='Cancer', symptoms='Unexplained weight loss, Fatigue, Persistent pain', 
                       treatment='Chemotherapy, Radiation, Surgery', speciality='Oncology'),
                Disease(name='Heart Problem', symptoms='Chest pain, Shortness of breath, Irregular heartbeat', 
                       treatment='Medication, Surgery, Lifestyle changes', speciality='Cardiology'),
                Disease(name='Diabetes', symptoms='Increased thirst, Frequent urination, Fatigue', 
                       treatment='Insulin, Medication, Diet control', speciality='Endocrinology'),
                Disease(name='Dental Issue', symptoms='Tooth pain, Swelling, Sensitivity', 
                       treatment='Cleaning, Filling, Root canal', speciality='Dentistry'),
            ]
            db.session.add_all(diseases)
        
        # Seed sample hospitals
        if Hospital.query.count() == 0:
            hospitals = [
                Hospital(name='Apollo Hospital', address='Delhi, India', speciality='Oncology, Cardiology', 
                        contact='011-12345678', email='apollo@hospital.com', 
                        password_hash=generate_password_hash('hospital123')),
                Hospital(name='Fortis Hospital', address='Mumbai, India', speciality='Cardiology, Neurology', 
                        contact='022-87654321', email='fortis@hospital.com',
                        password_hash=generate_password_hash('hospital123')),
                Hospital(name='Max Hospital', address='Delhi, India', speciality='Physician, Endocrinology', 
                        contact='011-11223344', email='max@hospital.com',
                        password_hash=generate_password_hash('hospital123')),
                Hospital(name='Dental Care Clinic', address='Bangalore, India', speciality='Dentistry', 
                        contact='080-99887766', email='dental@hospital.com',
                        password_hash=generate_password_hash('hospital123')),
            ]
            db.session.add_all(hospitals)
        
        db.session.commit()

# Prevent browser caching for templates (to see updates immediately)
@app.after_request
def add_cache_control(response):
    # Disable caching for HTML pages
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

if __name__ == '__main__':
    print("\n" + "="*50)
    print("  SMART MEDICAL SYSTEM - Starting Server...")
    print("="*50)
    print("\nInitializing database...")
    init_db()
    print("Database initialized successfully!")
    print("\nServer starting at: http://localhost:5000")
    print("Press Ctrl+C to stop the server\n")
    print("="*50 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5000)


