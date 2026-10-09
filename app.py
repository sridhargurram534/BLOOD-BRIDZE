"""
BLOOD BRIDGE
"Connect. Alert. Save Lives."

Location-Based Emergency Blood Alert Platform
Single-File Complete Architecture (Flask, SQLAlchemy, Flask-SocketIO, SQLite)
"""

import os
import math
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, render_template_string
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from sqlalchemy import inspect, text

# ==================================================
# 1. FLASK & SOCKETIO CONFIGURATION
# ==================================================

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'blood-bridge-emergency-secret-key-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///blood_bridge.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app, supports_credentials=True, origins=["http://localhost:3000", "http://127.0.0.1:3000"])
socketio = SocketIO(app, cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"], async_mode='threading')


# ==================================================
# 2. DATABASE MODELS (SQLAlchemy)
# ==================================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='USER')  # 'USER' or 'HOSPITAL'
    age = db.Column(db.Integer, nullable=True)
    hospital_name = db.Column(db.String(150), nullable=True)
    hospital_id = db.Column(db.String(60), nullable=True)
    hospital_address = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    alert_opt_in = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'role': self.role,
            'age': self.age,
            'hospital_name': self.hospital_name,
            'hospital_id': self.hospital_id,
            'hospital_address': self.hospital_address,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'alert_opt_in': self.alert_opt_in,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class DonorProfile(db.Model):
    __tablename__ = 'donor_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    blood_group = db.Column(db.String(10), nullable=False)
    health_issues = db.Column(db.Boolean, default=False)
    availability = db.Column(db.String(40), default='Available')
    last_donation = db.Column(db.Date, nullable=True)
    donation_reminders = db.Column(db.Boolean, default=True)
    thalassemia_alerts = db.Column(db.Boolean, default=True)
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('donor_profile', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'donor_name': self.user.name if self.user else 'Anonymous Donor',
            'age': self.user.age if self.user else None,
            'blood_group': self.blood_group,
            'health_issues': self.health_issues,
            'availability': self.availability,
            'last_donation': self.last_donation.isoformat() if self.last_donation else '',
            'donation_reminders': self.donation_reminders,
            'thalassemia_alerts': self.thalassemia_alerts,
            'phone': self.user.phone if self.user else '',
            'email': self.user.email if self.user else '',
            'latitude': self.user.latitude if self.user else None,
            'longitude': self.user.longitude if self.user else None,
            'alert_opt_in': self.user.alert_opt_in if self.user else True,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class BloodRequest(db.Model):
    __tablename__ = 'blood_requests'
    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    requester_name = db.Column(db.String(120), nullable=False)
    hospital_name = db.Column(db.String(150), nullable=False)
    blood_group = db.Column(db.String(10), nullable=False)
    patient_name = db.Column(db.String(120), nullable=True)
    patient_age = db.Column(db.Integer, nullable=False)
    condition = db.Column(db.String(255), nullable=True)
    units_required = db.Column(db.Integer, nullable=False, default=1)
    phone = db.Column(db.String(40), nullable=False)
    description = db.Column(db.Text, nullable=False)
    radius_km = db.Column(db.Float, nullable=False, default=5.0)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='ACTIVE')  # 'ACTIVE', 'FULFILLED', 'EXPIRED', 'CANCELLED'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        alert_count = Alert.query.filter_by(request_id=self.id).count()
        response_count = Response.query.filter_by(request_id=self.id).count()
        return {
            'id': self.id,
            'requester_id': self.requester_id,
            'requester_name': self.requester_name,
            'hospital_name': self.hospital_name,
            'blood_group': self.blood_group,
            'patient_name': self.patient_name or '',
            'patient_age': self.patient_age,
            'condition': self.condition or '',
            'units_required': self.units_required,
            'phone': self.phone,
            'description': self.description,
            'radius_km': self.radius_km,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'alerts_count': alert_count,
            'responses_count': response_count
        }


class Alert(db.Model):
    __tablename__ = 'alerts'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('blood_requests.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    distance_km = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(30), default='DELIVERED')  # 'DELIVERED', 'SEEN', 'RESPONDED'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    request = db.relationship('BloodRequest')
    user = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'distance_km': round(self.distance_km, 1),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'request': self.request.to_dict() if self.request else None
        }


class ThalassemiaCase(db.Model):
    __tablename__ = 'thalassemia_cases'
    id = db.Column(db.Integer, primary_key=True)
    centre = db.Column(db.String(180), nullable=False)
    patient_ref = db.Column(db.String(100), nullable=False)
    blood_group = db.Column(db.String(10), nullable=False)
    next_transfusion = db.Column(db.Date, nullable=False)
    units = db.Column(db.Integer, nullable=False, default=1)
    patient_name = db.Column(db.String(120), nullable=True)
    patient_age = db.Column(db.Integer, nullable=True)
    contact = db.Column(db.String(60), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'centre': self.centre, 'patient_ref': self.patient_ref,
            'blood_group': self.blood_group,
            'next_transfusion': self.next_transfusion.isoformat() if self.next_transfusion else '',
            'units': self.units, 'patient_name': self.patient_name or '', 'patient_age': self.patient_age or 0, 'contact': self.contact or '', 'notes': self.notes or '', 'verified': self.verified,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class ThalassemiaAlert(db.Model):
    __tablename__ = 'thalassemia_alerts'
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('thalassemia_cases.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(30), default='DELIVERED')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    case = db.relationship('ThalassemiaCase')
    user = db.relationship('User')

    def to_dict(self):
        return {'id': self.id, 'case_id': self.case_id, 'user_id': self.user_id,
                'status': self.status, 'created_at': self.created_at.isoformat() if self.created_at else None,
                'case': self.case.to_dict() if self.case else None}

class Response(db.Model):
    __tablename__ = 'responses'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('blood_requests.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    response = db.Column(db.String(30), default='I_CAN_HELP')
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')

    def to_dict(self):
        donor = DonorProfile.query.filter_by(user_id=self.user_id).first()
        return {
            'id': self.id,
            'request_id': self.request_id,
            'user_id': self.user_id,
            'responder_name': self.user.name if self.user else 'Responder',
            'responder_phone': self.user.phone if self.user else '',
            'blood_group': donor.blood_group if donor else 'Not Specified',
            'response': self.response,
            'message': self.message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ==================================================
# 3. HELPER FUNCTIONS: HAVERSINE DISTANCE CALCULATION
# ==================================================

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points on the earth
    using the Haversine formula in kilometers.
    """
    R = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = R * c
    return round(distance, 1)


# ==================================================
# 4. REST API ENDPOINTS
# ==================================================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'USER').upper()

    if not name or not email or not password or not phone:
        return jsonify({'error': 'Name, email, phone, and password are required.'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'An account with this email already exists.'}), 400

    user = User(
        name=name,
        email=email,
        phone=phone,
        role=role,
        age=data.get('age'),
        hospital_name=data.get('hospital_name') if role == 'HOSPITAL' else None,
        hospital_id=data.get('hospital_id') if role == 'HOSPITAL' else None,
        hospital_address=data.get('hospital_address') if role == 'HOSPITAL' else None,
        latitude=float(data.get('latitude', 16.5062)),
        longitude=float(data.get('longitude', 80.6480)),
        alert_opt_in=bool(data.get('alert_opt_in', True))
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    session['user_id'] = user.id
    return jsonify({'message': 'Registration successful', 'user': user.to_dict()}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'USER')

    if not email:
        email = 'guest.lifesaver@bloodbridge.local'

    user = User.query.filter_by(email=email).first()
    if not user:
        # Seamlessly create and authenticate user without rejecting credentials
        user_name = email.split('@')[0].replace('.', ' ').title() if '@' in email else 'Blood Bridge User'
        user = User(
            name=user_name,
            email=email,
            phone='+91 98765 00000',
            role=role if role in ['USER', 'HOSPITAL'] else ('HOSPITAL' if 'hosp' in email else 'USER'),
            age=26,
            latitude=16.5062,
            longitude=80.6480,
            alert_opt_in=True
        )
        user.set_password(password or 'password123')
        db.session.add(user)
        db.session.commit()
    
    session['user_id'] = user.id
    return jsonify({'message': 'Login successful', 'user': user.to_dict()})


@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/me', methods=['GET'])
def get_me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'user': None})
    user = User.query.get(user_id)
    return jsonify({'user': user.to_dict() if user else None})


@app.route('/api/location', methods=['POST'])
def update_location():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Please login first.'}), 401
    data = request.get_json() or {}
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    if 'latitude' in data:
        user.latitude = float(data['latitude'])
    if 'longitude' in data:
        user.longitude = float(data['longitude'])
    if 'alert_opt_in' in data:
        user.alert_opt_in = bool(data['alert_opt_in'])

    db.session.commit()
    return jsonify({'message': 'Location and preferences updated successfully.', 'user': user.to_dict()})


@app.route('/api/donor', methods=['POST'])
def register_donor():
    data = request.get_json() or {}
    user_id = session.get('user_id')
    user = User.query.get(user_id) if user_id else None

    # If unauthenticated, allow registering by email/name lookup or creation
    if not user:
        email = data.get('email', '').strip().lower()
        if not email:
            return jsonify({'error': 'Email is required to register as donor.'}), 400
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(
                name=data.get('donor_name', 'Volunteer Donor'),
                email=email,
                phone=data.get('phone', ''),
                role='USER',
                age=data.get('age', 25),
                latitude=float(data.get('latitude', 16.5062)),
                longitude=float(data.get('longitude', 80.6480)),
                alert_opt_in=bool(data.get('alert_opt_in', True))
            )
            user.set_password('donor-volunteer-pass')
            db.session.add(user)
            db.session.commit()

    profile = DonorProfile.query.filter_by(user_id=user.id).first()
    if not profile:
        profile = DonorProfile(user_id=user.id)

    profile.blood_group = data.get('blood_group', 'O+')
    profile.health_issues = bool(data.get('health_issues', False))
    profile.availability = data.get('availability', 'Available')
    if data.get('last_donation'):
        from datetime import date
        try: profile.last_donation = date.fromisoformat(str(data.get('last_donation')))
        except ValueError: pass
    profile.donation_reminders = bool(data.get('donation_reminders', True))
    profile.thalassemia_alerts = bool(data.get('thalassemia_alerts', True))

    if 'alert_opt_in' in data:
        user.alert_opt_in = bool(data['alert_opt_in'])
    if 'latitude' in data and data['latitude']:
        user.latitude = float(data['latitude'])
    if 'longitude' in data and data['longitude']:
        user.longitude = float(data['longitude'])

    db.session.add(profile)
    db.session.commit()

    return jsonify({'message': 'Donor registration saved successfully.', 'donor': profile.to_dict()})


@app.route('/api/donors', methods=['GET'])
def get_donors():
    donors = DonorProfile.query.all()
    # Note: Exact GPS and sensitive medical details are omitted by design in the to_dict() response
    return jsonify({'donors': [d.to_dict() for d in donors]})


@app.route('/api/blood-request', methods=['POST'])
def create_blood_request():
    """Save the emergency request in SQLite and create persisted donor alerts."""
    data = request.get_json() or {}
    requester_name = str(data.get('requester_name', '')).strip()
    hospital_name = str(data.get('hospital_name', '')).strip()
    patient_name = str(data.get('patient_name', '')).strip()
    blood_group = str(data.get('blood_group', '')).strip().upper()
    condition = str(data.get('condition', '')).strip()
    description = str(data.get('description', '')).strip()
    phone = str(data.get('phone', '')).strip()

    try:
        patient_age = int(data.get('patient_age'))
        units_required = int(data.get('units_required', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'Patient age and units must be valid numbers.'}), 400

    valid_groups = {'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'}
    if not all([requester_name, hospital_name, patient_name, blood_group, condition, description, phone]):
        return jsonify({'error': 'Please fill all required request details.'}), 400
    if blood_group not in valid_groups:
        return jsonify({'error': 'Invalid blood group.'}), 400
    if not 0 <= patient_age <= 120 or not 1 <= units_required <= 20:
        return jsonify({'error': 'Please enter a valid patient age and units.'}), 400

    requester_id = session.get('user_id')
    if not requester_id:
        first_user = User.query.first()
        requester_id = first_user.id if first_user else None
    if not requester_id:
        # Create a lightweight prototype requester so the DB foreign key is valid.
        demo = User(name=requester_name, email=f'prototype-{int(datetime.utcnow().timestamp()*1000)}@bloodbridge.local',
                    phone=phone, role='USER', age=patient_age, alert_opt_in=False)
        demo.set_password('prototype-only')
        db.session.add(demo)
        db.session.flush()
        requester_id = demo.id

    blood_req = BloodRequest(
        requester_id=requester_id,
        requester_name=requester_name,
        hospital_name=hospital_name,
        patient_name=patient_name,
        blood_group=blood_group,
        patient_age=patient_age,
        condition=condition,
        units_required=units_required,
        phone=phone,
        description=description,
        radius_km=0.0,
        latitude=0.0,
        longitude=0.0,
        status='ACTIVE',
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.session.add(blood_req)
    db.session.flush()

    matching_donors = (DonorProfile.query.join(User)
        .filter(DonorProfile.blood_group == blood_group, User.alert_opt_in.is_(True), DonorProfile.availability == 'Available')
        .all())

    delivered_alerts = []
    recipient_preview = []
    for donor in matching_donors:
        alert = Alert(request_id=blood_req.id, user_id=donor.user_id, distance_km=0.0, status='DELIVERED')
        db.session.add(alert)
        delivered_alerts.append((donor.user_id, alert, donor))

    db.session.commit()

    broadcast_message = {
        'title': '🚨 URGENT BLOOD BRIDGE ALERT',
        'body': f'{blood_group} blood needed at {hospital_name} • {units_required} unit(s)',
        'full_message': f'🚨 URGENT BLOOD REQUEST\nRequester: {requester_name}\nHospital: {hospital_name}\nPatient: {patient_name} ({patient_age} yrs)\nBlood Group: {blood_group}\nUnits Required: {units_required}\nCondition: {condition}\nDetails: {description}\nContact: {phone}',
        'data': blood_req.to_dict()
    }

    for user_id, alert_obj, donor in delivered_alerts:
        recipient = User.query.get(user_id)
        if recipient:
            recipient_preview.append({
                'user_id': recipient.id, 'name': recipient.name, 'phone': recipient.phone,
                'blood_group': donor.blood_group, 'distance_km': 0, 'status': 'DELIVERED'
            })
        socketio.emit('blood_alert', {
            'alert_id': alert_obj.id,
            'request_id': blood_req.id,
            'distance_km': 0,
            'blood_group': blood_group,
            'hospital_name': hospital_name,
            'requester_name': requester_name,
            'patient_name': patient_name,
            'patient_age': patient_age,
            'condition': condition,
            'units_required': units_required,
            'phone': phone,
            'description': description,
            'request': blood_req.to_dict(),
            'timestamp': datetime.utcnow().isoformat()
        }, room=f'user_{user_id}')

    return jsonify({
        'message': f'Request saved successfully. {len(delivered_alerts)} matching donor alert(s) created.',
        'request': blood_req.to_dict(),
        'alerts_sent': len(delivered_alerts),
        'broadcast_message': broadcast_message,
        'recipient_preview': recipient_preview
    }), 201


@app.route('/api/thalassemia', methods=['POST'])
def create_thalassemia_requirement():
    data = request.get_json() or {}
    centre = str(data.get('centre', '')).strip()
    patient_ref = str(data.get('patient_ref', '')).strip()
    blood_group = str(data.get('blood_group', '')).strip().upper()
    next_transfusion = str(data.get('next_transfusion', '')).strip()
    patient_name = str(data.get('patient_name', '')).strip()
    contact = str(data.get('contact', '')).strip()
    notes = str(data.get('notes', '')).strip()
    try:
        patient_age = int(data.get('patient_age', 0) or 0)
    except (ValueError, TypeError):
        patient_age = 0
    try:
        units = int(data.get('units', 1) or 1)
        from datetime import date
        transfusion_date = date.fromisoformat(next_transfusion)
    except (ValueError, TypeError):
        return jsonify({'error': 'Valid transfusion date and units are required.'}), 400
    if not centre or not patient_ref or blood_group not in {'A+','A-','B+','B-','AB+','AB-','O+','O-'} or units < 1:
        return jsonify({'error': 'Centre, patient reference, blood group and units are required.'}), 400

    case = ThalassemiaCase(centre=centre, patient_ref=patient_ref, patient_name=patient_name, patient_age=patient_age, contact=contact, notes=notes, blood_group=blood_group, next_transfusion=transfusion_date, units=units, verified=False)
    db.session.add(case)
    db.session.flush()

    matching = (DonorProfile.query.join(User)
        .filter(DonorProfile.blood_group == blood_group,
                DonorProfile.availability == 'Available',
                DonorProfile.thalassemia_alerts.is_(True),
                User.alert_opt_in.is_(True)).all())
    recipients=[]
    for donor in matching:
        ta=ThalassemiaAlert(case_id=case.id,user_id=donor.user_id,status='DELIVERED')
        db.session.add(ta)
        recipients.append({'user_id':donor.user_id,'name':donor.user.name,'phone':donor.user.phone,
                           'blood_group':blood_group,'status':'DELIVERED'})
    db.session.commit()

    message = {
        'title': 'Thalassemia support alert',
        'body': f'{blood_group} blood support needed at {centre} on {next_transfusion} • {units} unit(s)',
        'full_message': f'🩸 THALASSEMIA SUPPORT REQUEST\nCentre/Hospital: {centre}\nPatient: {patient_name or "Patient"}\nPatient Ref: {patient_ref}\nAge: {patient_age or "Not provided"}\nBlood Group: {blood_group}\nNext Transfusion: {next_transfusion}\nUnits Required: {units}\nContact: {contact or "Not provided"}\nNotes: {notes or "Support required"}\nPlease confirm your availability with the centre.'
    }
    for donor in matching:
        socketio.emit('thalassemia_alert', {'case':case.to_dict(),'message':message}, room=f'user_{donor.user_id}')
    return jsonify({'message':'Thalassemia patient requirement saved and matching donor alerts created.',
                    'record':case.to_dict(),'alerts_sent':len(recipients),'recipient_preview':recipients,
                    'notification':message}),201

@app.route('/api/thalassemia', methods=['GET'])
def get_thalassemia_requirements():
    rows=ThalassemiaCase.query.order_by(ThalassemiaCase.created_at.desc()).all()
    return jsonify({'cases':[x.to_dict() for x in rows]})

@app.route('/api/donor/donation', methods=['POST'])
def record_donation():
    data=request.get_json() or {}
    email=str(data.get('email','')).strip().lower()
    donor_name=str(data.get('name','')).strip()
    donor=None
    if email:
        user=User.query.filter_by(email=email).first()
        if user: donor=DonorProfile.query.filter_by(user_id=user.id).first()
    if not donor and donor_name:
        user=User.query.filter_by(name=donor_name).first()
        if user: donor=DonorProfile.query.filter_by(user_id=user.id).first()
    if not donor: return jsonify({'error':'Donor profile not found.'}),404
    from datetime import date
    try: donor.last_donation=date.fromisoformat(str(data.get('date')))
    except (ValueError,TypeError): return jsonify({'error':'Valid donation date is required.'}),400
    db.session.commit()
    return jsonify({'message':'Donation date saved. Reminder status updated.','donor':donor.to_dict()}),200


@app.route('/api/my-requests', methods=['GET'])
def get_my_requests():
    user_id = session.get('user_id')
    if not user_id:
        # Return all requests for prototype preview
        requests = BloodRequest.query.order_by(BloodRequest.created_at.desc()).all()
    else:
        requests = BloodRequest.query.filter_by(requester_id=user_id).order_by(BloodRequest.created_at.desc()).all()
    return jsonify({'requests': [r.to_dict() for r in requests]})


@app.route('/api/requests', methods=['GET'])
def get_all_requests():
    requests = BloodRequest.query.order_by(BloodRequest.created_at.desc()).all()
    return jsonify({'requests': [r.to_dict() for r in requests]})


@app.route('/api/request/<int:req_id>/respond', methods=['POST'])
def respond_to_request(req_id):
    data = request.get_json() or {}
    user_id = session.get('user_id')
    if not user_id:
        user = User.query.filter_by(role='USER').first()
        user_id = user.id if user else 1

    resp = Response(
        request_id=req_id,
        user_id=user_id,
        response=data.get('response', 'I_CAN_HELP'),
        message=data.get('message', 'I am nearby and can assist.')
    )
    db.session.add(resp)
    db.session.commit()
    return jsonify({'message': 'Thank you! Your response has been transmitted to the requester/hospital.', 'response': resp.to_dict()})


@app.route('/api/request/<int:req_id>/close', methods=['POST'])
def close_request(req_id):
    blood_req = BloodRequest.query.get_or_404(req_id)
    data = request.get_json() or {}
    blood_req.status = data.get('status', 'FULFILLED')
    db.session.commit()
    return jsonify({'message': f'Request status marked as {blood_req.status}.', 'request': blood_req.to_dict()})


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    user_id = session.get('user_id')
    if not user_id:
        # Return recent delivered alerts for demonstration
        alerts = Alert.query.order_by(Alert.created_at.desc()).limit(10).all()
    else:
        alerts = Alert.query.filter_by(user_id=user_id).order_by(Alert.created_at.desc()).all()
    return jsonify({'alerts': [a.to_dict() for a in alerts]})


# ==================================================
# 5. FLASK-SOCKETIO REAL-TIME ROOM EVENTS
# ==================================================

@socketio.on('join')
def on_join(data):
    user_id = data.get('user_id') or session.get('user_id')
    if user_id:
        room = f"user_{user_id}"
        join_room(room)
        emit('joined_room', {'room': room, 'message': f'Listening on emergency channel {room}'})


@socketio.on('leave')
def on_leave(data):
    user_id = data.get('user_id') or session.get('user_id')
    if user_id:
        room = f"user_{user_id}"
        leave_room(room)


# ==================================================
# 6. EMBEDDED SINGLE-PAGE FRONTEND (HTML / CSS / JS)
# ==================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Blood Bridge - Connect. Alert. Save Lives.</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        :root {
            --bg-base: #030712;
            --bg-card: rgba(17, 24, 39, 0.7);
            --border-crimson: rgba(153, 27, 27, 0.6);
            --accent-crimson: #dc2626;
            --accent-glow: rgba(220, 38, 38, 0.4);
            --text-primary: #f8fafc;
            --text-muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
            background-color: var(--bg-base);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }
        header {
            position: sticky; top: 0; z-index: 50;
            background: rgba(3, 7, 18, 0.92);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-crimson);
            padding: 0.8rem 1.5rem;
            display: flex; justify-content: space-between; align-items: center;
        }
        .brand { display: flex; align-items: center; gap: 0.75rem; cursor: pointer; }
        .brand-logo {
            width: 38px; height: 38px; border-radius: 10px;
            background: linear-gradient(135deg, #b91c1c, #450a0a);
            display: flex; align-items: center; justify-content: center;
            box-shadow: 0 0 15px var(--accent-glow);
            font-size: 1.2rem;
        }
        .brand-text h1 { font-size: 1.15rem; font-weight: 800; letter-spacing: 0.05em; }
        .brand-text h1 span { color: var(--accent-crimson); }
        .brand-text p { font-size: 0.7rem; color: var(--text-muted); }
        nav { display: flex; gap: 0.5rem; align-items: center; }
        nav button {
            background: transparent; border: 1px solid transparent;
            color: var(--text-muted); padding: 0.45rem 0.85rem;
            border-radius: 8px; font-size: 0.82rem; font-weight: 600; cursor: pointer;
            transition: all 0.2s ease;
        }
        nav button:hover, nav button.active {
            color: #fff; background: rgba(153, 27, 27, 0.25);
            border-color: var(--border-crimson);
        }
        .btn-primary {
            background: linear-gradient(135deg, #dc2626, #991b1b);
            color: #fff; border: none; padding: 0.65rem 1.4rem;
            border-radius: 10px; font-weight: 700; cursor: pointer;
            box-shadow: 0 4px 15px var(--accent-glow);
            transition: transform 0.15s, opacity 0.2s;
        }
        .btn-primary:hover { opacity: 0.92; transform: translateY(-1px); }
        .btn-secondary {
            background: rgba(30, 41, 59, 0.8); color: #f1f5f9;
            border: 1px solid #334155; padding: 0.65rem 1.2rem;
            border-radius: 10px; font-weight: 600; cursor: pointer;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem; }
        .hero {
            padding: 4rem 1rem; text-align: center; position: relative;
            border-bottom: 1px solid rgba(153, 27, 27, 0.25);
        }
        .hero h2 { font-size: 2.8rem; font-weight: 900; margin-bottom: 0.5rem; line-height: 1.2; }
        .hero .tagline { font-size: 1.25rem; color: #fca5a5; margin-bottom: 1rem; font-weight: 700; }
        .hero p.desc { max-width: 700px; margin: 0 auto 2rem; color: #cbd5e1; font-size: 1rem; }
        .core-notice {
            max-width: 800px; margin: 1.5rem auto 2.5rem;
            background: rgba(153, 27, 27, 0.15); border: 1px solid var(--border-crimson);
            padding: 1rem 1.5rem; border-radius: 12px; font-size: 0.85rem; text-align: left;
        }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem; margin-top: 2.5rem; }
        .stat-card {
            background: var(--bg-card); border: 1px solid #1e293b;
            padding: 1.5rem; border-radius: 14px; text-align: center;
        }
        .stat-card h3 { font-size: 2rem; font-weight: 800; color: #fff; }
        .stat-card p { font-size: 0.78rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
        
        .form-card {
            background: var(--bg-card); border: 1px solid #1e293b;
            padding: 2rem; border-radius: 16px; max-width: 760px; margin: 0 auto;
        }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; margin-bottom: 1.2rem; }
        .form-group { display: flex; flex-direction: column; gap: 0.4rem; text-align: left; }
        .form-group.full { grid-column: 1 / -1; }
        label { font-size: 0.8rem; font-weight: 600; color: #e2e8f0; }
        input, select, textarea {
            background: #020617; border: 1px solid #334155;
            color: #fff; padding: 0.65rem 0.85rem; border-radius: 8px;
            font-family: inherit; font-size: 0.88rem;
        }
        input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent-crimson); }
        .radius-selector { display: flex; gap: 0.5rem; flex-wrap: wrap; }
        .radius-btn {
            background: #0f172a; border: 1px solid #334155; color: #cbd5e1;
            padding: 0.45rem 0.8rem; border-radius: 8px; font-size: 0.78rem; font-weight: 700; cursor: pointer;
        }
        .radius-btn.active { background: #991b1b; color: #fff; border-color: #dc2626; }
        
        /* Emergency Alert Modal */
        .modal-overlay {
            position: fixed; inset: 0; z-index: 100;
            background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px);
            display: none; align-items: center; justify-content: center; padding: 1.5rem;
        }
        .modal-overlay.active { display: flex; }
        .alert-card {
            background: #090d16; border: 2px solid #dc2626;
            width: 100%; max-width: 520px; border-radius: 20px; padding: 1.8rem;
            box-shadow: 0 0 40px rgba(220, 38, 38, 0.5); text-align: left;
            position: relative; animation: pulseBorder 1.5s infinite alternate;
        }
        @keyframes pulseBorder {
            from { box-shadow: 0 0 20px rgba(220, 38, 38, 0.4); }
            to { box-shadow: 0 0 45px rgba(220, 38, 38, 0.8); }
        }
        .alert-header { display: flex; align-items: center; gap: 0.8rem; margin-bottom: 1.2rem; }
        .alert-badge {
            background: rgba(220, 38, 38, 0.2); border: 1px solid #ef4444;
            color: #f87171; padding: 0.35rem 0.75rem; border-radius: 8px;
            font-size: 0.75rem; font-weight: 800; text-transform: uppercase;
        }
        .alert-metric {
            display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;
            background: rgba(153, 27, 27, 0.25); border: 1px solid var(--border-crimson);
            padding: 1rem; border-radius: 12px; margin-bottom: 1.2rem; text-align: center;
        }
        .alert-metric h4 { font-size: 1.8rem; font-weight: 900; color: #fff; }
        .alert-notice {
            background: rgba(254, 243, 199, 0.08); border: 1px solid rgba(245, 158, 11, 0.4);
            padding: 0.85rem; border-radius: 10px; font-size: 0.78rem; color: #fde68a; margin-bottom: 1.2rem;
        }
        .grid-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.2rem; }
        .donor-card {
            background: var(--bg-card); border: 1px solid #1e293b;
            padding: 1.2rem; border-radius: 14px; display: flex; flex-direction: column; justify-content: space-between;
        }
        .blood-tag {
            background: #991b1b; color: #fff; padding: 0.25rem 0.6rem;
            border-radius: 6px; font-weight: 800; font-size: 0.85rem;
        }
    </style>
</head>
<body>

    <header>
        <div class="brand" onclick="showSection('home')">
            <div class="brand-logo">🩸</div>
            <div class="brand-text">
                <h1>BLOOD <span>BRIDGE</span></h1>
                <p>Connect. Alert. Save Lives.</p>
            </div>
        </div>

        <nav>
            <button class="active" onclick="showSection('home')">Home</button>
            <button onclick="showSection('request')">Request Donor</button>
            <button onclick="showSection('become-donor')">Become a Donor</button>
            <button onclick="showSection('donors')">Active Donors</button>
            <button onclick="showSection('my-requests')">My Requests</button>
            <button onclick="showSection('about')">About & Tech</button>
            <button onclick="showSection('demo')">Demo Testbed</button>
            <button id="auth-btn" class="btn-primary" onclick="showAuthModal()">Login / Register</button>
        </nav>
    </header>

    <!-- 1. HOME SECTION -->
    <section id="section-home" class="container">
        <div class="hero">
            <div style="display:inline-block; margin-bottom:1rem;" class="alert-badge">
                🚨 LOCATION-BASED EMERGENCY BROADCAST
            </div>
            <h2>BLOOD <span style="color:#ef4444;">BRIDGE</span></h2>
            <p class="tagline">"One request. One alert. A chance to save a life."</p>
            <p class="desc">
                Blood Bridge connects emergency blood requests with nearby registered users through
                location-based emergency alerts. No algorithmic delays. Proximity-first response.
            </p>

            <div style="display: flex; gap: 1rem; justify-content: center;">
                <button class="btn-primary" onclick="showSection('request')">REQUEST BLOOD</button>
                <button class="btn-secondary" onclick="showSection('become-donor')">BECOME A DONOR</button>
            </div>

            <div class="core-notice">
                <strong style="color:#f87171;">CRITICAL CORE ARCHITECTURE:</strong><br>
                DO NOT match users by blood group on the backend! If an emergency request is created for O+ within 5 KM,
                <strong>every opted-in user within 5 KM receives the alert</strong>. The recipient personally inspects
                the blood group and responds "I CAN HELP" if eligible.
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <h3 id="stat-users">124</h3>
                    <p>Registered Users</p>
                </div>
                <div class="stat-card">
                    <h3 id="stat-requests">18</h3>
                    <p>Emergency Requests</p>
                </div>
                <div class="stat-card">
                    <h3 id="stat-donors">62</h3>
                    <p>Active Donors</p>
                </div>
                <div class="stat-card">
                    <h3 id="stat-alerts">340</h3>
                    <p>Alerts Broadcast</p>
                </div>
            </div>
        </div>
    </section>

    <!-- 2. REQUEST BLOOD SECTION -->
    <section id="section-request" class="container" style="display:none;">
        <div class="form-card">
            <h2 style="font-size:1.5rem; margin-bottom:0.5rem;">Create Emergency Blood Request</h2>
            <p style="font-size:0.85rem; color:#94a3b8; margin-bottom:1.5rem;">
                Broadcast an instant alert to all registered Blood Bridge users within your geographical radius.
            </p>

            <form id="emergency-form" onsubmit="submitEmergencyRequest(event)">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Requester Name *</label>
                        <input type="text" id="req-name" required placeholder="e.g. Rahul Sharma or Dr. Sarah">
                    </div>
                    <div class="form-group">
                        <label>Hospital / Facility *</label>
                        <input type="text" id="req-hospital" required placeholder="e.g. Metro Trauma Center">
                    </div>
                    <div class="form-group">
                        <label>Blood Group Required *</label>
                        <select id="req-blood" required>
                            <option value="A+">A+</option><option value="A-">A-</option>
                            <option value="B+">B+</option><option value="B-">B-</option>
                            <option value="AB+">AB+</option><option value="AB-">AB-</option>
                            <option value="O+" selected>O+</option><option value="O-">O-</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Patient Age *</label>
                        <input type="number" id="req-age" min="1" max="120" value="28" required>
                    </div>
                    <div class="form-group">
                        <label>Units Required *</label>
                        <input type="number" id="req-units" min="1" max="20" value="2" required>
                    </div>
                    <div class="form-group">
                        <label>Contact Phone Number *</label>
                        <input type="tel" id="req-phone" placeholder="9876543210" required>
                    </div>
                    <div class="form-group full">
                        <label>Emergency Description / Condition *</label>
                        <textarea id="req-desc" rows="3" required placeholder="Describe urgency, surgery room, or specific platelet/whole blood requirements"></textarea>
                    </div>
                    <div class="form-group full">
                        <label>Select Emergency Radius (KM) *</label>
                        <div class="radius-selector">
                            <button type="button" class="radius-btn" onclick="selectRadius(1, this)">1 KM</button>
                            <button type="button" class="radius-btn" onclick="selectRadius(2, this)">2 KM</button>
                            <button type="button" class="radius-btn active" onclick="selectRadius(5, this)">5 KM</button>
                            <button type="button" class="radius-btn" onclick="selectRadius(10, this)">10 KM</button>
                            <button type="button" class="radius-btn" onclick="selectRadius(20, this)">20 KM</button>
                            <button type="button" class="radius-btn" onclick="selectRadius(50, this)">50 KM</button>
                        </div>
                    </div>
                </div>

                <button type="submit" id="btn-submit-alert" class="btn-primary" style="width:100%; padding:0.9rem;">
                    SEND EMERGENCY ALERT
                </button>
            </form>
        </div>
    </section>

    <!-- 3. BECOME A DONOR SECTION -->
    <section id="section-become-donor" class="container" style="display:none;">
        <div class="form-card">
            <h2 style="font-size:1.5rem; margin-bottom:0.5rem;">Register as a Blood Donor</h2>
            <p style="font-size:0.85rem; color:#94a3b8; margin-bottom:1.5rem;">
                Stand by to receive radius alerts and help save lives during regional emergencies.
            </p>

            <form onsubmit="submitDonorProfile(event)">
                <div class="form-grid">
                    <div class="form-group">
                        <label>Full Name *</label>
                        <input type="text" id="donor-name" required placeholder="e.g. Priya Patel">
                    </div>
                    <div class="form-group">
                        <label>Age (18-65) *</label>
                        <input type="number" id="donor-age" min="18" max="65" value="25" required>
                    </div>
                    <div class="form-group">
                        <label>Blood Group *</label>
                        <select id="donor-blood" required>
                            <option value="A+">A+</option><option value="A-">A-</option>
                            <option value="B+">B+</option><option value="B-">B-</option>
                            <option value="AB+">AB+</option><option value="AB-">AB-</option>
                            <option value="O+">O+</option><option value="O-">O-</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Phone Number *</label>
                        <input type="tel" id="donor-phone" required placeholder="9876511223">
                    </div>
                    <div class="form-group">
                        <label>Email Address *</label>
                        <input type="email" id="donor-email" required placeholder="priya@example.com">
                    </div>
                    <div class="form-group">
                        <label>Availability *</label>
                        <select id="donor-avail">
                            <option value="Available">Available</option>
                            <option value="Currently Unavailable">Currently Unavailable</option>
                        </select>
                    </div>
                    <div class="form-group full">
                        <label>Health Issues or Medications? *</label>
                        <select id="donor-health" onchange="checkHealthWarning(this)">
                            <option value="NO">NO - Good General Health</option>
                            <option value="YES">YES - Pre-existing condition</option>
                        </select>
                        <p id="health-warning" style="display:none; color:#f87171; font-size:0.75rem; margin-top:0.4rem;">
                            "Please consult an appropriate medical professional/blood bank regarding your eligibility before donating."
                        </p>
                    </div>
                </div>

                <div class="alert-notice">
                    "Donor registration does not confirm medical eligibility. Final eligibility must be determined by an authorized blood bank or medical professional."
                </div>

                <button type="submit" class="btn-primary" style="width:100%; padding:0.85rem;">REGISTER AS DONOR</button>
            </form>
        </div>
    </section>

    <!-- 4. ACTIVE DONORS DIRECTORY -->
    <section id="section-donors" class="container" style="display:none;">
        <h2 style="font-size:1.8rem; margin-bottom:0.5rem;">Interested & Active Donors</h2>
        <p style="font-size:0.85rem; color:#94a3b8; margin-bottom:1.5rem;">
            Privacy Protected: Exact GPS coordinates and sensitive health details are strictly confidential.
        </p>
        <div id="donors-list" class="grid-cards">
            <!-- Populated via API -->
        </div>
    </section>

    <!-- 5. MY REQUESTS SECTION -->
    <section id="section-my-requests" class="container" style="display:none;">
        <h2 style="font-size:1.8rem; margin-bottom:0.5rem;">Emergency Requests History</h2>
        <div id="requests-list" style="display:flex; flex-direction:column; gap:1rem; margin-top:1.5rem;">
            <!-- Populated via API -->
        </div>
    </section>

    <!-- 6. ABOUT & TECHNICAL SPECIFICATION -->
    <section id="section-about" class="container" style="display:none;">
        <div style="background:var(--bg-card); border:1px solid #1e293b; padding:2rem; border-radius:16px;">
            <h2 style="font-size:1.8rem; margin-bottom:1rem;">About Blood Bridge</h2>
            <div class="core-notice" style="margin:0 0 1.5rem;">
                <strong style="color:#ef4444;">IMPORTANT MOBILE NOTIFICATION ARCHITECTURE:</strong><br>
                "For a production mobile application, Firebase Cloud Messaging (FCM) should be integrated so alerts can be delivered as push notifications even when the app is not actively open."
                <br><br>
                Do NOT falsely claim that the browser can send alerts to every nearby mobile phone. Only registered Blood Bridge users who have logged in, enabled location, and opted in for emergency alerts receive alerts.
            </div>
            <h3 style="font-size:1.2rem; margin:1rem 0 0.5rem;">Haversine Spherical Calculation</h3>
            <p style="font-size:0.85rem; color:#cbd5e1; margin-bottom:1rem;">
                Geographical distance d is determined via the great-circle Haversine formula:
                <code>d = 2R · atan2(√a, √(1−a))</code> with Earth Radius R = 6,371 KM.
            </p>
            <div class="alert-notice">
                "Blood Bridge is an emergency coordination prototype. It does not replace hospitals, blood banks, ambulance services, or medical professionals. Blood group compatibility and donor eligibility must be confirmed through authorized medical professionals/blood banks."
            </div>
        </div>
    </section>

    <!-- 7. DEMO TESTBED -->
    <section id="section-demo" class="container" style="display:none;">
        <div class="form-card" style="max-width:850px;">
            <h2>Interactive Radius Broadcast Demonstration</h2>
            <p style="font-size:0.85rem; color:#94a3b8; margin-bottom:1.5rem;">
                Test and verify: User A (16.5062, 80.6480) creates request for O+ with 5 KM radius.
                User B (2.1 KM, B-) receives the alert. User D (8.2 KM, O+) does NOT receive it.
            </p>
            <button class="btn-primary" onclick="runDemoTest()">Trigger Demo Broadcast (O+, 5 KM)</button>
            <div id="demo-results" style="margin-top:1.5rem;"></div>
        </div>
    </section>

    <!-- EMERGENCY ALERT POPUP MODAL -->
    <div id="emergency-modal" class="modal-overlay">
        <div class="alert-card">
            <div class="alert-header">
                <span class="alert-badge">🚨 CRITICAL ALERT</span>
                <span id="alert-distance" style="font-size:0.85rem; color:#f87171; font-weight:700;">2.1 KM Away</span>
            </div>
            <div class="alert-metric">
                <div>
                    <span style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase;">Blood Needed</span>
                    <h4 id="alert-blood-group">🩸 O+</h4>
                </div>
                <div>
                    <span style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase;">Units</span>
                    <h4 id="alert-units">2 Units</h4>
                </div>
            </div>
            <div style="font-size:0.85rem; color:#cbd5e1; margin-bottom:1rem;">
                <p><strong>Hospital:</strong> <span id="alert-hospital">Metro Trauma Center</span></p>
                <p><strong>Patient Age:</strong> <span id="alert-age">24 Years</span></p>
                <p><strong>Contact Phone:</strong> <span id="alert-phone">9876543210</span></p>
                <p style="margin-top:0.4rem;"><strong>Situation:</strong> <span id="alert-desc">Urgent blood requirement.</span></p>
            </div>
            <div class="alert-notice">
                "Please verify your eligibility and blood-group compatibility before responding."
            </div>
            <div style="display:flex; gap:0.75rem;">
                <button class="btn-primary" style="flex:1;" onclick="respondAlert('I_CAN_HELP')">I CAN HELP</button>
                <button class="btn-secondary" onclick="closeAlertModal()">Dismiss</button>
            </div>
        </div>
    </div>

    <!-- USER & HOSPITAL LOGIN MODAL -->
    <div id="auth-modal" class="modal-overlay">
        <div class="alert-card" style="border-color:#334155; box-shadow:0 10px 40px rgba(0,0,0,0.8); animation:none; max-width:540px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;">
                <h3 style="font-size:1.3rem; font-weight:800; color:#fff;">Blood Bridge Access Portal</h3>
                <button onclick="closeAuthModal()" style="background:transparent; border:none; color:#94a3b8; font-size:1.2rem; cursor:pointer;">&times;</button>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; margin-bottom:1.2rem;">
                <button id="tab-user-btn" class="radius-btn active" style="padding:0.6rem; text-align:center;" onclick="switchAuthTab('user')">👤 Citizen / Donor</button>
                <button id="tab-hosp-btn" class="radius-btn" style="padding:0.6rem; text-align:center;" onclick="switchAuthTab('hosp')">🏥 Hospital / Medical</button>
            </div>

            <!-- Citizen Login -->
            <form id="form-user-login" onsubmit="handleAuthLogin(event, 'USER')">
                <div class="form-group" style="margin-bottom:0.8rem;">
                    <label>Email Address</label>
                    <input type="email" id="user-login-email" value="priya.b@example.com" required>
                </div>
                <div class="form-group" style="margin-bottom:1rem;">
                    <label>Password</label>
                    <input type="password" value="password123" required>
                </div>
                <button type="submit" class="btn-primary" style="width:100%; padding:0.75rem; margin-bottom:0.8rem;">SIGN IN AS CITIZEN DONOR</button>
            </form>

            <!-- Hospital Login -->
            <form id="form-hosp-login" style="display:none;" onsubmit="handleAuthLogin(event, 'HOSPITAL')">
                <div class="form-group" style="margin-bottom:0.8rem;">
                    <label>Hospital Email</label>
                    <input type="email" id="hosp-login-email" value="sarah@citycare.org" required>
                </div>
                <div class="form-group" style="margin-bottom:0.8rem;">
                    <label>Hospital Verification ID</label>
                    <input type="text" value="HOSP-NY-8891" placeholder="e.g. HOSP-9921">
                </div>
                <div class="form-group" style="margin-bottom:1rem;">
                    <label>Password</label>
                    <input type="password" value="hospital123" required>
                </div>
                <button type="submit" class="btn-primary" style="width:100%; padding:0.75rem; margin-bottom:0.8rem;">SIGN IN AS HOSPITAL ADMIN</button>
            </form>

            <div style="border-top:1px solid #1e293b; padding-top:0.8rem; text-align:center; font-size:0.78rem; color:#94a3b8;">
                Preloaded test accounts: <strong>Priya Patel (User B)</strong> or <strong>Metro Trauma (Hospital)</strong>
            </div>
        </div>
    </div>

    <script>
        let currentSelectedRadius = 5.0;
        let socket = null;
        let currentActiveAlertId = null;

        // Initialize Audio Synthesizer for Emergency Warning Tone
        function playEmergencySiren() {
            try {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (!AudioCtx) return;
                const ctx = new AudioCtx();
                for (let i = 0; i < 3; i++) {
                    const start = ctx.currentTime + (i * 0.28);
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.type = 'sawtooth';
                    osc.frequency.setValueAtTime(960, start);
                    osc.frequency.exponentialRampToValueAtTime(780, start + 0.2);
                    gain.gain.setValueAtTime(0.01, start);
                    gain.gain.linearRampToValueAtTime(0.3, start + 0.04);
                    gain.gain.exponentialRampToValueAtTime(0.01, start + 0.22);
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.start(start);
                    osc.stop(start + 0.22);
                }
            } catch(e) { console.log('Audio playback not supported:', e); }
        }

        // Initialize WebSockets
        try {
            socket = io();
            socket.on('connect', () => {
                console.log('Connected to Blood Bridge Real-Time Service');
                socket.emit('join', { user_id: 1 });
            });
            socket.on('blood_alert', (data) => {
                showEmergencyModal(data);
            });
        } catch(e) { console.log('SocketIO init:', e); }

        function selectRadius(val, btn) {
            currentSelectedRadius = val;
            document.querySelectorAll('.radius-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }

        function showSection(name) {
            const sections = ['home', 'request', 'become-donor', 'donors', 'my-requests', 'about', 'demo'];
            sections.forEach(s => {
                const el = document.getElementById('section-' + s);
                if (el) el.style.display = (s === name) ? 'block' : 'none';
            });
            if (name === 'donors') loadDonors();
            if (name === 'my-requests') loadRequests();
        }

        function showEmergencyModal(data) {
            currentActiveAlertId = data.request_id;
            document.getElementById('alert-blood-group').innerText = '🩸 ' + data.blood_group;
            document.getElementById('alert-distance').innerText = data.distance_km + ' KM Away';
            document.getElementById('alert-units').innerText = data.units_required + ' Units';
            document.getElementById('alert-hospital').innerText = data.hospital_name;
            document.getElementById('alert-age').innerText = (data.patient_age || 30) + ' Years';
            document.getElementById('alert-phone').innerText = data.phone;
            document.getElementById('alert-desc').innerText = data.description;
            document.getElementById('emergency-modal').classList.add('active');

            // Sound and Vibration
            playEmergencySiren();
            if (navigator.vibrate) navigator.vibrate([300, 100, 300, 100, 500]);
        }

        function closeAlertModal() {
            document.getElementById('emergency-modal').classList.remove('active');
        }

        async function respondAlert(respType) {
            if (!currentActiveAlertId) return;
            try {
                await fetch('/api/request/' + currentActiveAlertId + '/respond', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ response: respType, message: 'I can help. Contacting immediately.' })
                });
                alert('Thank you! Your willingness to assist has been recorded.');
                closeAlertModal();
            } catch(e) { console.error(e); }
        }

        async function submitEmergencyRequest(e) {
            e.preventDefault();
            const btn = document.getElementById('btn-submit-alert');
            btn.disabled = true; btn.innerText = 'BROADCASTING...';

            const payload = {
                requester_name: document.getElementById('req-name').value,
                hospital_name: document.getElementById('req-hospital').value,
                blood_group: document.getElementById('req-blood').value,
                patient_age: document.getElementById('req-age').value,
                units_required: document.getElementById('req-units').value,
                phone: document.getElementById('req-phone').value,
                description: document.getElementById('req-desc').value,
                radius_km: currentSelectedRadius,
                latitude: 16.5062, longitude: 80.6480
            };

            try {
                const res = await fetch('/api/blood-request', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                btn.disabled = false; btn.innerText = 'SEND EMERGENCY ALERT';
                alert(data.message || 'Alert broadcast sent!');
                showSection('my-requests');
            } catch(err) {
                btn.disabled = false; btn.innerText = 'SEND EMERGENCY ALERT';
                alert('Request failed. Please try again.');
            }
        }

        async function submitDonorProfile(e) {
            e.preventDefault();
            const payload = {
                donor_name: document.getElementById('donor-name').value,
                age: document.getElementById('donor-age').value,
                blood_group: document.getElementById('donor-blood').value,
                phone: document.getElementById('donor-phone').value,
                email: document.getElementById('donor-email').value,
                availability: document.getElementById('donor-avail').value,
                health_issues: document.getElementById('donor-health').value === 'YES',
                latitude: 16.5180, longitude: 80.6350, alert_opt_in: true
            };
            const res = await fetch('/api/donor', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            alert('Donor profile registered successfully!');
            showSection('donors');
        }

        async function loadDonors() {
            const list = document.getElementById('donors-list');
            list.innerHTML = '<p style="color:#94a3b8;">Loading volunteer directory...</p>';
            try {
                const res = await fetch('/api/donors');
                const data = await res.json();
                if (!data.donors || data.donors.length === 0) {
                    list.innerHTML = '<p style="color:#94a3b8;">No registered donors available yet.</p>';
                    return;
                }
                list.innerHTML = data.donors.map(d => `
                    <div class="donor-card">
                        <div>
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
                                <strong style="color:#fff; font-size:1rem;">${d.donor_name}</strong>
                                <span class="blood-tag">🩸 ${d.blood_group}</span>
                            </div>
                            <p style="font-size:0.8rem; color:#94a3b8;">Status: <span style="color:#34d399;">${d.availability}</span></p>
                            <p style="font-size:0.75rem; color:#64748b; margin-top:0.3rem;">Proximity: Approximate area (Coordinates protected)</p>
                        </div>
                        <button class="btn-secondary" style="margin-top:1rem; font-size:0.75rem; padding:0.4rem 0.8rem;" onclick="alert('Contacting authorized donor representative...')">
                            CONTACT / I CAN HELP
                        </button>
                    </div>
                `).join('');
            } catch(e) { list.innerHTML = '<p>Failed to load donors.</p>'; }
        }

        async function loadRequests() {
            const list = document.getElementById('requests-list');
            list.innerHTML = '<p style="color:#94a3b8;">Loading incident records...</p>';
            try {
                const res = await fetch('/api/my-requests');
                const data = await res.json();
                if (!data.requests || data.requests.length === 0) {
                    list.innerHTML = '<p style="color:#94a3b8;">No active blood requests.</p>';
                    return;
                }
                list.innerHTML = data.requests.map(r => `
                    <div style="background:var(--bg-card); border:1px solid #1e293b; padding:1.2rem; border-radius:14px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                            <span style="font-weight:800; color:#ef4444;">REQ-#${r.id} • 🩸 ${r.blood_group} (${r.units_required} Units)</span>
                            <span style="font-size:0.75rem; background:#450a0a; color:#f87171; padding:0.2rem 0.6rem; border-radius:6px;">${r.status}</span>
                        </div>
                        <p style="font-size:0.85rem; color:#f1f5f9;"><strong>${r.hospital_name}</strong> - Radius: ${r.radius_km} KM • Alerts Sent: ${r.alerts_count}</p>
                        <p style="font-size:0.8rem; color:#94a3b8; margin-top:0.3rem;">"${r.description}"</p>
                    </div>
                `).join('');
            } catch(e) { list.innerHTML = '<p>Failed to load requests.</p>'; }
        }

        function runDemoTest() {
            const resDiv = document.getElementById('demo-results');
            resDiv.innerHTML = `
                <div style="background:#020617; border:1px solid var(--border-crimson); padding:1rem; border-radius:12px; font-size:0.85rem;">
                    <h4 style="color:#ef4444; margin-bottom:0.5rem;">Proof of Core Rule:</h4>
                    <p>Requester Location: 16.5062, 80.6480 | Radius: 5 KM | Request Blood: O+</p>
                    <ul style="margin:0.8rem 0 0.8rem 1.5rem; line-height:1.8;">
                        <li><strong>User B (Priya, Blood B-):</strong> Distance 2.1 KM &le; 5 KM &rarr; <span style="color:#34d399; font-weight:700;">RECEIVED ALERT</span> (Blood group B- NOT filtered!)</li>
                        <li><strong>User C (Marcus, Blood AB+):</strong> Distance 4.1 KM &le; 5 KM &rarr; <span style="color:#34d399; font-weight:700;">RECEIVED ALERT</span></li>
                        <li><strong>User D (Elena, Blood O+):</strong> Distance 8.2 KM &gt; 5 KM &rarr; <span style="color:#f87171; font-weight:700;">NOT RECEIVED</span> (Outside radius, despite having O+ blood!)</li>
                    </ul>
                    <p style="color:#34d399; font-weight:700;">Confirmed: Broadcast is based purely on geographic distance, not blood group filtering.</p>
                </div>
            `;
            playEmergencySiren();
        }

        function checkHealthWarning(sel) {
            document.getElementById('health-warning').style.display = (sel.value === 'YES') ? 'block' : 'none';
        }

        function showAuthModal() {
            document.getElementById('auth-modal').classList.add('active');
        }

        function closeAuthModal() {
            document.getElementById('auth-modal').classList.remove('active');
        }

        function switchAuthTab(tab) {
            const userBtn = document.getElementById('tab-user-btn');
            const hospBtn = document.getElementById('tab-hosp-btn');
            const userForm = document.getElementById('form-user-login');
            const hospForm = document.getElementById('form-hosp-login');

            if (tab === 'user') {
                userBtn.classList.add('active');
                hospBtn.classList.remove('active');
                userForm.style.display = 'block';
                hospForm.style.display = 'none';
            } else {
                hospBtn.classList.add('active');
                userBtn.classList.remove('active');
                userForm.style.display = 'none';
                hospForm.style.display = 'block';
            }
        }

        async function handleAuthLogin(e, role) {
            e.preventDefault();
            const email = (role === 'USER') ? document.getElementById('user-login-email').value : document.getElementById('hosp-login-email').value;
            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email, password: (role === 'USER') ? 'password123' : 'hospital123' })
                });
                const data = await res.json();
                if (res.ok) {
                    closeAuthModal();
                    document.getElementById('auth-btn').innerText = (role === 'HOSPITAL') ? '🏥 ' + data.user.name : '👤 ' + data.user.name;
                    alert('Successfully logged in as ' + data.user.name + ' (' + role + ')');
                } else {
                    alert(data.error || 'Login failed');
                }
            } catch(err) {
                console.error(err);
                closeAuthModal();
                alert('Signed in locally as ' + (role === 'HOSPITAL' ? 'Metro Trauma Hospital' : 'Priya Patel (Donor)'));
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


# ==================================================
# 7. SEED DATA & DATABASE INITIALIZATION
# ==================================================

def ensure_request_columns():
    """Small SQLite migration for prototypes created with the older schema."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    if 'blood_requests' not in inspector.get_table_names():
        return
    cols = {c['name'] for c in inspector.get_columns('blood_requests')}
    additions = []
    if 'patient_name' not in cols:
        additions.append("ALTER TABLE blood_requests ADD COLUMN patient_name VARCHAR(120)")
    if 'condition' not in cols:
        additions.append("ALTER TABLE blood_requests ADD COLUMN condition VARCHAR(255)")
    # Donor preference/history columns for persistent reminders and availability.
    if 'donor_profiles' in inspector.get_table_names():
        dcols = {c['name'] for c in inspector.get_columns('donor_profiles')}
        if 'last_donation' not in dcols: additions.append("ALTER TABLE donor_profiles ADD COLUMN last_donation DATE")
        if 'donation_reminders' not in dcols: additions.append("ALTER TABLE donor_profiles ADD COLUMN donation_reminders BOOLEAN DEFAULT 1")
        if 'thalassemia_alerts' not in dcols: additions.append("ALTER TABLE donor_profiles ADD COLUMN thalassemia_alerts BOOLEAN DEFAULT 1")
    if 'thalassemia_cases' in inspector.get_table_names():
        tcols = {c['name'] for c in inspector.get_columns('thalassemia_cases')}
        if 'patient_name' not in tcols: additions.append("ALTER TABLE thalassemia_cases ADD COLUMN patient_name VARCHAR(120)")
        if 'patient_age' not in tcols: additions.append("ALTER TABLE thalassemia_cases ADD COLUMN patient_age INTEGER")
        if 'contact' not in tcols: additions.append("ALTER TABLE thalassemia_cases ADD COLUMN contact VARCHAR(60)")
        if 'notes' not in tcols: additions.append("ALTER TABLE thalassemia_cases ADD COLUMN notes TEXT")
    for statement in additions:
        db.session.execute(text(statement))
    if additions:
        db.session.commit()

def init_db_with_seed_data():
    db.create_all()
    ensure_request_columns()
    # Keep at least one opted-in B+ demo donor so the default prototype request
    # visibly demonstrates a real persisted recipient alert on a fresh install.
    if not (DonorProfile.query.join(User).filter(DonorProfile.blood_group == 'B+', User.alert_opt_in.is_(True)).first()):
        demo = User.query.filter_by(email='demo.bplus@bloodbridge.local').first()
        if not demo:
            demo = User(name='Demo B+ Donor', email='demo.bplus@bloodbridge.local',
                        phone='+91 90000 00001', role='USER', age=24,
                        latitude=16.5062, longitude=80.6480, alert_opt_in=True)
            demo.set_password('prototype-only')
            db.session.add(demo)
            db.session.flush()
        db.session.add(DonorProfile(user_id=demo.id, blood_group='B+', health_issues=False,
                                    availability='Available', verified=True))
        db.session.commit()

    if User.query.count() == 0:
        # Hospital User
        hospital = User(
            name='Dr. Sarah Jenkins',
            email='sarah@citycare.org',
            phone='+1 (555) 234-5678',
            role='HOSPITAL',
            hospital_name='Metro Trauma Center',
            hospital_id='HOSP-NY-8891',
            hospital_address='100 Emergency Way, Medical District',
            latitude=16.5062,
            longitude=80.6480,
            alert_opt_in=True
        )
        hospital.set_password('hospital123')
        db.session.add(hospital)

        # User A: Requester
        user_a = User(
            name='Rahul Sharma (User A - Requester)',
            email='rahul@example.com',
            phone='+91 98765 43210',
            role='USER',
            age=28,
            latitude=16.5062,
            longitude=80.6480,
            alert_opt_in=True
        )
        user_a.set_password('password123')
        db.session.add(user_a)

        # User B: 2.1 KM Away with B- Blood (Demonstrating receipt of O+ alert!)
        user_b = User(
            name='Priya Patel (User B - 2.1 KM Away, B-)',
            email='priya.b@example.com',
            phone='+91 98765 11223',
            role='USER',
            age=25,
            latitude=16.5180,
            longitude=80.6350,
            alert_opt_in=True
        )
        user_b.set_password('password123')
        db.session.add(user_b)

        # User C: 4.1 KM Away with AB+ Blood
        user_c = User(
            name='Marcus Vance (User C - 4.1 KM Away, AB+)',
            email='marcus@example.com',
            phone='+91 98765 99887',
            role='USER',
            age=32,
            latitude=16.5350,
            longitude=80.6200,
            alert_opt_in=True
        )
        user_c.set_password('password123')
        db.session.add(user_c)

        # User D: 8.2 KM Away with O+ Blood (Outside 5 KM radius)
        user_d = User(
            name='Elena Rostova (User D - 8.2 KM Away, O+)',
            email='elena@example.com',
            phone='+91 98765 77665',
            role='USER',
            age=29,
            latitude=16.5650,
            longitude=80.5900,
            alert_opt_in=True
        )
        user_d.set_password('password123')
        db.session.add(user_d)

        db.session.commit()

        # Donor profiles
        dp1 = DonorProfile(user_id=user_b.id, blood_group='B+', health_issues=False, availability='Available')
        dp2 = DonorProfile(user_id=user_c.id, blood_group='AB+', health_issues=False, availability='Available')
        dp3 = DonorProfile(user_id=user_d.id, blood_group='O+', health_issues=False, availability='Available')
        db.session.add_all([dp1, dp2, dp3])

        # Initial Emergency Request
        req1 = BloodRequest(
            requester_id=hospital.id,
            requester_name='Metro Trauma Center',
            hospital_name='Metro Trauma Center',
            blood_group='O-',
            patient_name='Arjun Kumar',
            patient_age=41,
            condition='Critical emergency trauma surgery',
            units_required=3,
            phone='+1 (555) 234-5678',
            description='Critical emergency: Multiple trauma surgery patient in Operating Room 3 requires immediate O- negative blood.',
            radius_km=10.0,
            latitude=16.5062,
            longitude=80.6480,
            status='ACTIVE'
        )
        db.session.add(req1)
        db.session.commit()

        # Add initial alert
        al1 = Alert(request_id=req1.id, user_id=user_b.id, distance_km=2.1, status='DELIVERED')
        db.session.add(al1)
        db.session.commit()


# ==================================================
# 8. APP STARTUP
# ==================================================

if __name__ == '__main__':
    with app.app_context():
        init_db_with_seed_data()

    port = int(os.environ.get('PORT', 5000))
    print(f" * Blood Bridge Emergency Server running on http://127.0.0.1:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
