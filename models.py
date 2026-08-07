from extensions import db
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')

def get_ist_now():
    return datetime.now(IST)

class Patient(db.Model):
    __tablename__ = 'patients'
    patient_id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    # Login / account fields
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(255))
    security_image = db.Column(db.String(50))

    gender = db.Column(db.String(10))
    phone = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(100))
    email_verified = db.Column(db.Boolean, default=False)  # ✅ ADD
    dob = db.Column(db.Date)
    address = db.Column(db.Text, nullable=False)

    aadhar_no = db.Column(db.String(12), unique=True, nullable=False)
    aadhar_document_url = db.Column(db.String(255))

    has_ayushman = db.Column(db.String(5))
    ayushman_document_url = db.Column(db.String(255))

    created_at = db.Column(db.DateTime, default=get_ist_now)



    

class Disease(db.Model):
    __tablename__ = 'diseases'
    disease_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    symptoms = db.Column(db.Text)
    treatment = db.Column(db.Text)
    speciality = db.Column(db.String(100))
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=True)  # Which hospital added it
    admin_approved = db.Column(db.Boolean, default=False)  # Admin approval status
    admin_approved_by = db.Column(db.Integer, db.ForeignKey('admins.admin_id'), nullable=True)
    admin_approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=get_ist_now)
    
    # Relationships
    hospital = db.relationship('Hospital', backref='diseases')

class Hospital(db.Model):
    __tablename__ = 'hospitals'

    id = db.Column(db.Integer, primary_key=True)   # ✅ CHANGE
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text, nullable=False)
    speciality = db.Column(db.String(200))
    contact = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(100))
    password_hash = db.Column(db.String(255))

    admin_approved = db.Column(db.Boolean, default=False)
    admin_approved_by = db.Column(db.Integer, db.ForeignKey('admins.admin_id'))
    admin_approved_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.Text, nullable=True)  # Reason if rejected
    rejected_at = db.Column(db.DateTime, nullable=True)  # When rejected
    rejected_by = db.Column(db.Integer, db.ForeignKey('admins.admin_id'), nullable=True)  # Who rejected

    created_at = db.Column(db.DateTime, default=get_ist_now)
    
    @property
    def hospital_id(self):
        """Property to return id as hospital_id for compatibility"""
        return self.id



class PatientRequest(db.Model):
    __tablename__ = 'patient_requests'

    request_id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False)
    disease_id = db.Column(db.Integer, db.ForeignKey('diseases.disease_id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)

    status = db.Column(db.String(50), default='pending')

    problem_description = db.Column(db.Text)
    symptoms = db.Column(db.Text)

    # ✅ ADD THESE TWO LINES
    disease_duration = db.Column(db.String(100))   # जैसे: 3 महीने, 1 साल
    current_condition = db.Column(db.Text)         # जैसे: हालत गंभीर, स्थिर

    report_document_url = db.Column(db.String(255))
    patient_serial_number = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=get_ist_now)



    
    # Relationships
    patient = db.relationship('Patient', backref='requests')
    disease = db.relationship('Disease', backref='requests')
    hospital = db.relationship('Hospital', backref='requests')


class TreatmentReport(db.Model):
    __tablename__ = 'treatment_reports'
    report_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('patient_requests.request_id'), nullable=True)  # Can be NULL for accident cases
    accident_id = db.Column(db.Integer, db.ForeignKey('accident_cases.accident_id'), nullable=True)  # Can be NULL for normal requests
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False)
    
    # Case Type (Normal / Accident)
    case_source = db.Column(db.String(50), nullable=False)  # 'normal' or 'accident'
    
    # Treatment Details
    patient_serial_number = db.Column(db.String(50))  # Serial number given by hospital
    patient_name = db.Column(db.String(100), nullable=False)
    disease_injury = db.Column(db.String(200), nullable=False)  # Disease name or injury description
    treatment_details = db.Column(db.Text, nullable=False)
    work_done = db.Column(db.Text)  # Tests, medicines, procedures
    admission_date = db.Column(db.Date)
    discharge_date = db.Column(db.Date)
    final_treatment_report = db.Column(db.Text)
    medical_report_url = db.Column(db.String(255))  # Medical report upload
    
    # Financial Details
    total_expense = db.Column(db.Numeric(10, 2))
    bill_document_url = db.Column(db.String(255))  # For Government case - single bill
    case_type = db.Column(db.String(50))  # Private or Government
    
    # Private Case - Separate Bills
    hospital_bill_url = db.Column(db.String(255))  # Private case - Hospital bill
    hospital_bill_amount = db.Column(db.Numeric(10, 2))  # Private case - Hospital bill amount
    test_bill_url = db.Column(db.String(255))  # Private case - Test bill
    test_bill_amount = db.Column(db.Numeric(10, 2))  # Private case - Test bill amount
    medical_bill_url = db.Column(db.String(255))  # Private case - Medical bill
    medical_bill_amount = db.Column(db.Numeric(10, 2))  # Private case - Medical bill amount
    net_amount = db.Column(db.Numeric(10, 2))  # Private case - Net amount after deducting medical bill
    
    # Payment Details
    payment_amount = db.Column(db.Numeric(10, 2))  # 10% amount
    payment_screenshot_url = db.Column(db.String(255))
    payment_method = db.Column(db.String(50))  # 'upi' or 'qr_code'
    upi_id = db.Column(db.String(100))
    payment_status = db.Column(db.String(50), default='pending')  # pending, paid, verified
    
    # Status
    status = db.Column(db.String(50), default='submitted')  # submitted, approved, rejected, closed
    admin_notes = db.Column(db.Text)
    
    created_at = db.Column(
        db.DateTime,
        default=get_ist_now
    )
    updated_at = db.Column(
        db.DateTime,
        default=get_ist_now,
        onupdate=get_ist_now
    )

    # Relationships
    request = db.relationship('PatientRequest', backref='treatment_reports')
    accident_case = db.relationship('AccidentCase', backref='treatment_reports')
    hospital = db.relationship('Hospital', backref='treatment_reports')
    patient = db.relationship('Patient', backref='treatment_reports')

class AccidentCase(db.Model):
    __tablename__ = 'accident_cases'
    accident_id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False)
    hospital_id = db.Column(
        db.Integer,
        db.ForeignKey('hospitals.id'),  # ✅ FIX HERE
        nullable=False
    )

    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected, treatment_complete, discharged
    
    # Patient Details
    case_type = db.Column(db.String(20))  # accident / emergency
    patient_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10))
    patient_mobile = db.Column(db.String(15)) 
    email = db.Column(db.String(100))# Patient mobile number
    date_of_birth = db.Column(db.Date)
    aadhar_no = db.Column(db.String(12), nullable=False)
    patient_image_url = db.Column(db.String(255))  # Jan Aadhaar image
    ayushman_card_url = db.Column(db.String(255))  # Ayushman card image (optional)
    
    # Accident Details
    accident_description = db.Column(db.Text, nullable=False)  # How it happened
    accident_date = db.Column(db.Date)
    accident_location = db.Column(db.String(200))
    current_condition = db.Column(db.Text, nullable=False)  # Bone fracture, bleeding, etc.
    patient_condition_image_url = db.Column(db.String(255))  # Patient condition/injury photo
    
    # Hospital Details
    patient_serial_number = db.Column(db.String(50))  # Given by hospital
    admission_date = db.Column(db.Date)
    discharge_date = db.Column(db.Date)
    
    created_at = db.Column(
        db.DateTime,
        default=get_ist_now
    )
    updated_at = db.Column(
        db.DateTime,
        default=get_ist_now,
        onupdate=get_ist_now
    )

    # Relationships
    patient = db.relationship('Patient', backref='accident_cases')
    hospital = db.relationship('Hospital', backref='accident_cases')

class PatientClaim(db.Model):
    __tablename__ = 'patient_claims'
    claim_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('patient_requests.request_id'), nullable=True)  # For normal requests
    accident_id = db.Column(db.Integer, db.ForeignKey('accident_cases.accident_id'), nullable=True)  # For accident cases
    treatment_report_id = db.Column(db.Integer, db.ForeignKey('treatment_reports.report_id'), nullable=False)  # Link to treatment report
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.patient_id'), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)
    
    # Case Source (Normal / Accident)
    case_source = db.Column(db.String(50), nullable=False)  # 'normal' or 'accident'
    
    # Patient Confirmation Details
    patient_serial_number = db.Column(db.String(50), nullable=False)
    patient_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    disease_injury = db.Column(db.String(200), nullable=False)
    medical_report_url = db.Column(db.String(255))
    treatment_from_date = db.Column(db.Date, nullable=False)
    treatment_to_date = db.Column(db.Date, nullable=False)
    current_condition = db.Column(db.Text)
    
    # Claim Type (ONLY ONE at a time)
    claim_type = db.Column(db.String(50), nullable=False)  # 'paisa_claim' or 'samaan_claim'
    
    # Financial Help Details (if claim_type = paisa_claim) - ONLY ONE payment method
    payment_method = db.Column(db.String(50))  # 'bank', 'upi', or 'qr_code'
    
    # Bank Details (if payment_method = 'bank')
    bank_name = db.Column(db.String(200))
    account_holder_name = db.Column(db.String(100))
    account_number = db.Column(db.String(50))
    ifsc_code = db.Column(db.String(20))
    
    # UPI Details (if payment_method = 'upi')
    upi_id = db.Column(db.String(100))
    upi_name = db.Column(db.String(100))
    
    # QR Code (if payment_method = 'qr_code')
    qr_code_url = db.Column(db.String(255))
    
    # Food/Essentials Details (if claim_type = samaan_claim)
    receiver_name = db.Column(db.String(100))
    receiver_mobile = db.Column(db.String(15))
    delivery_address = db.Column(db.Text)
    pincode = db.Column(db.String(10))
    
    # Admin Action
    status = db.Column(db.String(50), default='pending')  # pending, payment_sent, order_placed, completed
    admin_action = db.Column(db.String(50))  # payment or order
    transaction_id = db.Column(db.String(100))
    order_id = db.Column(db.String(100))
    admin_notes = db.Column(db.Text)
    
    created_at = db.Column(
        db.DateTime,
        default=get_ist_now
    )
    updated_at = db.Column(
        db.DateTime,
        default=get_ist_now,
        onupdate=get_ist_now
    )

    # Relationships
    request = db.relationship('PatientRequest', backref='claims')
    accident_case = db.relationship('AccidentCase', backref='claims')
    treatment_report = db.relationship('TreatmentReport', backref='claims')
    patient = db.relationship('Patient', backref='claims')
    hospital = db.relationship('Hospital', backref='claims')

class Notification(db.Model):
    __tablename__ = 'notifications'
    notification_id = db.Column(db.Integer, primary_key=True)
    user_type = db.Column(db.String(50), nullable=False)  # admin, hospital, patient
    user_id = db.Column(db.Integer, nullable=False)  # admin_id, hospital_id, or patient_id
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))  # patient_request, admin_message, treatment_report, payment, request_accepted, request_rejected, accident_case, patient_claim
    related_id = db.Column(db.Integer)  # request_id, report_id, accident_id, claim_id, etc.
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=get_ist_now)

class Doctor(db.Model):
    __tablename__ = 'doctors'
    doctor_id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    qualification = db.Column(db.String(200))  # MBBS, MD, etc.
    specialization = db.Column(db.Text)  # Which diseases they treat
    image_url = db.Column(db.String(255))  # Passport size photo
    created_at = db.Column(db.DateTime, default=get_ist_now)
    
    # Relationships
    hospital = db.relationship('Hospital', backref='doctors')

class Admin(db.Model):
    __tablename__ = 'admins'
    admin_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

class HospitalDisease(db.Model):
    __tablename__ = 'hospital_diseases'
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospitals.id'), nullable=False)
    disease_name = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=get_ist_now)
    hospital = db.relationship('Hospital', backref='hospital_diseases')
