import requests

headers = {'Content-Type': 'application/json'}
response = requests.post('http://localhost:5000/trigger_report', headers=headers)
if response.status_code == 200:
    try:
        data = response.json()
        report_id = data.get('report_id')
        print("Report ID:", report_id)
    except ValueError:
        print("Response was not in JSON format.")
else:
    print(f"Request failed with status code: {response.status_code}")

print(response.text)

