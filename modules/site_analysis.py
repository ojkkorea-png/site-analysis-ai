from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from modules.environment_analysis import ClimateSummary, SunAnalysis


@dataclass
class SiteAnalysis:
    site_name: str
    lat: float
    lon: float
    radius: int
    address_text: str
    region_text: str
    place_counts: dict[str, int]
    nearest_places: list[dict[str, Any]]
    population_summary: dict[str, Any] | None
    spatial_layer_counts: dict[str, int | str]
    sun_analysis: SunAnalysis | None
    climate_summary: ClimateSummary | None
    insights: list[str]
    design_keywords: list[str]
    opportunities: list[str]
    cautions: list[str]


def extract_address_text(address_response: dict[str, Any] | None) -> str:
    if not address_response:
        return "주소 정보를 불러오지 못했습니다."
    documents = address_response.get("documents") or []
    if not documents:
        return "주소 정보 없음"
    first = documents[0]
    road = first.get("road_address") or {}
    jibun = first.get("address") or {}
    return road.get("address_name") or jibun.get("address_name") or "주소 정보 없음"


def extract_region_text(region_response: dict[str, Any] | None) -> str:
    if not region_response:
        return "행정구역 정보를 불러오지 못했습니다."
    documents = region_response.get("documents") or []
    if not documents:
        return "행정구역 정보 없음"
    legal = next((item for item in documents if item.get("region_type") == "B"), documents[0])
    return " ".join(
        part
        for part in [
            legal.get("region_1depth_name"),
            legal.get("region_2depth_name"),
            legal.get("region_3depth_name"),
        ]
        if part
    )


def summarize_places(places: list[dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts = Counter(row.get("analysis_category", "기타") for row in places)
    nearest = sorted(places, key=lambda row: int(row.get("distance") or 999999))[:10]
    return dict(counts), nearest


def extract_population_record(population_response: dict[str, Any] | None) -> dict[str, Any] | None:
    if not population_response:
        return None
    result = population_response.get("result")
    if isinstance(result, list) and result:
        return result[0]
    if isinstance(result, dict):
        records = result.get("resultdata") or result.get("data")
        if isinstance(records, list) and records:
            return records[0]
        return result
    return None


def count_vworld_features(vworld_response: dict[str, Any] | None) -> int | str:
    if not vworld_response:
        return "조회 실패"
    response = vworld_response.get("response") or {}
    record = response.get("record") or {}
    total = record.get("total")
    if total is not None:
        try:
            return int(total)
        except (TypeError, ValueError):
            return str(total)
    features = (((response.get("result") or {}).get("featureCollection") or {}).get("features") or [])
    return len(features)


def build_rule_based_insights(
    place_counts: dict[str, int],
    population: dict[str, Any] | None,
    spatial_layer_counts: dict[str, int | str],
    sun_analysis: SunAnalysis | None,
    climate_summary: ClimateSummary | None,
) -> tuple[list[str], list[str], list[str], list[str]]:
    insights: list[str] = []
    opportunities: list[str] = []
    cautions: list[str] = []
    keywords: list[str] = []

    transit_count = place_counts.get("대중교통", 0)
    cafe_count = place_counts.get("카페", 0)
    food_count = place_counts.get("음식점", 0)
    culture_count = place_counts.get("문화시설", 0)
    school_count = place_counts.get("학교", 0)

    if transit_count >= 5:
        insights.append("반경 내 대중교통 접근점이 많아 방문형 프로그램에 유리합니다.")
        opportunities.append("입구, 대기, 픽업, 빠른 회전 동선을 명확하게 계획할 수 있습니다.")
        keywords.extend(["접근성", "유입", "도시 동선"])
    elif transit_count:
        insights.append("대중교통 접근은 가능하지만 도보 접근 동선의 품질 검토가 필요합니다.")
        cautions.append("가장 가까운 정류장/역에서 대지까지의 보행 경험을 별도로 확인하세요.")
        keywords.append("보행 연결")
    else:
        cautions.append("반경 내 대중교통 검색 결과가 적어 목적 방문형 공간 전략이 필요합니다.")

    if cafe_count + food_count >= 12:
        insights.append("식음 상권 밀도가 높아 체류와 소비 활동이 이미 형성된 지역입니다.")
        opportunities.append("기존 상권과 차별화되는 정체성, 야간 조명, 파사드 전략이 중요합니다.")
        keywords.extend(["상권 밀도", "체류", "파사드"])
    elif cafe_count + food_count >= 4:
        insights.append("주변에 생활 편의형 식음 시설이 분포해 일상 방문 수요를 기대할 수 있습니다.")
        keywords.append("생활권")

    if culture_count:
        insights.append("문화시설이 가까워 전시, 커뮤니티, 브랜드 경험형 프로그램과 연결하기 좋습니다.")
        opportunities.append("전시 벽, 가변 가구, 이벤트 동선처럼 프로그램 전환이 쉬운 실내 구성이 어울립니다.")
        keywords.extend(["문화 연계", "가변성"])

    if school_count:
        insights.append("학교가 주변에 있어 학생·교직원 등 반복 방문층을 고려할 수 있습니다.")
        opportunities.append("짧은 체류, 합리적 가격, 스터디/휴식 기능을 프로그램에 반영할 수 있습니다.")
        keywords.extend(["청년층", "반복 방문"])

    if population:
        twenties = _as_float(population.get("twenty_per"))
        thirties = _as_float(population.get("thirty_per"))
        seniors = _as_float(population.get("sixty_per")) + _as_float(population.get("seventy_more_than_per"))
        if twenties + thirties >= 30:
            insights.append("20-30대 비율이 높아 트렌드 반응성이 좋은 프로그램을 검토할 수 있습니다.")
            keywords.extend(["젊은 이용자", "트렌드"])
        if seniors >= 25:
            cautions.append("고령층 비율이 높은 편이라 접근성, 휴식 지점, 명료한 안내 체계가 중요합니다.")
            keywords.extend(["무장애", "명료한 동선"])

    parcel_count = spatial_layer_counts.get("연속지적도")
    if isinstance(parcel_count, int) and parcel_count > 30:
        insights.append("작은 필지가 조밀한 맥락일 가능성이 있어 가로 스케일과 입면 리듬을 세밀하게 봐야 합니다.")
        cautions.append("필지 경계, 인접 건물 간격, 후면 서비스 동선을 도면에서 재확인하세요.")

    if sun_analysis:
        insights.extend(sun_analysis.insights)
        opportunities.append("남향 채광을 주요 체류 공간에 연결하고, 동서향 창은 시간대별 눈부심 제어 전략을 세우세요.")
        keywords.extend(["일조", "채광", "차양"])

    if climate_summary:
        insights.extend(climate_summary.insights)
        opportunities.append("계절별 온열 쾌적성 차이를 공간 프로그램, 재료, 외피 계획과 연결해 설명할 수 있습니다.")
        keywords.extend(["기후 반응", "열쾌적성", "자연환기"])

    if not insights:
        insights.append("현재 수집된 데이터가 제한적이므로 현장 답사와 수동 리서치를 병행해야 합니다.")
    if not opportunities:
        opportunities.append("주변시설 분포를 기준으로 주 이용자와 운영 시간대를 먼저 가정해보세요.")
    if not cautions:
        cautions.append("API 데이터는 실제 현장 상황과 차이가 있을 수 있으므로 답사 사진으로 검증하세요.")

    keywords = list(dict.fromkeys(keywords or ["맥락 분석", "사용자 경험", "공간 전략"]))
    return insights, keywords[:10], opportunities, cautions


def create_site_analysis(
    *,
    site_name: str,
    lat: float,
    lon: float,
    radius: int,
    address_response: dict[str, Any] | None,
    region_response: dict[str, Any] | None,
    places: list[dict[str, Any]],
    population_response: dict[str, Any] | None,
    vworld_responses: dict[str, dict[str, Any] | None],
    sun_analysis: SunAnalysis | None,
    climate_summary: ClimateSummary | None,
) -> SiteAnalysis:
    place_counts, nearest_places = summarize_places(places)
    population = extract_population_record(population_response)
    spatial_layer_counts = {
        label: count_vworld_features(response)
        for label, response in vworld_responses.items()
    }
    insights, keywords, opportunities, cautions = build_rule_based_insights(
        place_counts,
        population,
        spatial_layer_counts,
        sun_analysis,
        climate_summary,
    )
    return SiteAnalysis(
        site_name=site_name,
        lat=lat,
        lon=lon,
        radius=radius,
        address_text=extract_address_text(address_response),
        region_text=extract_region_text(region_response),
        place_counts=place_counts,
        nearest_places=nearest_places,
        population_summary=population,
        spatial_layer_counts=spatial_layer_counts,
        sun_analysis=sun_analysis,
        climate_summary=climate_summary,
        insights=insights,
        design_keywords=keywords,
        opportunities=opportunities,
        cautions=cautions,
    )


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
