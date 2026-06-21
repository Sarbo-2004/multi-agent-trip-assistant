from services.gemini_service import GeminiService
from services.weather_service import WeatherService
from services.places_service import PlacesService
from services.routing_service import RoutingService

DESTINATION = "Jaipur"


def test_gemini():
    print("\n===== Testing Gemini =====")

    gemini = GeminiService()

    response = gemini.generate(
        "You are a helpful assistant.",
        "Say hello in one sentence."
    )

    print("✅ Gemini Working")
    print(response)


def test_places():
    print("\n===== Testing Geoapify =====")

    places = PlacesService()

    result = places.get_attractions(DESTINATION)

    print("✅ Geoapify Working")

    print(f"Latitude : {result['latitude']}")
    print(f"Longitude: {result['longitude']}")

    print(f"Attractions Found: {len(result['attractions'])}")

    if result["attractions"]:
        print("\nFirst Attraction:")
        print(result["attractions"][0])

    return result


def test_weather(latitude: float, longitude: float):
    print("\n===== Testing Open-Meteo =====")

    weather = WeatherService()

    forecast = weather.get_forecast(
        latitude=latitude,
        longitude=longitude,
    )

    print("✅ Open-Meteo Forecast Working")

    print(forecast.keys())

    historical = weather.get_historical_weather(
        latitude=latitude,
        longitude=longitude,
        start_date="2024-07-01",
        end_date="2024-07-07",
    )

    print("✅ Open-Meteo Historical Working")

    print(historical.keys())


def test_routing():
    print("\n===== Testing OpenRouteService =====")

    routing = RoutingService()

    route = routing.get_route(
        [
            [2.2945, 48.8584],   # Eiffel Tower
            [2.3376, 48.8606],   # Louvre Museum
        ]
    )

    print("✅ OpenRouteService Working")

    print(route.keys())


if __name__ == "__main__":

    test_gemini()

    place_data = test_places()

    test_weather(
        latitude=place_data["latitude"],
        longitude=place_data["longitude"],
    )

    test_routing()

    print("\n==============================")
    print("✅ ALL SERVICES ARE WORKING")
    print("==============================")