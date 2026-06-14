from math import cos, radians


def bbox_from_radius(lon: float, lat: float, radius_m: int) -> tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320
    lon_delta = radius_m / (111_320 * max(cos(radians(lat)), 0.01))
    return lon - lon_delta, lat - lat_delta, lon + lon_delta, lat + lat_delta


def sgis_adm_cd_from_findcode(result: dict) -> str | None:
    payload = result.get("result") or {}
    sido = payload.get("sido_cd")
    sgg = payload.get("sgg_cd")
    emdong = payload.get("emdong_cd")
    if sido and sgg and emdong:
        return f"{sido}{sgg}{emdong}"
    if sido and sgg:
        return f"{sido}{sgg}"
    return None
