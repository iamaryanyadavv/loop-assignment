from flask import Flask, jsonify, send_file
import threading
from uuid import uuid4
import pandas as pd
from db import db
import models 
from models import Store, BusinessHours, PollData
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload
from sqlalchemy import func
from flask_cors import CORS


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///loop_aryan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

CORS(app)

db.init_app(app)

with app.app_context():
    db.create_all()

tasks = {}  # status of report generation tasks

@app.route('/trigger_report', methods=['POST'])
def trigger_report():
    report_id = str(uuid4())
    tasks[report_id] = 'Running'
    threading.Thread(target=lambda: generate_report(report_id)).start()
    return jsonify({"report_id": report_id}), 202

@app.route('/get_report/<report_id>', methods=['GET'])
def get_report(report_id):
    status = tasks.get(report_id, None)
    if status is None:
        return jsonify({"error": "Report not found."}), 404
    elif status == 'Running':
        return jsonify({"status": "Running"}), 202
    elif status == 'Complete':
        return send_file(f'reports/report_{report_id}.csv', as_attachment=True)
    else:
        return jsonify({"error": "Unknown error."}), 500
    
def calculate_uptime_downtime(start, end, polls):
    """
    Calculate uptime and downtime between start and end times using poll data.
    Returns uptime and downtime in minutes.
    """
    uptime = downtime = 0
    last_status = "offline"  # assuming offline until the first poll
    last_time = start

    for poll in polls:
        if poll.timestamp_utc < start or poll.timestamp_utc > end:
            continue  # skipping polls outside the interval

        delta = (poll.timestamp_utc - last_time).total_seconds() / 60 
        if last_status == "online":
            uptime += delta
        else:
            downtime += delta

        # updating last status and time for next iteration
        last_status = poll.status
        last_time = poll.timestamp_utc

    # accounting for time after the last poll to the end of the interval
    final_delta = (end - last_time).total_seconds() / 60
    if last_status == "online":
        uptime += final_delta
    else:
        downtime += final_delta

    return uptime, downtime

def generate_report(report_id):
    with app.app_context():
        stores = db.session.query(Store.store_id, Store.timezone_str).all()

    # determining the "current" timestamp to use as a reference for "last" intervals
    max_timestamp = db.session.query(func.max(PollData.timestamp_utc)).scalar() or datetime.utcnow()
    
    report_data = []

    for store_id, timezone in stores:
        # assuming each report covers the last hour, day, and week from "current" timestamp
        end_time = max_timestamp
        start_times = {
            'last_hour': end_time - timedelta(hours=1),
            'last_day': end_time - timedelta(days=1),
            'last_week': end_time - timedelta(weeks=1),
        }

        # accumulating uptime/downtime
        uptimes = {'last_hour': 0, 'last_day': 0, 'last_week': 0}
        downtimes = {'last_hour': 0, 'last_day': 0, 'last_week': 0}

        for period, start_time in start_times.items():
            # fetching relevant business hours and poll data
            business_hours = BusinessHours.query.filter(
                BusinessHours.store_id == store_id,
                BusinessHours.start_time_local <= end_time.time(),
                BusinessHours.end_time_local >= start_time.time()
            ).all()

            polls = PollData.query.filter(
                PollData.store_id == store_id,
                PollData.timestamp_utc >= start_time,
                PollData.timestamp_utc <= end_time
            ).order_by(PollData.timestamp_utc.asc()).all()

            # calculating uptime/downtime for each business hour within the period
            for bh in business_hours:
                bh_start = datetime.combine(end_time.date(), bh.start_time_local)
                bh_end = datetime.combine(end_time.date(), bh.end_time_local)
                uptime, downtime = calculate_uptime_downtime(bh_start, bh_end, polls)
                uptimes[period] += uptime
                downtimes[period] += downtime

        # converting total uptimes and downtimes from minutes to hours for day and week
        report_row = {
            "store_id": store_id,
            "uptime_last_hour": uptimes['last_hour'],
            "uptime_last_day": uptimes['last_day'] / 60,
            "uptime_last_week": uptimes['last_week'] / 60,
            "downtime_last_hour": downtimes['last_hour'],
            "downtime_last_day": downtimes['last_day'] / 60,
            "downtime_last_week": downtimes['last_week'] / 60,
        }
        report_data.append(report_row)

    # writing report data to CSV
    report_df = pd.DataFrame(report_data)
    report_filename = f'reports/{report_id}.csv'
    report_df.to_csv(report_filename, index=False)

    # updating the report's task status
    tasks[report_id] = 'Complete'

    print(f"Report generated: {report_filename}")

@app.route('/check_data')
def check_data():
    stores_count = Store.query.count()
    business_hours_count = BusinessHours.query.count()
    poll_data_count = PollData.query.count()

    return f"Stores: {stores_count}, Business Hours: {business_hours_count}, Poll Data: {poll_data_count}"


@app.route('/report/store_activity/<int:store_id>', methods=['GET'])
def store_activity_report(store_id):
    print('store_id passed: ', store_id)
    # validating the store exists
    store = db.session.get(Store, store_id)
    if not store:
        return jsonify({"error": "Store not found."}), 404

    # fetching business hours and poll data for the store
    store_data = Store.query.options(
        joinedload(Store.business_hours),
        joinedload(Store.poll_data)
    ).filter_by(store_id=store_id).first()

    if not store_data:
        return jsonify({"error": "Data not found for the store."}), 404

    # Generate report
    report = generate_activity_report(store_data)

    return jsonify(report)

def generate_activity_report(store_data):
    print('store_data passed: ', store_data)
    report_data = []

    # last 30 days for simplicity
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    for business_hour in store_data.business_hours:
        # filtering poll data for each business day
        day = business_hour.dayOfWeek
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() == day:
                start_time = datetime.combine(current_date, business_hour.start_time_local)
                end_time = datetime.combine(current_date, business_hour.end_time_local)
                offline_periods = find_offline_periods(store_data.poll_data, start_time, end_time)
                if offline_periods:
                    report_data.append({
                        "date": current_date.strftime('%Y-%m-%d'),
                        "dayOfWeek": day,
                        "offline_periods": offline_periods,
                    })
            current_date += timedelta(days=1)

    return report_data

def find_offline_periods(poll_data, start_time, end_time):
    offline_periods = []
    offline_start = None

    for poll in sorted(poll_data, key=lambda x: x.timestamp_utc):
        if start_time <= poll.timestamp_utc <= end_time:
            if poll.status == 'offline' and not offline_start:
                # start of offline period
                offline_start = poll.timestamp_utc
            elif poll.status == 'online' and offline_start:
                # end of offline period
                offline_periods.append({"start": offline_start, "end": poll.timestamp_utc})
                offline_start = None

    # checking if the store went offline and hasn't come back online
    if offline_start:
        offline_periods.append({"start": offline_start, "end": end_time})

    return offline_periods

if __name__ == '__main__':
    app.run(debug=True)
