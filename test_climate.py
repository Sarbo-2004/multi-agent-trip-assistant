from services.weather_service import WeatherService

weather = WeatherService()

result = weather.get_weather(
    destination="rajasthan",
    start_date="2026-08-01",
    end_date="2026-08-05",
)

print(result.keys())
print(result["days"][0])