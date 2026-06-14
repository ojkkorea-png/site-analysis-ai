import os
from math import asin, cos, radians, sin, sqrt
from typing import Any
from urllib.parse import urlparse

import requests


class ApiError(RuntimeError):
    pass


def _get_json(url: str, *, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
    request_headers = {"User-Agent": "site-analysis-assistant/1.0"}
    if headers:
        request_headers.update(headers)
    try:
        response = requests.get(url, headers=request_headers, params=params, timeout=15)
    except requests.RequestException as exc:
        raise ApiError(f"Request failed: {exc}") from exc
    if not response.ok:
        raise ApiError(f"{response.status_code} {response.reason}: {response.text[:300]}")
    return response.json()


class KakaoLocalClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("KAKAO_REST_API_KEY")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ApiError("KAKAO_REST_API_KEY is missing.")
        return {"Authorization": f"KakaoAK {self.api_key}"}

    def coord_to_address(self, lon: float, lat: float) -> dict[str, Any]:
        return _get_json(
            "https://dapi.kakao.com/v2/local/geo/coord2address.json",
            headers=self._headers(),
            params={"x": lon, "y": lat, "input_coord": "WGS84"},
        )

    def coord_to_region(self, lon: float, lat: float) -> dict[str, Any]:
        return _get_json(
            "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json",
            headers=self._headers(),
            params={"x": lon, "y": lat, "input_coord": "WGS84"},
        )

    def category_search(self, lon: float, lat: float, category_code: str, radius: int = 500, size: int = 15) -> dict[str, Any]:
        return _get_json(
            "https://dapi.kakao.com/v2/local/search/category.json",
            headers=self._headers(),
            params={
                "x": lon,
                "y": lat,
                "category_group_code": category_code,
                "radius": radius,
                "size": min(size, 15),
                "sort": "distance",
            },
        )


class VWorldDataClient:
    PLACE_KEYWORDS = {
        "대중교통": ["지하철역", "버스정류장"],
        "음식점": ["음식점", "식당"],
        "카페": ["카페"],
        "문화시설": ["문화시설", "도서관", "박물관", "공연장"],
        "관광명소": ["관광명소", "문화재"],
        "학교": ["학교"],
        "편의점": ["편의점"],
        "병원": ["병원", "의원"],
    }

    def __init__(self, api_key: str | None = None, domain: str | None = None) -> None:
        self.api_key = api_key or os.getenv("VWORLD_API_KEY")
        self.domain = domain or os.getenv("VWORLD_DOMAIN") or self._default_domain()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def get_features(self, data_id: str, bbox: tuple[float, float, float, float], size: int = 100) -> dict[str, Any]:
        if not self.api_key:
            raise ApiError("VWORLD_API_KEY is missing.")
        min_lon, min_lat, max_lon, max_lat = bbox
        errors = []
        for domain in self._domain_candidates():
            data = _get_json(
                "https://api.vworld.kr/req/data",
                params={
                    "service": "data",
                    "version": "2.0",
                    "request": "GetFeature",
                    "key": self.api_key,
                    "domain": domain,
                    "format": "json",
                    "data": data_id,
                    "geomFilter": f"BOX({min_lon},{min_lat},{max_lon},{max_lat})",
                    "crs": "EPSG:4326",
                    "size": size,
                },
            )
            response = data.get("response") or {}
            if response.get("status") != "ERROR":
                self.domain = domain
                return data
            error = response.get("error") or {}
            errors.append(f"{domain}: {error.get('code', 'ERROR')} - {error.get('text', response)}")
            if error.get("code") != "INCORRECT_KEY":
                break
        raise ApiError("VWorld data API failed. " + " | ".join(errors))

    def _domain_candidates(self) -> list[str]:
        raw_candidates = [
            self.domain,
            os.getenv("VWORLD_DOMAIN"),
            os.getenv("RENDER_EXTERNAL_URL"),
            _hostname_to_url(os.getenv("RENDER_EXTERNAL_HOSTNAME")),
            _service_to_render_url(os.getenv("RENDER_SERVICE_NAME")),
            "https://site-analysis-ai.onrender.com",
            "http://localhost:8501",
            "http://127.0.0.1:8501",
        ]
        candidates = []
        seen = set()
        for raw in raw_candidates:
            normalized = _normalize_domain(raw)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(normalized)
        return candidates

    def _default_domain(self) -> str:
        return (
            _normalize_domain(os.getenv("RENDER_EXTERNAL_URL"))
            or _hostname_to_url(os.getenv("RENDER_EXTERNAL_HOSTNAME"))
            or _service_to_render_url(os.getenv("RENDER_SERVICE_NAME"))
            or "http://localhost:8501"
        )

    def coord_to_address_and_region(self, lon: float, lat: float) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.api_key:
            raise ApiError("VWORLD_API_KEY is missing.")
        errors = []
        data = None
        for domain in self._domain_candidates():
            data = _get_json(
                "https://api.vworld.kr/req/address",
                params={
                    "service": "address",
                    "request": "getAddress",
                    "version": "2.0",
                    "key": self.api_key,
                    "domain": domain,
                    "format": "json",
                    "crs": "epsg:4326",
                    "point": f"{lon},{lat}",
                    "type": "both",
                },
            )
            response = data.get("response") or {}
            if response.get("status") == "OK":
                self.domain = domain
                break
            error = response.get("error") or response
            errors.append(f"{domain}: {error}")
            code = error.get("code") if isinstance(error, dict) else None
            if code != "INCORRECT_KEY":
                break
        else:
            response = {}

        response = (data or {}).get("response") or {}
        if response.get("status") != "OK":
            raise ApiError("VWorld reverse geocode failed. " + " | ".join(errors))

        results = response.get("result") or []
        road = next((item for item in results if item.get("type") == "road"), None)
        parcel = next((item for item in results if item.get("type") == "parcel"), None)
        primary = road or parcel or (results[0] if results else {})
        structure = primary.get("structure") or {}
        address_name = primary.get("text") or ""

        address_response = {
            "documents": [
                {
                    "address_name": address_name,
                    "address": {
                        "address_name": (parcel or primary).get("text") or address_name,
                        "region_1depth_name": structure.get("level1"),
                        "region_2depth_name": structure.get("level2"),
                        "region_3depth_name": structure.get("level4L") or structure.get("level4A") or structure.get("level3"),
                    },
                    "road_address": {
                        "address_name": (road or primary).get("text") or address_name,
                        "region_1depth_name": structure.get("level1"),
                        "region_2depth_name": structure.get("level2"),
                        "region_3depth_name": structure.get("level4L") or structure.get("level4A") or structure.get("level3"),
                    },
                }
            ]
        }
        region_response = {
            "documents": [
                {
                    "region_type": "B",
                    "region_1depth_name": structure.get("level1"),
                    "region_2depth_name": structure.get("level2"),
                    "region_3depth_name": structure.get("level4L") or structure.get("level4A") or structure.get("level3"),
                }
            ]
        }
        return address_response, region_response

    def place_search(self, lon: float, lat: float, category_label: str, radius: int = 500, size: int = 15) -> dict[str, Any]:
        if not self.api_key:
            raise ApiError("VWORLD_API_KEY is missing.")
        min_lon, min_lat, max_lon, max_lat = _bbox_from_radius(lon, lat, radius)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        errors = []
        for keyword in self.PLACE_KEYWORDS.get(category_label, [category_label]):
            data = None
            for domain in self._domain_candidates():
                data = _get_json(
                    "https://api.vworld.kr/req/search",
                    params={
                        "service": "search",
                        "request": "search",
                        "version": "2.0",
                        "crs": "EPSG:4326",
                        "bbox": f"{min_lon},{min_lat},{max_lon},{max_lat}",
                        "size": min(size, 10),
                        "page": 1,
                        "query": keyword,
                        "type": "place",
                        "format": "json",
                        "key": self.api_key,
                        "domain": domain,
                    },
                )
                response = data.get("response") or {}
                if response.get("status") != "ERROR":
                    self.domain = domain
                    break
                error = response.get("error") or {}
                errors.append(f"{keyword}/{domain}: {error.get('code', 'ERROR')} - {error.get('text', response)}")
                if error.get("code") != "INCORRECT_KEY":
                    break
            if data is None:
                continue
            response = data.get("response") or {}
            if response.get("status") == "ERROR":
                continue
            items = (((data.get("response") or {}).get("result") or {}).get("items") or [])
            for item in items:
                item_id = str(item.get("id") or item.get("title") or item)
                if item_id in seen:
                    continue
                seen.add(item_id)
                point = item.get("point") or {}
                item_lon = point.get("x")
                item_lat = point.get("y")
                if item_lon is None or item_lat is None:
                    continue
                address = item.get("address") or {}
                rows.append(
                    {
                        "analysis_category": category_label,
                        "place_name": _strip_tags(str(item.get("title") or keyword)),
                        "distance": str(int(_haversine_m(lat, lon, float(item_lat), float(item_lon)))),
                        "road_address_name": address.get("road") or address.get("parcel") or "",
                        "address_name": address.get("parcel") or address.get("road") or "",
                        "category_name": f"브이월드 검색 > {keyword}",
                        "x": str(item_lon),
                        "y": str(item_lat),
                        "place_url": "",
                    }
                )
                if len(rows) >= size:
                    break
            if len(rows) >= size:
                break
        if not rows and errors:
            raise ApiError("VWorld place search failed. " + " | ".join(errors[:4]))
        rows.sort(key=lambda row: int(row["distance"]))
        return {"documents": rows[:size]}


class OpenStreetMapClient:
    CATEGORY_FILTERS = {
        "대중교통": ['nwr["public_transport"~"station|stop_position|platform"]', 'nwr["highway"="bus_stop"]', 'nwr["railway"="station"]', 'nwr["station"="subway"]'],
        "음식점": ['nwr["amenity"~"restaurant|fast_food|food_court"]'],
        "카페": ['nwr["amenity"="cafe"]'],
        "문화시설": ['nwr["amenity"~"arts_centre|theatre|cinema|library"]', 'nwr["tourism"="museum"]'],
        "관광명소": ['nwr["tourism"~"attraction|gallery|viewpoint"]', 'nwr["historic"]'],
        "학교": ['nwr["amenity"~"school|university|college"]'],
        "편의점": ['nwr["shop"="convenience"]'],
        "병원": ['nwr["amenity"~"hospital|clinic|doctors"]'],
    }

    @property
    def enabled(self) -> bool:
        return True

    def reverse_geocode(self, lon: float, lat: float) -> tuple[dict[str, Any], dict[str, Any]]:
        data = _get_json(
            "https://nominatim.openstreetmap.org/reverse",
            headers={"User-Agent": "site-analysis-assistant/1.0"},
            params={
                "format": "jsonv2",
                "lat": lat,
                "lon": lon,
                "zoom": 18,
                "addressdetails": 1,
                "accept-language": "ko,en",
            },
        )
        address = data.get("address") or {}
        road_parts = [
            address.get("road") or address.get("pedestrian") or address.get("footway"),
            address.get("house_number"),
        ]
        region_1 = address.get("province") or address.get("city") or address.get("state")
        region_2 = address.get("borough") or address.get("county") or address.get("city_district")
        region_3 = address.get("suburb") or address.get("quarter") or address.get("neighbourhood")
        display_name = data.get("display_name") or "주소 정보 없음"
        road_name = " ".join(str(part) for part in road_parts if part) or display_name
        address_response = {
            "documents": [
                {
                    "address_name": display_name,
                    "address": {
                        "address_name": display_name,
                        "region_1depth_name": region_1,
                        "region_2depth_name": region_2,
                        "region_3depth_name": region_3,
                    },
                    "road_address": {
                        "address_name": road_name,
                        "region_1depth_name": region_1,
                        "region_2depth_name": region_2,
                        "region_3depth_name": region_3,
                    },
                }
            ]
        }
        region_response = {
            "documents": [
                {
                    "region_type": "B",
                    "region_1depth_name": region_1,
                    "region_2depth_name": region_2,
                    "region_3depth_name": region_3,
                }
            ]
        }
        return address_response, region_response

    def category_search(self, lon: float, lat: float, category_label: str, radius: int = 500, size: int = 15) -> dict[str, Any]:
        filters = self.CATEGORY_FILTERS.get(category_label)
        if not filters:
            return {"documents": []}
        body = "\n".join(f"{filter_expr}(around:{radius},{lat},{lon});" for filter_expr in filters)
        query = f"[out:json][timeout:12];({body});out tags center {size};"
        data = _get_json("https://overpass-api.de/api/interpreter", params={"data": query})
        rows = []
        for element in data.get("elements", []):
            tags = element.get("tags") or {}
            item_lat = element.get("lat") or (element.get("center") or {}).get("lat")
            item_lon = element.get("lon") or (element.get("center") or {}).get("lon")
            if item_lat is None or item_lon is None:
                continue
            distance = int(_haversine_m(lat, lon, float(item_lat), float(item_lon)))
            rows.append(
                {
                    "analysis_category": category_label,
                    "place_name": tags.get("name") or tags.get("name:ko") or f"이름 없는 {category_label}",
                    "distance": str(distance),
                    "road_address_name": _format_osm_address(tags),
                    "address_name": _format_osm_address(tags),
                    "category_name": f"OpenStreetMap > {category_label}",
                    "x": str(item_lon),
                    "y": str(item_lat),
                    "place_url": f"https://www.openstreetmap.org/{element.get('type', 'node')}/{element.get('id')}",
                }
            )
        rows.sort(key=lambda row: int(row["distance"]))
        return {"documents": rows[:size]}


class SgisClient:
    def __init__(self, consumer_key: str | None = None, consumer_secret: str | None = None) -> None:
        self.consumer_key = consumer_key or os.getenv("SGIS_CONSUMER_KEY")
        self.consumer_secret = consumer_secret or os.getenv("SGIS_CONSUMER_SECRET")
        self._access_token: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.consumer_key and self.consumer_secret)

    def access_token(self) -> str:
        if self._access_token:
            return self._access_token
        if not self.enabled:
            raise ApiError("SGIS_CONSUMER_KEY or SGIS_CONSUMER_SECRET is missing.")
        data = _get_json(
            "https://sgisapi.kostat.go.kr/OpenAPI3/auth/authentication.json",
            params={"consumer_key": self.consumer_key, "consumer_secret": self.consumer_secret},
        )
        result = data.get("result") or {}
        access_token = result.get("accessToken")
        if not access_token:
            raise ApiError(f"SGIS authentication failed: {data}")
        self._access_token = access_token
        return self._access_token

    def transform_wgs84_to_utm_k(self, lon: float, lat: float) -> tuple[str, str]:
        data = _get_json(
            "https://sgisapi.kostat.go.kr/OpenAPI3/transformation/transcoord.json",
            params={
                "accessToken": self.access_token(),
                "src": "EPSG:4326",
                "dst": "EPSG:5179",
                "posX": lon,
                "posY": lat,
            },
        )
        result = data.get("result") or {}
        if "posX" not in result or "posY" not in result:
            raise ApiError(f"SGIS coordinate transform failed: {data}")
        return str(result["posX"]), str(result["posY"])

    def find_small_area_code(self, lon: float, lat: float) -> dict[str, Any]:
        x_coor, y_coor = self.transform_wgs84_to_utm_k(lon, lat)
        return _get_json(
            "https://sgisapi.kostat.go.kr/OpenAPI3/personal/findcodeinsmallarea.json",
            params={"accessToken": self.access_token(), "x_coor": x_coor, "y_coor": y_coor},
        )

    def population_summary(self, adm_cd: str) -> dict[str, Any]:
        return _get_json(
            "https://sgisapi.kostat.go.kr/OpenAPI3/startupbiz/pplsummary.json",
            params={"accessToken": self.access_token(), "adm_cd": adm_cd},
        )


class OpenMeteoClient:
    @property
    def enabled(self) -> bool:
        return True

    def daily_history(self, lon: float, lat: float, start_date: str, end_date: str) -> dict[str, Any]:
        return _get_json(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": ",".join(
                    [
                        "temperature_2m_mean",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_sum",
                        "sunshine_duration",
                        "daylight_duration",
                        "shortwave_radiation_sum",
                        "wind_speed_10m_mean",
                        "wind_direction_10m_dominant",
                    ]
                ),
                "timezone": "Asia/Seoul",
                "wind_speed_unit": "ms",
            },
        )


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    value = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    return 2 * radius * asin(sqrt(value))


def _format_osm_address(tags: dict[str, Any]) -> str:
    parts = [
        tags.get("addr:city") or tags.get("addr:province"),
        tags.get("addr:district") or tags.get("addr:suburb"),
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
    ]
    return " ".join(str(part) for part in parts if part)


def _bbox_from_radius(lon: float, lat: float, radius_m: int) -> tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320
    lon_delta = radius_m / (111_320 * max(cos(radians(lat)), 0.01))
    return lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta


def _normalize_domain(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().rstrip("/")
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _hostname_to_url(value: str | None) -> str | None:
    return _normalize_domain(value)


def _service_to_render_url(value: str | None) -> str | None:
    if not value:
        return None
    return _normalize_domain(f"https://{value}.onrender.com")


def _strip_tags(value: str) -> str:
    return value.replace("<b>", "").replace("</b>", "").replace("<br>", " ")
