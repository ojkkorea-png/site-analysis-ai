from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from modules.site_analysis import SiteAnalysis


def render_html_report(analysis: SiteAnalysis) -> str:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{escape(analysis.site_name)} 대지 분석 보고서</title>
  <style>
    body {{ font-family: Arial, "Noto Sans KR", sans-serif; color: #111827; margin: 40px; line-height: 1.55; }}
    h1 {{ font-size: 28px; margin-bottom: 6px; }}
    h2 {{ font-size: 18px; border-bottom: 1px solid #d1d5db; padding-bottom: 6px; margin-top: 30px; }}
    .meta {{ color: #6b7280; margin-bottom: 28px; }}
    .grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 14px; }}
    .label {{ color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
    .value {{ font-size: 18px; font-weight: 700; margin-top: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f3f4f6; }}
    .tag {{ display: inline-block; border: 1px solid #9ca3af; border-radius: 999px; padding: 4px 9px; margin: 3px; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>{escape(analysis.site_name)} 대지 분석 보고서</h1>
  <div class="meta">생성일: {created_at} | 좌표: {analysis.lat:.7f}, {analysis.lon:.7f} | 반경: {analysis.radius}m</div>

  <div class="grid">
    <div class="card"><div class="label">주소</div><div class="value">{escape(analysis.address_text)}</div></div>
    <div class="card"><div class="label">행정구역</div><div class="value">{escape(analysis.region_text)}</div></div>
  </div>

  <h2>설계 키워드</h2>
  <p>{''.join(f'<span class="tag">{escape(keyword)}</span>' for keyword in analysis.design_keywords)}</p>

  <h2>분석 요약</h2>
  {render_list(analysis.insights)}

  <h2>일조 분석</h2>
  {render_sun_analysis(analysis)}

  <h2>기후 요약</h2>
  {render_climate_summary(analysis)}

  <h2>설계 기회 요소</h2>
  {render_list(analysis.opportunities)}

  <h2>주의 및 검증 사항</h2>
  {render_list(analysis.cautions)}

  <h2>주변 시설 분포</h2>
  {render_key_value_table(analysis.place_counts)}

  <h2>가까운 장소</h2>
  {render_places_table(analysis.nearest_places)}

  <h2>인구 요약</h2>
  {render_population_table(analysis.population_summary)}

  <h2>공간정보 레이어 조회 결과</h2>
  {render_key_value_table(analysis.spatial_layer_counts)}
</body>
</html>"""


def render_list(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def render_key_value_table(values: dict[str, Any]) -> str:
    if not values:
        return "<p>조회된 데이터가 없습니다.</p>"
    rows = "".join(
        f"<tr><td>{escape(str(key))}</td><td>{escape(str(value))}</td></tr>"
        for key, value in values.items()
    )
    return f"<table><thead><tr><th>항목</th><th>값</th></tr></thead><tbody>{rows}</tbody></table>"


def render_places_table(places: list[dict[str, Any]]) -> str:
    if not places:
        return "<p>조회된 장소가 없습니다.</p>"
    rows = ""
    for place in places:
        rows += (
            "<tr>"
            f"<td>{escape(str(place.get('analysis_category', '')))}</td>"
            f"<td>{escape(str(place.get('place_name', '')))}</td>"
            f"<td>{escape(str(place.get('distance', '')))}m</td>"
            f"<td>{escape(str(place.get('road_address_name') or place.get('address_name') or ''))}</td>"
            "</tr>"
        )
    return f"<table><thead><tr><th>분류</th><th>장소명</th><th>거리</th><th>주소</th></tr></thead><tbody>{rows}</tbody></table>"


def render_population_table(population: dict[str, Any] | None) -> str:
    if not population:
        return "<p>조회된 인구 요약이 없습니다.</p>"
    keys = [
        ("adm_nm", "행정구역"),
        ("teenage_less_than_per", "10대 미만 비율"),
        ("teenage_per", "10대 비율"),
        ("twenty_per", "20대 비율"),
        ("thirty_per", "30대 비율"),
        ("forty_per", "40대 비율"),
        ("fifty_per", "50대 비율"),
        ("sixty_per", "60대 비율"),
        ("seventy_more_than_per", "70대 이상 비율"),
    ]
    rows = "".join(
        f"<tr><td>{label}</td><td>{escape(str(population.get(key, '-')))}</td></tr>"
        for key, label in keys
    )
    return f"<table><thead><tr><th>항목</th><th>값</th></tr></thead><tbody>{rows}</tbody></table>"


def render_sun_analysis(analysis: SiteAnalysis) -> str:
    if not analysis.sun_analysis:
        return "<p>일조 분석 데이터가 없습니다.</p>"
    rows = "".join(
        "<tr>"
        f"<td>{sample.label}</td>"
        f"<td>{sample.date_label}</td>"
        f"<td>{sample.time_label}</td>"
        f"<td>{sample.altitude}°</td>"
        f"<td>{sample.azimuth}°</td>"
        "</tr>"
        for sample in analysis.sun_analysis.samples
    )
    daylight = render_key_value_table({key: f"{value}시간" for key, value in analysis.sun_analysis.daylight_hours.items()})
    table = f"<table><thead><tr><th>절기</th><th>날짜</th><th>시각</th><th>태양고도</th><th>방위각</th></tr></thead><tbody>{rows}</tbody></table>"
    return daylight + table + render_list(analysis.sun_analysis.insights)


def render_climate_summary(analysis: SiteAnalysis) -> str:
    climate = analysis.climate_summary
    if not climate:
        return "<p>기후 요약 데이터가 없습니다.</p>"
    values = {
        "자료 기간": climate.source_period,
        "연평균 기온": _unit(climate.mean_temp, "°C"),
        "여름 평균 최고기온": _unit(climate.summer_mean_max_temp, "°C"),
        "겨울 평균 최저기온": _unit(climate.winter_mean_min_temp, "°C"),
        "연간 강수량": _unit(climate.annual_precipitation, "mm"),
        "연간 일조 시간": _unit(climate.annual_sunshine_hours, "시간"),
        "평균 풍속": _unit(climate.mean_wind_speed, "m/s"),
        "우세풍 방향": _unit(climate.dominant_wind_direction, "°"),
    }
    return render_key_value_table(values) + render_list(climate.insights)


def _unit(value: float | None, unit: str) -> str:
    return "-" if value is None else f"{value}{unit}"
