from datetime import datetime
from app import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    is_employee = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(256), nullable=True)  # Only employees have passwords
    
    # Relationship with fines
    fines = db.relationship('Fine', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    # Add these methods to make compatible with flask-login once installed
    def is_authenticated(self):
        return True
        
    def is_active(self):
        return True
        
    def is_anonymous(self):
        return False
        
    def get_id(self):
        return str(self.id)


class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(20), unique=True, nullable=False)
    state = db.Column(db.String(20), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationship with fines
    fines = db.relationship('Fine', backref='vehicle', lazy=True)
    
    def __repr__(self):
        return f'<Vehicle {self.plate_number}>'


class Fine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reason = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    paid = db.Column(db.Boolean, default=False)
    proof_image = db.Column(db.Text, nullable=True)  # Store base64 encoded image
    
    # Foreign keys
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<Fine {self.id} for Vehicle {self.vehicle_id}>'
