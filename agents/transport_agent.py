"""
Transport Agent.

Workflow:

TripState
      ↓
RoutingService (city order + intra-city)
      ↓
RoutePlan
      ↓
TripState
"""

from __future__ import annotations

from typing import Optional

from models.trip_state import TripState
from models.route_plan import CityRoute, RoutePlan
from services.routing_service import RoutingService


class TransportAgent:

    def __init__(
        self,
        routing_service: Optional[
            RoutingService
        ] = None,
    ):

        self._routing = (
            routing_service
            or RoutingService()
        )

    def run(
        self,
        state: TripState,
    ) -> TripState:

        experience = state.recommended_experiences

        if (
            experience is None
            or len(experience.attractions) < 2
        ):
            return state

        cities = experience.cities or []

        if len(cities) > 1:
            route = self._build_multi_city_route(
                experience.attractions, cities
            )
        else:
            route = self._build_single_city_route(
                experience.attractions, cities[0] if cities else ""
            )

        route.recommended_transport = self._recommend_transport(
            total_distance_km=route.total_distance_km,
            num_travelers=state.number_of_travelers,
        )

        state.optimized_route = route

        state.decision_log.append(
            "Transport: Route optimized."
        )

        return state

    # --------------------------------------------------------- #
    # Single City Route
    # --------------------------------------------------------- #

    def _build_single_city_route(
        self,
        attractions: list,
        city: str,
    ) -> RoutePlan:
        """Build route for a single city."""

        coordinates = [
            [a.longitude, a.latitude]
            for a in attractions
        ]

        raw_route = self._routing.optimize_route(coordinates)

        ordered_names = [
            attractions[i].name
            for i in raw_route["optimized_order"]
        ]

        return RoutePlan(
            total_distance_km=raw_route["total_distance_km"],
            total_duration_minutes=raw_route["total_duration_minutes"],
            recommended_transport="car",
            optimized_order=ordered_names,
            city_order=[city],
            city_routes=[
                CityRoute(
                    city=city,
                    attraction_order=ordered_names,
                    distance_km=raw_route["total_distance_km"],
                    duration_minutes=raw_route["total_duration_minutes"],
                )
            ],
            notes="Generated using OpenRouteService.",
        )

    # --------------------------------------------------------- #
    # Multi City Route
    # --------------------------------------------------------- #

    def _build_multi_city_route(
        self,
        attractions: list,
        cities: list[str],
    ) -> RoutePlan:
        """Build route for multiple cities."""

        city_groups: dict[str, list] = {}
        for a in attractions:
            city = a.city or cities[0] if cities else "Unknown"
            city_groups.setdefault(city, []).append(a)

        city_order = self._optimize_city_order(city_groups)

        total_distance = 0.0
        total_duration = 0
        all_ordered_names: list[str] = []
        city_routes: list[CityRoute] = []

        for city in city_order:
            group = city_groups.get(city, [])
            if not group:
                continue

            coordinates = [
                [a.longitude, a.latitude] for a in group
            ]

            if len(coordinates) >= 2:
                raw_route = self._routing.optimize_route(coordinates)
                ordered_names = [
                    group[i].name
                    for i in raw_route["optimized_order"]
                ]
                distance = raw_route["total_distance_km"]
                duration = raw_route["total_duration_minutes"]
            else:
                ordered_names = [group[0].name]
                distance = 0.0
                duration = 0

            total_distance += distance
            total_duration += duration
            all_ordered_names.extend(ordered_names)

            city_routes.append(
                CityRoute(
                    city=city,
                    attraction_order=ordered_names,
                    distance_km=distance,
                    duration_minutes=duration,
                )
            )

        return RoutePlan(
            total_distance_km=round(total_distance, 2),
            total_duration_minutes=round(total_duration),
            recommended_transport="car",
            optimized_order=all_ordered_names,
            city_order=city_order,
            city_routes=city_routes,
            notes="Generated using OpenRouteService.",
        )

    # --------------------------------------------------------- #
    # City Order Optimization
    # --------------------------------------------------------- #

    def _optimize_city_order(
        self,
        city_groups: dict[str, list],
    ) -> list[str]:
        """
        Optimize the order of cities using nearest-neighbor
        heuristic based on city center coordinates.
        """

        from services.places_service import PlacesService

        places = PlacesService()

        city_coords: dict[str, tuple[float, float]] = {}

        for city in city_groups:
            try:
                place_data = places.get_attractions(city)
                city_coords[city] = (
                    place_data["latitude"],
                    place_data["longitude"],
                )
            except Exception:
                city_coords[city] = (0.0, 0.0)

        if len(city_coords) <= 2:
            return list(city_coords.keys())

        remaining = set(city_coords.keys())
        ordered: list[str] = []

        current = next(iter(remaining))
        ordered.append(current)
        remaining.remove(current)

        while remaining:
            lat1, lon1 = city_coords[current]
            nearest = None
            nearest_dist = float("inf")

            for city in remaining:
                lat2, lon2 = city_coords[city]
                dist = (lat2 - lat1) ** 2 + (lon2 - lon1) ** 2
                if dist < nearest_dist:
                    nearest_dist = dist
                    nearest = city

            if nearest is None:
                break

            ordered.append(nearest)
            remaining.remove(nearest)
            current = nearest

        return ordered

    # --------------------------------------------------------- #
    # Transport Recommendation
    # --------------------------------------------------------- #

    @staticmethod
    def _recommend_transport(
        total_distance_km: float,
        num_travelers: int | None,
    ) -> str:
        """
        Recommend transport mode based on distance
        and number of travelers.
        """

        travelers = num_travelers or 1

        if travelers >= 7:
            return "minivan"

        if travelers >= 3:
            if total_distance_km <= 5:
                return "car"
            return "suv"

        if total_distance_km <= 2:
            return "walking"

        if total_distance_km <= 15:
            return "bike"

        return "car"
