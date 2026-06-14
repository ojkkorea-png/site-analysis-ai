from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import acos, asin, atan2, cos, degrees, radians, sin, tan
from statistics import mean
from typing import Any


@dataclass
class SunSample:
    label: str
    date_label: str
    time_label: str
    altitude: float
    azimuth: float


@dataclass
class SunAnalysis:
    samples: list[SunSample]
    daylight_hours: dict[str, float]
    insights: list[str]


@dataclass
class ClimateSummary:
    source_period: str
    mean_temp: float | None
    summer_mean_max_temp: float | None
    winter_mean_min_temp: float | None
    annual_precipitation: float | None
    annual_sunshine_hours: float | None
    mean_wind_speed: float | None
    dominant_wind_direction: float | None
    insights: list[str]


def analyze_sun(lat: float, lon: float) -> SunAnalysis:
    del lon
    checkpoints = [
        ("춘분", date(2026, 3, 20)),
        ("하지", date(2026, 6, 21)),
        ("추분", date(2026, 9, 22)),
        ("동지", date(2026, 12, 21)),
    ]
    samples: list[SunSample] = []
    daylight_hours: dict[str, float] = {}
    for label, day in checkpoints:
        declination = _solar_declination(day)
        daylight_hours[label] = _daylight_hours(lat, declination)
        for hour in [9, 12, 15]:
            altitude, azimuth = _solar_position(lat, declination, hour)
            samples.append(
                SunSample(
                    label=label,
                    date_label=day.isoformat(),
                    time_label=f"{hour:02d}:00",
                    altitude=round(altitude, 1),
                    azimuth=round(azimuth, 1),
                )
            )

    winter_noon = next(sample.altitude for sample in samples if sample.label == "동지" and sample.time_label == "12:00")
    summer_noon = next(sample.altitude for sample in samples if sample.label == "하지" and sample.time_label == "12:00")
    insights = [
        f"동지 정오 태양고도는 약 {winter_noon:.1f}도로 낮아 남측 채광 확보와 인접 건물 음영 검토가 중요합니다.",
        f"하지 정오 태양고도는 약 {summer_noon:.1f}도로 높아 수평 차양, 깊은 창호, 내부 눈부심 제어가 필요합니다.",
        "오전은 동측, 오후는 서측 일사가 강하므로 프로그램 배치와 차양 방향을 시간대별로 나누어 검토하세요.",
    ]
    return SunAnalysis(samples=samples, daylight_hours={k: round(v, 1) for k, v in daylight_hours.items()}, insights=insights)


def summarize_climate(history_response: dict[str, Any] | None, source_period: str) -> ClimateSummary | None:
    if not history_response:
        return None
    daily = history_response.get("daily") or {}
    dates = daily.get("time") or []
    if not dates:
        return None

    mean_temp = _safe_mean(daily.get("temperature_2m_mean"))
    annual_precipitation = _safe_sum(daily.get("precipitation_sum"))
    annual_sunshine_hours = _safe_sum(daily.get("sunshine_duration"), scale=3600)
    mean_wind_speed = _safe_mean(daily.get("wind_speed_10m_mean"))
    dominant_wind_direction = _circular_mean(daily.get("wind_direction_10m_dominant"))

    summer_indices = [idx for idx, value in enumerate(dates) if value[5:7] in {"06", "07", "08"}]
    winter_indices = [idx for idx, value in enumerate(dates) if value[5:7] in {"01", "02", "12"}]
    summer_mean_max_temp = _safe_mean(_pick(daily.get("temperature_2m_max"), summer_indices))
    winter_mean_min_temp = _safe_mean(_pick(daily.get("temperature_2m_min"), winter_indices))

    insights = build_climate_insights(
        mean_temp=mean_temp,
        summer_mean_max_temp=summer_mean_max_temp,
        winter_mean_min_temp=winter_mean_min_temp,
        annual_precipitation=annual_precipitation,
        annual_sunshine_hours=annual_sunshine_hours,
        mean_wind_speed=mean_wind_speed,
        dominant_wind_direction=dominant_wind_direction,
    )
    return ClimateSummary(
        source_period=source_period,
        mean_temp=_round_or_none(mean_temp),
        summer_mean_max_temp=_round_or_none(summer_mean_max_temp),
        winter_mean_min_temp=_round_or_none(winter_mean_min_temp),
        annual_precipitation=_round_or_none(annual_precipitation),
        annual_sunshine_hours=_round_or_none(annual_sunshine_hours),
        mean_wind_speed=_round_or_none(mean_wind_speed),
        dominant_wind_direction=_round_or_none(dominant_wind_direction),
        insights=insights,
    )


def build_climate_insights(
    *,
    mean_temp: float | None,
    summer_mean_max_temp: float | None,
    winter_mean_min_temp: float | None,
    annual_precipitation: float | None,
    annual_sunshine_hours: float | None,
    mean_wind_speed: float | None,
    dominant_wind_direction: float | None,
) -> list[str]:
    insights: list[str] = []
    if summer_mean_max_temp is not None and summer_mean_max_temp >= 28:
        insights.append("여름철 최고기온 평균이 높아 차양, 통풍, 냉방 부하 저감 전략이 중요합니다.")
    if winter_mean_min_temp is not None and winter_mean_min_temp <= 0:
        insights.append("겨울철 최저기온 평균이 낮아 출입구 방풍, 외피 단열, 대기 공간의 열쾌적성을 고려해야 합니다.")
    if annual_precipitation is not None and annual_precipitation >= 1200:
        insights.append("연간 강수량이 많은 편이므로 우천 동선, 진입부 캐노피, 바닥 미끄럼 방지 계획이 필요합니다.")
    if annual_sunshine_hours is not None and annual_sunshine_hours >= 2200:
        insights.append("연간 일조 시간이 풍부해 자연채광 활용 가능성이 높지만 눈부심과 과열을 함께 제어해야 합니다.")
    if mean_wind_speed is not None and mean_wind_speed >= 3:
        insights.append("평균 풍속이 비교적 높아 외부 대기공간, 출입구, 테라스의 방풍 계획을 검토하세요.")
    if dominant_wind_direction is not None:
        insights.append(f"우세풍 방향은 약 {dominant_wind_direction:.0f}도 기준으로 나타나며, 환기와 냄새/소음 확산 방향 검토에 활용할 수 있습니다.")
    if mean_temp is not None:
        insights.append(f"연평균 기온은 약 {mean_temp:.1f}도로, 계절별 실내 쾌적성 전략을 함께 제시하기 좋습니다.")
    return insights or ["기후 데이터가 제한적이므로 현장 답사 시 바람, 습도, 그늘, 표면 온도를 추가로 관찰하세요."]


def _solar_declination(day: date) -> float:
    day_of_year = day.timetuple().tm_yday
    return 23.44 * sin(radians((360 / 365) * (day_of_year - 81)))


def _solar_position(lat: float, declination: float, hour: int) -> tuple[float, float]:
    lat_rad = radians(lat)
    dec_rad = radians(declination)
    hour_angle = radians(15 * (hour - 12))
    altitude_rad = asin(sin(lat_rad) * sin(dec_rad) + cos(lat_rad) * cos(dec_rad) * cos(hour_angle))
    azimuth_rad = atan2(
        sin(hour_angle),
        cos(hour_angle) * sin(lat_rad) - tan(dec_rad) * cos(lat_rad),
    )
    azimuth_from_south = degrees(azimuth_rad)
    azimuth_from_north = (azimuth_from_south + 180) % 360
    return degrees(altitude_rad), azimuth_from_north


def _daylight_hours(lat: float, declination: float) -> float:
    lat_rad = radians(lat)
    dec_rad = radians(declination)
    value = -tan(lat_rad) * tan(dec_rad)
    value = max(-1, min(1, value))
    return (2 / 15) * degrees(acos(value))


def _safe_mean(values: list[float | int | None] | None) -> float | None:
    clean = [float(value) for value in values or [] if value is not None]
    return mean(clean) if clean else None


def _safe_sum(values: list[float | int | None] | None, scale: float = 1) -> float | None:
    clean = [float(value) for value in values or [] if value is not None]
    return sum(clean) / scale if clean else None


def _pick(values: list[Any] | None, indices: list[int]) -> list[Any]:
    if not values:
        return []
    return [values[idx] for idx in indices if idx < len(values)]


def _circular_mean(values: list[float | int | None] | None) -> float | None:
    clean = [radians(float(value)) for value in values or [] if value is not None]
    if not clean:
        return None
    sin_mean = mean(sin(value) for value in clean)
    cos_mean = mean(cos(value) for value in clean)
    return (degrees(atan2(sin_mean, cos_mean)) + 360) % 360


def _round_or_none(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None
