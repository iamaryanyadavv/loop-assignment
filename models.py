from db import db
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship

class Store(db.Model):
    __tablename__ = 'stores'
    store_id = db.Column(db.String, primary_key=True)
    timezone_str = db.Column(db.String, default='America/Chicago')
    business_hours = relationship("BusinessHours", backref="store")
    poll_data = relationship("PollData", backref="store")

class BusinessHours(db.Model):
    __tablename__ = 'business_hours'
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.String, db.ForeignKey('stores.store_id'))
    dayOfWeek = db.Column(db.Integer)
    start_time_local = db.Column(db.Time)
    end_time_local = db.Column(db.Time)

class PollData(db.Model):
    __tablename__ = 'poll_data'
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.String, db.ForeignKey('stores.store_id'))
    timestamp_utc = db.Column(db.DateTime)
    status = db.Column(db.String)
