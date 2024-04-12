import pandas as pd
from datetime import datetime
from app import app 
from db import db
from models import Store, BusinessHours, PollData


# Function to load data from CSV into the database
def load_data():
    with app.app_context():
        # Load and insert store timezone data
        store_timezone_df = pd.read_csv('data/bq-results-20230125-202210-1674678181880.csv')
        for _, row in store_timezone_df.iterrows():
            store = Store(store_id=row['store_id'], timezone_str=row['timezone_str'])
            db.session.add(store)
        
        # Load and insert business hours data
        business_hours_df = pd.read_csv('data/Menu hours.csv')
        for _, row in business_hours_df.iterrows():
            # Convert string times to Python time objects
            start_time_obj = datetime.strptime(row['start_time_local'], '%H:%M:%S').time()
            end_time_obj = datetime.strptime(row['end_time_local'], '%H:%M:%S').time()

            business_hour = BusinessHours(
                store_id=row['store_id'], 
                dayOfWeek=row['day'], 
                start_time_local=start_time_obj, 
                end_time_local=end_time_obj
            )
            db.session.add(business_hour)

        
        # Load and insert store status data
        store_status_df = pd.read_csv('data/store status.csv')
        for _, row in store_status_df.iterrows():
            poll_data = PollData(
                store_id=row['store_id'], 
                timestamp_utc=pd.to_datetime(row['timestamp_utc']), 
                status=row['status']
            )
            db.session.add(poll_data)
        
        db.session.commit()

if __name__ == '__main__':
    load_data()