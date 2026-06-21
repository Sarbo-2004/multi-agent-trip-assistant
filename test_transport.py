import requests

from config.settings import settings

url = "https://api.openrouteservice.org/v2/directions/driving-car"

headers = {
    "Authorization": settings.OPENROUTESERVICE_API_KEY.get_secret_value(),
    "Content-Type": "application/json",
}

body = {
    "coordinates": [
        [75.7873, 26.9124],
        [75.8150, 26.9250],
    ]
}

response = requests.post(
    url,
    headers=headers,
    json=body,
)

print(response.status_code)
print(response.text)