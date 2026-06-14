from datetime import date, datetime
import math
import json
import os

import folium
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from streamlit_folium import st_folium

from modules.api_clients import ApiError, KakaoLocalClient, OpenMeteoClient, OpenStreetMapClient, SgisClient, VWorldDataClient
from modules.environment_analysis import analyze_sun, summarize_climate
from modules.geo_utils import bbox_from_radius, sgis_adm_cd_from_findcode
from modules.report_generator import render_html_report
from modules.site_analysis import create_site_analysis


load_dotenv()

PLACE_CATEGORIES = {
    "대중교통": "SW8",
    "음식점": "FD6",
    "카페": "CE7",
    "문화시설": "CT1",
    "관광명소": "AT4",
    "학교": "SC4",
    "편의점": "CS2",
    "병원": "HP8",
}

VWORLD_LAYERS = {
    "연속지적도": "LP_PA_CBND_BUBUN",
    "도시지역": "LT_C_UQ111",
    "관리지역": "LT_C_UQ112",
    "경관지구": "LT_C_UQ121",
    "고도지구": "LT_C_UQ123",
    "방화지구": "LT_C_UQ124",
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] .stCaption { color: #6b7280; }
        .block-container { padding-top: 2rem; }
        .site-card {
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 12px;
            background: #ffffff;
        }
        .site-card .label {
            font-size: 12px;
            color: #6b7280;
            margin-bottom: 4px;
        }
        .site-card .value {
            font-size: 18px;
            font-weight: 700;
            color: #111827;
        }
        .keyword {
            display: inline-block;
            border: 1px solid #d1d5db;
            border-radius: 999px;
            padding: 4px 10px;
            margin: 3px 4px 3px 0;
            font-size: 13px;
            background: #f9fafb;
        }
        .insight-list {
            margin: 0 0 12px 0;
            padding-left: 18px;
        }
        .insight-list li { margin-bottom: 6px; }
        .place-row {
            display: grid;
            grid-template-columns: 86px 1fr 60px;
            gap: 8px;
            align-items: start;
            border-bottom: 1px solid #e5e7eb;
            padding: 8px 0;
        }
        .place-cat {
            color: #374151;
            font-size: 12px;
            font-weight: 700;
        }
        .place-name {
            font-size: 14px;
            font-weight: 700;
            color: #111827;
        }
        .place-address {
            color: #6b7280;
            font-size: 12px;
            margin-top: 2px;
            line-height: 1.35;
        }
        .place-distance {
            text-align: right;
            color: #2563eb;
            font-size: 12px;
            font-weight: 700;
        }
        .comparison-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 10px;
            margin-top: 8px;
        }
        .comparison-card {
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 12px;
            background: #fff;
        }
        .comparison-card strong {
            display: block;
            font-size: 15px;
            margin-bottom: 6px;
        }
        .score {
            font-size: 24px;
            font-weight: 800;
            color: #2563eb;
        }
        .score-guide {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 10px;
            margin: 10px 0 16px;
        }
        .score-guide-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 11px 12px;
        }
        .score-guide-card strong {
            display: block;
            color: #0f172a;
            font-size: 14px;
            margin-bottom: 4px;
        }
        .score-guide-card span {
            display: block;
            color: #475569;
            font-size: 12px;
            line-height: 1.4;
        }
        .score-note {
            color: #64748b;
            font-size: 12px;
            line-height: 1.45;
            margin-top: 6px;
        }
        .env-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin: 8px 0 18px;
        }
        .env-card {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            background: #ffffff;
            padding: 12px;
        }
        .env-card .label {
            color: #64748b;
            font-size: 12px;
            margin-bottom: 4px;
        }
        .env-card .value {
            color: #0f172a;
            font-size: 19px;
            font-weight: 800;
        }
        .env-card .note {
            color: #64748b;
            font-size: 12px;
            margin-top: 3px;
        }
        .strategy-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
            gap: 10px;
            margin: 8px 0 14px;
        }
        .strategy-card {
            border-left: 4px solid #2563eb;
            background: #f8fafc;
            padding: 10px 12px;
            border-radius: 6px;
        }
        .strategy-card .label {
            color: #64748b;
            font-size: 12px;
            margin-bottom: 4px;
        }
        .strategy-card .value {
            color: #0f172a;
            font-weight: 800;
            font-size: 16px;
        }
        .strategy-card .note {
            color: #475569;
            font-size: 12px;
            margin-top: 4px;
            line-height: 1.35;
        }
        div[data-testid="stDataFrame"] { margin-top: 4px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    configure_chart_font()


def configure_chart_font() -> None:
    try:
        import koreanize_matplotlib  # noqa: F401
    except ImportError:
        pass

    font_candidates = ["Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "NanumGothic"]
    available_fonts = {font.name for font in font_manager.fontManager.ttflist}
    for font_name in font_candidates:
        if font_name in available_fonts:
            plt.rcParams["font.family"] = font_name
            break
    plt.rcParams["axes.unicode_minus"] = False


def add_places_to_map(map_obj: folium.Map, rows: list[dict]) -> None:
    for row in rows:
        folium.CircleMarker(
            location=[float(row["y"]), float(row["x"])],
            radius=5,
            color="#2563eb",
            fill=True,
            fill_opacity=0.8,
            popup=f"{row.get('place_name', '')}<br>{row.get('road_address_name') or row.get('address_name', '')}",
        ).add_to(map_obj)


def add_movement_to_map(map_obj: folium.Map, lat: float, lon: float, rows: list[dict]) -> None:
    colors = {
        "대중교통": "#ef4444",
        "카페": "#2563eb",
        "음식점": "#f59e0b",
        "문화시설": "#7c3aed",
        "관광명소": "#10b981",
    }
    for row in get_direction_targets(rows, lat, lon, limit_per_category=2):
        folium.PolyLine(
            locations=[[lat, lon], [row["lat"], row["lon"]]],
            color=colors.get(row["category"], "#64748b"),
            weight=3,
            opacity=0.7,
            tooltip=f"{row['category']} · {row['name']} · {row['distance']}m",
        ).add_to(map_obj)


def format_api_error(exc: ApiError) -> str:
    message = str(exc)
    if "disabled OPEN_MAP_AND_LOCAL service" in message:
        return (
            f"{message}\n\n"
            "해결 방법: 카카오 Developers 콘솔에서 현재 앱의 "
            "[제품 설정 > 카카오맵 > 로컬] 또는 카카오맵/로컬 API 사용 설정을 활성화하세요. "
            "이 기능은 어드민 키가 아니라 REST API 키로 호출해야 합니다."
        )
    return message


def render_analysis_summary(analysis) -> None:
    st.subheader("핵심 요약")
    st.markdown(render_list_html(analysis.insights[:6]), unsafe_allow_html=True)

    st.subheader("설계 기회")
    st.markdown(render_list_html(analysis.opportunities), unsafe_allow_html=True)

    st.subheader("검증 사항")
    st.markdown(render_list_html(analysis.cautions), unsafe_allow_html=True)


def render_overview(analysis) -> None:
    st.subheader(analysis.site_name)

    metric_cols = st.columns(4)
    metric_cols[0].metric("분석 반경", f"{analysis.radius}m")
    metric_cols[1].metric("주변 장소", f"{sum(analysis.place_counts.values())}건")
    metric_cols[2].metric("공간 레이어", f"{len(analysis.spatial_layer_counts)}개")
    metric_cols[3].metric("설계 키워드", f"{len(analysis.design_keywords)}개")

    address_col, region_col = st.columns(2)
    with address_col:
        render_info_card("주소", analysis.address_text)
    with region_col:
        render_info_card("행정구역", analysis.region_text)

    st.markdown(
        "".join(f'<span class="keyword">{keyword}</span>' for keyword in analysis.design_keywords),
        unsafe_allow_html=True,
    )


def render_places(places_rows: list[dict], analysis) -> None:
    st.subheader("주변 장소 분포")
    if analysis.place_counts:
        labels = list(analysis.place_counts.keys())
        values = [analysis.place_counts[label] for label in labels]
        st.pyplot(
            make_bar_figure(labels, values, ylabel="개수", height=2.9, color="#2563eb"),
            clear_figure=True,
            width="stretch",
        )
    else:
        st.caption("조회된 주변 장소가 없습니다.")


def render_movement_diagram(places_rows: list[dict], lat: float, lon: float) -> None:
    st.subheader("접근 동선 전략")
    targets = get_direction_targets(places_rows, lat, lon, limit_per_category=2)
    if not targets:
        st.caption("접근 동선을 해석할 주변 장소 데이터가 없습니다.")
        return

    direction_summary = summarize_movement_strategy(targets)
    st.markdown(render_movement_strategy_cards(direction_summary), unsafe_allow_html=True)

    map_col, chart_col = st.columns([1.2, 0.8])
    with map_col:
        st_folium(
            make_movement_map(lat, lon, select_key_targets(targets), direction_summary),
            height=420,
            use_container_width=True,
        )
    with chart_col:
        st.pyplot(
            make_movement_figure(targets),
            clear_figure=True,
            width="stretch",
        )
    st.caption("지도는 주 유입축과 대표 앵커만 단순화해 표시합니다. 그래프는 방향별 접근 강도를 비교하기 위한 근거 자료입니다.")

    st.subheader("동선 판단 근거")
    if places_rows:
        df = pd.DataFrame(places_rows)
        nearest = df.sort_values("distance", key=lambda col: col.astype(int)).head(8)
        st.markdown(render_place_rows(nearest.to_dict("records")), unsafe_allow_html=True)

        with st.expander("장소 목록 전체 보기"):
            compact = df[["analysis_category", "place_name", "distance", "road_address_name"]].rename(
                columns={
                    "analysis_category": "분류",
                    "place_name": "장소명",
                    "distance": "거리",
                    "road_address_name": "주소",
                }
            )
            st.dataframe(compact, width="stretch", hide_index=True, height=260)
    else:
        st.caption("조회된 주변 장소가 없습니다.")


def render_spatial_layers(analysis) -> None:
    st.subheader("공간정보")
    if analysis.spatial_layer_counts:
        cols = st.columns(min(len(analysis.spatial_layer_counts), 4))
        for idx, (key, value) in enumerate(analysis.spatial_layer_counts.items()):
            cols[idx % len(cols)].metric(key, f"{value}건" if isinstance(value, int) else str(value))
    else:
        st.caption("조회된 공간정보 레이어가 없습니다.")


def render_comparison(comparison_rows: list[dict]) -> None:
    st.subheader("후보지 비교")
    if not comparison_rows:
        st.caption("후보지 비교 데이터가 없습니다. 사이드바에 후보 좌표를 추가하면 비교표가 생성됩니다.")
        return
    df = pd.DataFrame(comparison_rows)
    best = df.sort_values("종합점수", ascending=False).iloc[0].to_dict()
    st.info(f"현재 기준 최상위 후보는 **{best['후보지']}**입니다. {best.get('비교해석', '')}")
    render_comparison_cards(comparison_rows)

    render_score_guide()
    st.caption("점수는 절대적인 부동산 평가가 아니라, 실내건축 스튜디오 초기 대지 비교를 위한 0-100점 스크리닝 지표입니다.")

    chart_df = df[["후보지", "종합점수", "접근성", "상권성", "문화성", "균형성"]].sort_values("종합점수", ascending=True)
    rank_col, matrix_col = st.columns([0.9, 1.1])
    with rank_col:
        st.pyplot(
            make_total_rank_figure(chart_df),
            clear_figure=True,
            width="stretch",
        )
    with matrix_col:
        st.pyplot(
            make_score_matrix_figure(chart_df.sort_values("종합점수", ascending=False)),
            clear_figure=True,
            width="stretch",
        )

    with st.expander("비교표 자세히 보기"):
        visible_columns = [
            "후보지",
            "종합점수",
            "유형",
            "비교해석",
            "접근성",
            "상권성",
            "문화성",
            "균형성",
            "대중교통",
            "상업편의",
            "문화관광",
            "최근접교통",
            "최근접상업",
            "최근접문화",
            "주소",
        ]
        st.dataframe(df[[column for column in visible_columns if column in df]], width="stretch", hide_index=True, height=280)


def render_list_html(items: list[str]) -> str:
    return '<ul class="insight-list">' + "".join(f"<li>{item}</li>" for item in items) + "</ul>"


def render_info_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="site-card">
            <div class="label">{label}</div>
            <div class="value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_place_rows(rows: list[dict]) -> str:
    html = []
    for row in rows:
        address = row.get("road_address_name") or row.get("address_name") or "주소 정보 없음"
        html.append(
            f"""
            <div class="place-row">
                <div class="place-cat">{row.get("analysis_category", "")}</div>
                <div>
                    <div class="place-name">{row.get("place_name", "")}</div>
                    <div class="place-address">{address}</div>
                </div>
                <div class="place-distance">{row.get("distance", "-")}m</div>
            </div>
            """
        )
    return "".join(html)


def render_comparison_cards(rows: list[dict]) -> None:
    if not rows:
        return
    cols = st.columns(min(3, len(rows)))
    for idx, row in enumerate(rows):
        with cols[idx % len(cols)]:
            with st.container(border=True):
                st.markdown(f"**{row['후보지']}**")
                st.metric("종합점수", row.get("종합점수", "-"))
                st.caption(row.get("유형", "종합 후보"))
                st.write(row.get("비교해석", ""))
                st.caption(
                    f"교통 {row.get('최근접교통', '-')} · "
                    f"상업 {row.get('최근접상업', '-')} · "
                    f"문화 {row.get('최근접문화', '-')}"
                )


def render_score_guide() -> None:
    guide = [
        ("접근성", "가까운 대중교통의 거리 68% + 대중교통 개수 32%"),
        ("상권성", "가까운 카페/음식/편의시설 42% + 생활 상업 밀도 58%"),
        ("문화성", "가까운 문화/관광 거점 52% + 문화 거점 개수 48%"),
        ("균형성", "한 종류에 치우치지 않고 여러 프로그램이 분포하는 정도"),
        ("종합점수", "접근성 32% + 상권성 28% + 문화성 22% + 균형성 18%"),
    ]
    cols = st.columns(5)
    for idx, (title, description) in enumerate(guide):
        with cols[idx % len(cols)]:
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.caption(description)


def render_environment_cards(items: list[tuple[str, str, str]]) -> None:
    if not items:
        return
    cols = st.columns(4)
    for idx, (label, value, note) in enumerate(items):
        with cols[idx % len(cols)]:
            with st.container(border=True):
                st.caption(label)
                st.markdown(f"### {value}")
                st.caption(note)


def render_sun_reading_cards() -> None:
    items = [
        ("고도", "높을수록 실내 깊숙한 직사광은 줄고, 낮을수록 눈부심과 긴 그림자가 커집니다."),
        ("방위", "동측은 오전, 남측은 정오 전후, 서측은 오후 과열과 눈부심 검토가 중요합니다."),
        ("설계 적용", "주 체류공간은 안정적인 자연광을, 전이공간은 계절별 직사광 조절을 기준으로 배치합니다."),
    ]
    for title, description in items:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(description)


def render_environment_sections(analysis) -> None:
    st.subheader("일조 및 기후 환경")

    summary_items = []
    if analysis.climate_summary:
        climate = analysis.climate_summary
        summary_items.extend(
            [
                ("연평균 기온", _format_value(climate.mean_temp, "°C"), "실내 쾌적성 기준"),
                ("여름 최고기온", _format_value(climate.summer_mean_max_temp, "°C"), "차양/냉방 부하"),
                ("겨울 최저기온", _format_value(climate.winter_mean_min_temp, "°C"), "단열/채광 전략"),
                ("연간 강수량", _format_value(climate.annual_precipitation, "mm"), "출입부/외부마감"),
                ("일조 시간", _format_value(climate.annual_sunshine_hours, "시간"), "자연광 활용성"),
                ("평균 풍속", _format_value(climate.mean_wind_speed, "m/s"), "환기/문풍 고려"),
            ]
        )
    if analysis.sun_analysis:
        longest = max(analysis.sun_analysis.daylight_hours.items(), key=lambda item: item[1])
        shortest = min(analysis.sun_analysis.daylight_hours.items(), key=lambda item: item[1])
        summary_items.extend(
            [
                ("최장 일장", f"{longest[0]} {longest[1]}시간", "여름 채광/차양"),
                ("최단 일장", f"{shortest[0]} {shortest[1]}시간", "겨울 채광 확보"),
            ]
        )
    if summary_items:
        render_environment_cards(summary_items)
    else:
        st.caption("일조 및 기후 데이터가 없습니다.")

    if analysis.sun_analysis:
        path_col, note_col = st.columns([1.55, 0.75])
        with path_col:
            st.markdown("#### 태양 경로 다이어그램")
            st.pyplot(
                make_sun_path_3d_figure(analysis.sun_analysis.samples),
                clear_figure=True,
                width="stretch",
            )
        with note_col:
            st.markdown("#### 읽는 방법")
            render_sun_reading_cards()

        lower_col1, lower_col2 = st.columns([1.1, 0.9])
        with lower_col1:
            st.markdown("#### 시간대별 태양 고도")
            st.pyplot(
                make_sun_altitude_figure(analysis.sun_analysis.samples),
                clear_figure=True,
                width="stretch",
            )
        with lower_col2:
            st.markdown("#### 절기별 일장")
            st.pyplot(
                make_bar_figure(
                    list(analysis.sun_analysis.daylight_hours.keys()),
                    list(analysis.sun_analysis.daylight_hours.values()),
                    ylabel="일장(시간)",
                    height=3.0,
                    color="#f59e0b",
                ),
                clear_figure=True,
                width="stretch",
            )

        with st.expander("태양고도/방위각 상세표"):
            table = pd.DataFrame(
                [
                    {
                        "절기": sample.label,
                        "시각": sample.time_label,
                        "고도": f"{sample.altitude}°",
                        "방위": f"{sample.azimuth}°",
                    }
                    for sample in analysis.sun_analysis.samples
                ]
            )
            st.dataframe(table, width="stretch", hide_index=True, height=220)
    else:
        st.caption("일조 분석 데이터가 없습니다.")

    if analysis.climate_summary:
        st.caption(f"기후 자료 기간: {analysis.climate_summary.source_period}")


def main() -> None:
    st.set_page_config(page_title="Site Analysis Assistant", layout="wide")
    inject_styles()
    st.title("Site Analysis Assistant")
    st.caption("대한민국 좌표 기반 대지 분석 자료 생성기")

    with st.sidebar:
        st.subheader("대지 입력")
        site_name = st.text_input("프로젝트/대지 이름", value="서울시청 인근 대지")
        lat = st.number_input("위도 latitude", value=37.5665, format="%.7f")
        lon = st.number_input("경도 longitude", value=126.9780, format="%.7f")
        radius = st.slider("분석 반경(m)", min_value=100, max_value=2000, value=500, step=100)
        selected_categories = st.multiselect(
            "주변 장소",
            list(PLACE_CATEGORIES),
            default=["대중교통", "카페", "문화시설", "음식점"],
        )
        selected_layers = st.multiselect(
            "공간정보 레이어",
            list(VWORLD_LAYERS),
            default=["연속지적도", "도시지역"],
        )
        include_sun = st.checkbox("일조 분석 포함", value=True)
        include_climate = st.checkbox("기후 요약 포함", value=True)
        climate_year = st.number_input("기후 기준 연도", min_value=2017, max_value=date.today().year - 1, value=date.today().year - 1)
        auto_candidates = st.checkbox("비교 후보 자동 추천", value=True)
        auto_candidate_count = st.slider("자동 후보 수", min_value=1, max_value=5, value=3, step=1, disabled=not auto_candidates)
        candidate_text = st.text_area(
            "직접 추가할 비교 후보 좌표",
            value="",
            placeholder="선택 입력: 후보지 B,37.5700,126.9820\n후보지 C,37.5610,126.9770",
            height=88,
        )

        with st.expander("브이월드 API 직접 입력"):
            st.caption("배포 환경변수가 잘 적용되지 않을 때 임시로 테스트할 수 있습니다. 입력값은 현재 앱 세션에서만 사용되고 저장되지 않습니다.")
            vworld_key_input = st.text_input(
                "브이월드 인증키",
                value="",
                type="password",
                placeholder="비워두면 서버 환경변수 VWORLD_API_KEY 사용",
            )
            vworld_domain_input = st.text_input(
                "브이월드 허용 도메인",
                value="",
                placeholder=os.getenv("VWORLD_DOMAIN") or "https://site-analysis-ai.onrender.com",
            )

        vworld = VWorldDataClient(
            api_key=vworld_key_input.strip() or None,
            domain=vworld_domain_input.strip() or None,
        )
        kakao = KakaoLocalClient()
        sgis = SgisClient()
        meteo = OpenMeteoClient()
        osm = OpenStreetMapClient()

        run = st.button("분석 자료 생성", type="primary")

        with st.expander("데이터 소스 상태"):
            st.write(f"브이월드: {'연결 가능' if vworld.enabled else '키 필요'}")
            st.write(f"브이월드 도메인: {vworld.domain}")
            st.write(f"SGIS 인구 통계: {'연결 가능' if sgis.enabled else '키 필요'}")
            st.write("Open-Meteo 기후: 키 없이 사용")

    site_map = folium.Map(location=[lat, lon], zoom_start=16, tiles="OpenStreetMap")
    folium.Marker([lat, lon], tooltip="대지 좌표", icon=folium.Icon(color="red")).add_to(site_map)
    folium.Circle([lat, lon], radius=radius, color="#ef4444", fill=False).add_to(site_map)

    saved_result = st.session_state.get("analysis_result")
    if not run and not saved_result:
        st_folium(site_map, height=620, use_container_width=True)
        st.info("좌표와 분석 반경을 설정한 뒤 '분석 자료 생성'을 실행하세요.")
        return

    if run:
        address_response = None
        region_response = None
        places_rows: list[dict] = []
        collection_notes: list[str] = []
        comparison_rows: list[dict] = []
        population_response = None
        vworld_responses: dict[str, dict | None] = {}
        climate_response = None
        sun_analysis = analyze_sun(lat, lon) if include_sun else None

        with st.spinner("좌표 기반 데이터를 수집하는 중입니다..."):
            if vworld.enabled:
                try:
                    address_response, region_response = vworld.coord_to_address_and_region(lon, lat)
                    collection_notes.append("주소/행정구역: 브이월드 역지오코딩 사용")
                except ApiError as exc:
                    collection_notes.append(f"브이월드 주소 조회 실패: {exc}")

            if not address_response and kakao.enabled:
                try:
                    address_response = kakao.coord_to_address(lon, lat)
                    region_response = kakao.coord_to_region(lon, lat)
                    collection_notes.append("주소/행정구역: 카카오 보조 조회 사용")
                except ApiError as exc:
                    collection_notes.append(f"카카오 주소 보조 조회 실패: {format_api_error(exc)}")

            if not address_response:
                try:
                    address_response, region_response = osm.reverse_geocode(lon, lat)
                    collection_notes.append("주소/행정구역: OpenStreetMap 보조 조회 사용")
                except ApiError as exc:
                    collection_notes.append(f"OpenStreetMap 주소 보조 조회 실패: {exc}")

            for label in selected_categories:
                docs: list[dict] = []
                if vworld.enabled:
                    try:
                        data = vworld.place_search(lon, lat, label, radius=radius)
                        docs = data.get("documents", [])
                        collection_notes.append(f"{label}: 브이월드 {len(docs)}건")
                    except ApiError as exc:
                        collection_notes.append(f"{label} 브이월드 장소 조회 실패: {exc}")

                if not docs and kakao.enabled:
                    try:
                        data = kakao.category_search(lon, lat, PLACE_CATEGORIES[label], radius=radius)
                        docs = data.get("documents", [])
                        for item in docs:
                            item["analysis_category"] = label
                        collection_notes.append(f"{label}: 카카오 보조 {len(docs)}건")
                    except ApiError as exc:
                        collection_notes.append(f"{label} 카카오 보조 조회 실패: {format_api_error(exc)}")

                if not docs:
                    try:
                        osm_data = osm.category_search(lon, lat, label, radius=radius)
                        docs = osm_data.get("documents", [])
                        collection_notes.append(f"{label}: OpenStreetMap 보조 {len(docs)}건")
                    except ApiError as exc:
                        collection_notes.append(f"{label} OpenStreetMap 보조 조회 실패: {exc}")

                places_rows.extend(docs)

            if not places_rows and kakao.enabled:
                for label in selected_categories:
                    try:
                        data = kakao.category_search(lon, lat, PLACE_CATEGORIES[label], radius=radius)
                        docs = data.get("documents", [])
                        for item in docs:
                            item["analysis_category"] = label
                        places_rows.extend(docs)
                    except ApiError:
                        pass

            if not places_rows:
                for label in selected_categories:
                    try:
                        osm_data = osm.category_search(lon, lat, label, radius=radius)
                        docs = osm_data.get("documents", [])
                        places_rows.extend(docs)
                    except ApiError:
                        pass

            if not places_rows:
                collection_notes.append("주변 장소: 보조 데이터 소스에서도 결과 없음")
                collection_notes.append(
                    "확인 필요: Render 환경변수 VWORLD_API_KEY가 비어 있거나, 브이월드 인증키의 허용 도메인과 VWORLD_DOMAIN이 다르면 장소 검색이 0건으로 표시될 수 있습니다."
                )

            if sgis.enabled:
                try:
                    code_data = sgis.find_small_area_code(lon, lat)
                    adm_cd = sgis_adm_cd_from_findcode(code_data)
                    if adm_cd:
                        population_response = sgis.population_summary(adm_cd)
                except ApiError as exc:
                    collection_notes.append(f"SGIS 인구 통계 조회 실패: {exc}")

            if vworld.enabled:
                bbox = bbox_from_radius(lon, lat, min(radius, 700))
                for label in selected_layers:
                    try:
                        vworld_responses[label] = vworld.get_features(VWORLD_LAYERS[label], bbox)
                    except ApiError as exc:
                        vworld_responses[label] = None
                        collection_notes.append(f"{label} 공간정보 조회 실패: {exc}")

            if include_climate:
                try:
                    climate_response = meteo.daily_history(
                        lon=lon,
                        lat=lat,
                        start_date=f"{climate_year}-01-01",
                        end_date=f"{climate_year}-12-31",
                    )
                except ApiError as exc:
                    collection_notes.append(f"Open-Meteo 기후 데이터 조회 실패: {exc}")

            comparison_rows = build_comparison_rows(
                base_name=site_name,
                base_lat=lat,
                base_lon=lon,
                base_places=places_rows,
                base_layers=vworld_responses,
                candidate_text=candidate_text,
                auto_candidates=auto_candidates,
                auto_candidate_count=auto_candidate_count,
                vworld=vworld,
                categories=selected_categories,
                radius=radius,
            )

        climate_summary = summarize_climate(climate_response, f"{climate_year}-01-01 ~ {climate_year}-12-31")
        analysis = create_site_analysis(
            site_name=site_name,
            lat=lat,
            lon=lon,
            radius=radius,
            address_response=address_response,
            region_response=region_response,
            places=places_rows,
            population_response=population_response,
            vworld_responses=vworld_responses,
            sun_analysis=sun_analysis,
            climate_summary=climate_summary,
        )
        saved_result = {
            "analysis": analysis,
            "places_rows": places_rows,
            "address_response": address_response,
            "region_response": region_response,
            "population_response": population_response,
            "climate_response": climate_response,
            "collection_notes": collection_notes,
            "comparison_rows": comparison_rows,
        }
        st.session_state["analysis_result"] = saved_result
    else:
        analysis = saved_result["analysis"]
        places_rows = saved_result["places_rows"]
        address_response = saved_result["address_response"]
        region_response = saved_result["region_response"]
        population_response = saved_result["population_response"]
        climate_response = saved_result["climate_response"]
        collection_notes = saved_result.get("collection_notes", [])
        comparison_rows = saved_result.get("comparison_rows", [])
        site_map = folium.Map(location=[analysis.lat, analysis.lon], zoom_start=16, tiles="OpenStreetMap")
        folium.Marker([analysis.lat, analysis.lon], tooltip="대지 좌표", icon=folium.Icon(color="red")).add_to(site_map)
        folium.Circle([analysis.lat, analysis.lon], radius=analysis.radius, color="#ef4444", fill=False).add_to(site_map)

    if places_rows:
        add_places_to_map(site_map, places_rows)
        add_movement_to_map(site_map, analysis.lat, analysis.lon, places_rows)

    render_overview(analysis)

    st.divider()
    top_left, top_right = st.columns([1.1, 0.9])
    with top_left:
        st.subheader("대지 지도")
        st_folium(site_map, height=560, use_container_width=True)
    with top_right:
        render_analysis_summary(analysis)

    st.divider()
    render_movement_diagram(places_rows, analysis.lat, analysis.lon)

    st.divider()
    render_places(places_rows, analysis)
    if not places_rows:
        st.warning(
            "주변 장소가 0건입니다. 사이드바의 데이터 소스 상태와 하단 데이터 수집 로그에서 "
            "VWORLD_API_KEY, VWORLD_DOMAIN, 카카오 로컬 API 활성화 여부를 확인하세요."
        )

    st.divider()
    render_environment_sections(analysis)

    st.divider()
    render_comparison(comparison_rows)

    st.divider()
    render_spatial_layers(analysis)

    html_report = render_html_report(analysis)
    export_col1, export_col2, export_col3 = st.columns(3)
    with export_col1:
        st.download_button(
            "HTML 보고서",
            data=html_report.encode("utf-8"),
            file_name=f"{site_name}_site_analysis.html",
            mime="text/html",
            width="stretch",
        )
    with export_col2:
        st.download_button(
            "주변 장소 CSV",
            data=places_to_csv(places_rows).encode("utf-8-sig"),
            file_name=f"{site_name}_places.csv",
            mime="text/csv",
            width="stretch",
        )
    with export_col3:
        st.download_button(
            "분석 데이터 JSON",
            data=analysis_to_json(analysis, places_rows, comparison_rows).encode("utf-8"),
            file_name=f"{site_name}_analysis.json",
            mime="application/json",
            width="stretch",
        )
    st.caption("PDF가 필요하면 HTML 보고서를 연 뒤 브라우저 인쇄에서 PDF로 저장하면 됩니다.")

    with st.expander("데이터 수집 로그와 원본 응답"):
        if collection_notes:
            for note in collection_notes:
                st.write(f"- {note}")
        st.json(
            {
                "address": address_response,
                "region": region_response,
                "population": population_response,
                "spatial_layers": analysis.spatial_layer_counts,
                "climate": climate_response,
            }
        )


def _format_value(value: float | None, unit: str) -> str:
    return "-" if value is None else f"{value}{unit}"


def make_bar_figure(labels: list[str], values: list[int | float], ylabel: str, height: float, color: str):
    fig, ax = plt.subplots(figsize=(7.2, height), dpi=120)
    bars = ax.bar(labels, values, color=color, width=0.58)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d1d5db")
    ax.spines["bottom"].set_color("#d1d5db")
    ax.tick_params(axis="x", labelrotation=0, labelsize=9)
    ax.tick_params(axis="y", labelsize=9)
    for bar in bars:
        value = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value,
            f"{value:g}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="#374151",
        )
    fig.tight_layout()
    return fig


def make_sun_altitude_figure(samples):
    fig, ax = plt.subplots(figsize=(7.2, 2.7), dpi=120)
    colors = {
        "춘분": "#22c55e",
        "하지": "#f59e0b",
        "추분": "#0ea5e9",
        "동지": "#64748b",
    }
    times = ["09:00", "12:00", "15:00"]
    for label in ["춘분", "하지", "추분", "동지"]:
        values = [
            next((sample.altitude for sample in samples if sample.label == label and sample.time_label == time), None)
            for time in times
        ]
        ax.plot(times, values, marker="o", linewidth=2, color=colors.get(label), label=label)
        for time, value in zip(times, values):
            if value is not None:
                ax.text(time, value + 1.8, f"{value:g}", ha="center", va="bottom", fontsize=8, color="#374151")
    ax.set_ylabel("태양고도(°)")
    max_altitude = max(sample.altitude for sample in samples)
    ax.set_ylim(bottom=0, top=min(95, max_altitude + 12))
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d1d5db")
    ax.spines["bottom"].set_color("#d1d5db")
    ax.tick_params(axis="both", labelsize=9)
    ax.legend(loc="upper left", ncols=4, frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def make_sun_path_3d_figure(samples):
    fig = plt.figure(figsize=(7.2, 4.2), dpi=120)
    ax = fig.add_subplot(111, projection="3d")
    colors = {
        "춘분": "#22c55e",
        "하지": "#f59e0b",
        "추분": "#0ea5e9",
        "동지": "#64748b",
    }
    times = ["09:00", "12:00", "15:00"]

    draw_sky_dome(ax)
    draw_cardinal_guides(ax)

    for label in ["춘분", "하지", "추분", "동지"]:
        points = []
        for time in times:
            sample = next((item for item in samples if item.label == label and item.time_label == time), None)
            if not sample:
                continue
            x, y, z = sun_to_cartesian(sample.azimuth, sample.altitude)
            points.append((x, y, z, sample))
        if not points:
            continue
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        zs = [point[2] for point in points]
        ax.plot(xs, ys, zs, color=colors[label], linewidth=2.4, label=label)
        ax.scatter(xs, ys, zs, color=colors[label], s=34, depthshade=False)
        for x, y, z, sample in points:
            ax.text(x, y, z + 0.05, sample.time_label.replace(":00", "시"), fontsize=8, ha="center")

    ax.set_title("3D 태양 경로 다이어그램", pad=12, fontsize=12, fontweight="bold")
    ax.set_xlabel("동-서")
    ax.set_ylabel("남-북")
    ax.set_zlabel("고도")
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_zlim(0, 1.05)
    ax.set_box_aspect((1, 1, 0.62))
    ax.view_init(elev=24, azim=-48)
    ax.legend(loc="upper left", bbox_to_anchor=(0.02, 0.98), frameon=False, fontsize=8)
    ax.grid(False)
    fig.tight_layout()
    return fig


def sun_to_cartesian(azimuth: float, altitude: float) -> tuple[float, float, float]:
    az = math.radians(azimuth)
    alt = math.radians(altitude)
    horizontal = math.cos(alt)
    x = horizontal * math.sin(az)
    y = horizontal * math.cos(az)
    z = math.sin(alt)
    return x, y, z


def draw_sky_dome(ax) -> None:
    for altitude in [15, 30, 45, 60, 75]:
        radius = math.cos(math.radians(altitude))
        z = math.sin(math.radians(altitude))
        angles = [math.radians(value) for value in range(0, 361, 5)]
        xs = [radius * math.sin(angle) for angle in angles]
        ys = [radius * math.cos(angle) for angle in angles]
        zs = [z for _ in angles]
        ax.plot(xs, ys, zs, color="#e5e7eb", linewidth=0.7)

    horizon_angles = [math.radians(value) for value in range(0, 361, 5)]
    ax.plot(
        [math.sin(angle) for angle in horizon_angles],
        [math.cos(angle) for angle in horizon_angles],
        [0 for _ in horizon_angles],
        color="#9ca3af",
        linewidth=1.0,
    )


def draw_cardinal_guides(ax) -> None:
    guides = {
        "N": (0, 1, 0),
        "E": (1, 0, 0),
        "S": (0, -1, 0),
        "W": (-1, 0, 0),
    }
    for label, (x, y, z) in guides.items():
        ax.plot([0, x], [0, y], [0, z], color="#d1d5db", linewidth=0.8)
        ax.text(x * 1.08, y * 1.08, 0, label, ha="center", va="center", fontsize=9, fontweight="bold")


def get_direction_targets(rows: list[dict], base_lat: float, base_lon: float, limit_per_category: int = 3) -> list[dict]:
    targets: list[dict] = []
    counts: dict[str, int] = {}
    sorted_rows = sorted(rows, key=lambda row: _to_int(row.get("distance"), 999999))
    for row in sorted_rows:
        category = row.get("analysis_category") or "기타"
        if counts.get(category, 0) >= limit_per_category:
            continue
        lat = _to_float(row.get("y"))
        lon = _to_float(row.get("x"))
        if lat is None or lon is None:
            continue
        distance = _to_int(row.get("distance"), int(haversine_m(base_lat, base_lon, lat, lon)))
        bearing = bearing_deg(base_lat, base_lon, lat, lon)
        targets.append(
            {
                "category": category,
                "name": row.get("place_name") or category,
                "lat": lat,
                "lon": lon,
                "distance": distance,
                "bearing": bearing,
                "direction": bearing_to_direction_label(bearing),
            }
        )
        counts[category] = counts.get(category, 0) + 1
    return targets


def summarize_directions(targets: list[dict]) -> str:
    if not targets:
        return "분석 대상 없음"
    weighted: dict[str, float] = {}
    for target in targets:
        distance = max(target.get("distance", 1), 1)
        weighted[target["direction"]] = weighted.get(target["direction"], 0) + 1 / distance
    ranked = sorted(weighted.items(), key=lambda item: item[1], reverse=True)
    labels = [label for label, _ in ranked[:3]]
    return ", ".join(labels)


def summarize_movement_strategy(targets: list[dict]) -> dict:
    direction_order = ["북측", "북동측", "동측", "남동측", "남측", "남서측", "서측", "북서측"]
    scores = {direction: 0.0 for direction in direction_order}
    counts = {direction: 0 for direction in direction_order}
    anchors = {direction: [] for direction in direction_order}
    for target in targets:
        direction = target["direction"]
        distance = max(target.get("distance", 1), 1)
        category_weight = {
            "대중교통": 1.35,
            "문화시설": 1.12,
            "관광명소": 1.08,
            "카페": 1.0,
            "음식점": 1.0,
        }.get(target["category"], 0.88)
        scores[direction] = scores.get(direction, 0) + category_weight / math.sqrt(distance)
        counts[direction] = counts.get(direction, 0) + 1
        anchors.setdefault(direction, []).append(target)

    ranked = sorted(direction_order, key=lambda direction: scores[direction], reverse=True)
    primary = ranked[0]
    secondary = next((direction for direction in ranked[1:] if scores[direction] > 0), "보조축 없음")
    primary_anchor = sorted(anchors.get(primary, []), key=lambda item: item["distance"])[0] if anchors.get(primary) else None
    response = design_response_for_axis(primary, primary_anchor)
    return {
        "primary": primary,
        "secondary": secondary,
        "primary_score": scores.get(primary, 0),
        "scores": scores,
        "counts": counts,
        "primary_anchor": primary_anchor,
        "response": response,
    }


def render_movement_strategy_cards(summary: dict) -> str:
    anchor = summary.get("primary_anchor") or {}
    anchor_text = f"{anchor.get('name', '-')} ({anchor.get('category', '-')}, {anchor.get('distance', '-')}m)"
    return f"""
    <div class="strategy-grid">
        <div class="strategy-card">
            <div class="label">주 유입축</div>
            <div class="value">{summary.get('primary', '-')}</div>
            <div class="note">사람이 들어올 가능성이 가장 큰 방향입니다.</div>
        </div>
        <div class="strategy-card">
            <div class="label">보조 유입축</div>
            <div class="value">{summary.get('secondary', '-')}</div>
            <div class="note">두 번째로 고려할 접근 방향입니다.</div>
        </div>
        <div class="strategy-card">
            <div class="label">대표 앵커</div>
            <div class="value">{anchor_text}</div>
            <div class="note">입구, 간판, 전이공간 배치의 기준점입니다.</div>
        </div>
        <div class="strategy-card">
            <div class="label">설계 대응</div>
            <div class="value">{summary.get('response', '-')}</div>
            <div class="note">초기 평면과 동선 계획에 바로 반영할 방향입니다.</div>
        </div>
    </div>
    """


def design_response_for_axis(direction: str, anchor: dict | None) -> str:
    if not anchor:
        return "현장 보행축 확인 필요"
    category = anchor.get("category")
    if category == "대중교통":
        return f"{direction}에 명확한 진입부와 빠른 안내축 배치"
    if category in {"카페", "음식점", "편의점"}:
        return f"{direction} 생활가로와 연결되는 열린 전면 계획"
    if category in {"문화시설", "관광명소"}:
        return f"{direction} 시야축과 체류형 전이공간 강화"
    return f"{direction} 보행 흐름을 받는 완충 공간 계획"


def select_key_targets(targets: list[dict], max_count: int = 8) -> list[dict]:
    summary = summarize_movement_strategy(targets)
    preferred_directions = [summary["primary"], summary["secondary"]]
    selected: list[dict] = []
    used_names: set[str] = set()
    for direction in preferred_directions:
        direction_targets = sorted([target for target in targets if target["direction"] == direction], key=lambda item: item["distance"])
        for target in direction_targets[:3]:
            if target["name"] in used_names:
                continue
            selected.append(target)
            used_names.add(target["name"])
    for target in sorted(targets, key=lambda item: item["distance"]):
        if len(selected) >= max_count:
            break
        if target["name"] in used_names:
            continue
        selected.append(target)
        used_names.add(target["name"])
    return selected


def make_movement_map(lat: float, lon: float, targets: list[dict], summary: dict) -> folium.Map:
    colors = {
        "대중교통": "#ef4444",
        "카페": "#2563eb",
        "음식점": "#f59e0b",
        "문화시설": "#7c3aed",
        "관광명소": "#10b981",
        "학교": "#14b8a6",
        "편의점": "#64748b",
        "병원": "#0ea5e9",
    }
    movement_map = folium.Map(location=[lat, lon], zoom_start=16, tiles="OpenStreetMap")
    folium.Marker(
        [lat, lon],
        tooltip="분석 대지",
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(movement_map)
    folium.Circle([lat, lon], radius=max(target["distance"] for target in targets), color="#ef4444", fill=False, weight=1).add_to(movement_map)

    for target in targets:
        color = colors.get(target["category"], "#64748b")
        tooltip = f"{target['category']} · {target['name']} · {target['direction']} · {target['distance']}m"
        folium.PolyLine(
            locations=[[lat, lon], [target["lat"], target["lon"]]],
            color=color,
            weight=3,
            opacity=0.72,
            tooltip=tooltip,
        ).add_to(movement_map)
        folium.CircleMarker(
            location=[target["lat"], target["lon"]],
            radius=5,
            color=color,
            fill=True,
            fill_opacity=0.86,
            tooltip=tooltip,
        ).add_to(movement_map)

    primary_anchor = summary.get("primary_anchor")
    if primary_anchor:
        folium.PolyLine(
            locations=[[lat, lon], [primary_anchor["lat"], primary_anchor["lon"]]],
            color="#111827",
            weight=6,
            opacity=0.8,
            tooltip=f"주 유입축: {summary.get('primary')} · {primary_anchor['name']}",
        ).add_to(movement_map)
    return movement_map


def make_movement_figure(targets: list[dict]):
    colors = {
        "북측": "#2563eb",
        "북동측": "#0ea5e9",
        "동측": "#10b981",
        "남동측": "#84cc16",
        "남측": "#f59e0b",
        "남서측": "#f97316",
        "서측": "#ef4444",
        "북서측": "#7c3aed",
    }
    direction_order = ["북측", "북동측", "동측", "남동측", "남측", "남서측", "서측", "북서측"]
    direction_angles = [0, 45, 90, 135, 180, 225, 270, 315]
    values = {direction: 0.0 for direction in direction_order}
    counts = {direction: 0 for direction in direction_order}
    for target in targets:
        direction = target["direction"]
        distance = max(target.get("distance", 1), 1)
        values[direction] = values.get(direction, 0) + 1 / math.sqrt(distance)
        counts[direction] = counts.get(direction, 0) + 1

    max_value = max(values.values()) if values else 1
    scaled_values = [(values[direction] / max_value) * 100 if max_value else 0 for direction in direction_order]

    fig = plt.figure(figsize=(5.6, 4.2), dpi=120)
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, 112)
    ax.set_yticks([25, 50, 75, 100])
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=8)
    ax.set_xticks([math.radians(value) for value in range(0, 360, 45)])
    ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW"], fontsize=9, fontweight="bold")
    ax.grid(color="#e5e7eb", linewidth=0.8)
    ax.set_title("방향별 접근 흐름", pad=18, fontsize=12, fontweight="bold")

    bars = ax.bar(
        [math.radians(angle) for angle in direction_angles],
        scaled_values,
        width=math.radians(34),
        color=[colors[direction] for direction in direction_order],
        alpha=0.82,
        edgecolor="white",
        linewidth=1,
    )
    for bar, direction, count in zip(bars, direction_order, [counts[direction] for direction in direction_order]):
        if count:
            theta = bar.get_x() + bar.get_width() / 2
            radius = bar.get_height() + 8
            ax.text(theta, radius, f"{count}건", fontsize=8, ha="center", va="center", color="#374151")

    ax.text(
        0.5,
        -0.14,
        "가까운 장소일수록 흐름 강도가 크게 반영됩니다.",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=8,
        color="#6b7280",
    )
    fig.tight_layout()
    return fig


def parse_candidate_text(candidate_text: str) -> list[tuple[str, float, float]]:
    candidates = []
    for index, raw_line in enumerate(candidate_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.replace("\t", ",").split(",") if part.strip()]
        if len(parts) == 2:
            name = f"후보지 {index}"
            lat_text, lon_text = parts
        elif len(parts) >= 3:
            name, lat_text, lon_text = parts[:3]
        else:
            continue
        lat = _to_float(lat_text)
        lon = _to_float(lon_text)
        if lat is None or lon is None:
            continue
        candidates.append((name, lat, lon))
    return candidates


def build_comparison_rows(
    *,
    base_name: str,
    base_lat: float,
    base_lon: float,
    base_places: list[dict],
    base_layers: dict[str, dict | None],
    candidate_text: str,
    auto_candidates: bool,
    auto_candidate_count: int,
    vworld: VWorldDataClient,
    categories: list[str],
    radius: int,
) -> list[dict]:
    rows = [
        make_comparison_row(
            name=base_name,
            address="현재 분석 대지",
            lat=base_lat,
            lon=base_lon,
            places=base_places,
            layer_count=sum(1 for response in base_layers.values() if response),
            radius=radius,
            candidate_type="기준 대지",
        )
    ]
    if not vworld.enabled:
        return rows

    candidates = parse_candidate_text(candidate_text)
    if auto_candidates:
        candidates = merge_candidates(candidates, auto_candidate_suggestions(base_places, auto_candidate_count))

    for name, lat, lon in candidates:
        candidate_places: list[dict] = []
        address = "주소 조회 실패"
        try:
            address_response, _ = vworld.coord_to_address_and_region(lon, lat)
            docs = address_response.get("documents") or []
            if docs:
                first = docs[0]
                road = first.get("road_address") or {}
                jibun = first.get("address") or {}
                address = road.get("address_name") or jibun.get("address_name") or address
        except ApiError:
            pass

        for category in categories:
            try:
                candidate_places.extend(vworld.place_search(lon, lat, category, radius=radius).get("documents", []))
            except ApiError:
                continue

        rows.append(
            make_comparison_row(
                name=name,
                address=address,
                lat=lat,
                lon=lon,
                places=candidate_places,
                layer_count=0,
                radius=radius,
                candidate_type=infer_candidate_type(name, candidate_places),
            )
        )
    return rows


def auto_candidate_suggestions(places: list[dict], limit: int) -> list[tuple[str, float, float]]:
    strategy = [
        ("교통 거점 후보", ["대중교통"]),
        ("상권 거점 후보", ["카페", "음식점", "편의점"]),
        ("문화 거점 후보", ["문화시설", "관광명소"]),
        ("생활 편의 후보", ["학교", "병원"]),
    ]
    suggestions: list[tuple[str, float, float]] = []
    used: set[tuple[float, float]] = set()
    for label, categories in strategy:
        row = nearest_place_in_categories(places, categories, used)
        if not row:
            continue
        lat = _to_float(row.get("y"))
        lon = _to_float(row.get("x"))
        if lat is None or lon is None:
            continue
        key = (round(lat, 5), round(lon, 5))
        used.add(key)
        place_name = _short_label(row.get("place_name") or label, 12)
        suggestions.append((f"{label} 검토점 ({place_name} 인근)", lat, lon))
        if len(suggestions) >= limit:
            return suggestions

    for row in sorted(places, key=lambda item: _to_int(item.get("distance"), 999999)):
        lat = _to_float(row.get("y"))
        lon = _to_float(row.get("x"))
        if lat is None or lon is None:
            continue
        key = (round(lat, 5), round(lon, 5))
        if key in used:
            continue
        used.add(key)
        place_name = _short_label(row.get("place_name") or "주변 거점", 12)
        suggestions.append((f"주변 거점 검토점 ({place_name} 인근)", lat, lon))
        if len(suggestions) >= limit:
            break
    return suggestions


def nearest_place_in_categories(places: list[dict], categories: list[str], used: set[tuple[float, float]]) -> dict | None:
    candidates = [
        row
        for row in places
        if row.get("analysis_category") in categories
        and (_to_float(row.get("y")) is not None)
        and (_to_float(row.get("x")) is not None)
        and (round(_to_float(row.get("y")), 5), round(_to_float(row.get("x")), 5)) not in used
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: _to_int(item.get("distance"), 999999))[0]


def merge_candidates(
    manual_candidates: list[tuple[str, float, float]],
    auto_candidates: list[tuple[str, float, float]],
) -> list[tuple[str, float, float]]:
    merged: list[tuple[str, float, float]] = []
    used: set[tuple[float, float]] = set()
    for candidate in manual_candidates + auto_candidates:
        _, lat, lon = candidate
        key = (round(lat, 5), round(lon, 5))
        if key in used:
            continue
        used.add(key)
        merged.append(candidate)
    return merged


def make_comparison_row(
    name: str,
    address: str,
    lat: float,
    lon: float,
    places: list[dict],
    layer_count: int,
    radius: int,
    candidate_type: str,
) -> dict:
    counts: dict[str, int] = {}
    for place in places:
        category = place.get("analysis_category") or "기타"
        counts[category] = counts.get(category, 0) + 1

    transit_count = counts.get("대중교통", 0)
    commerce_count = counts.get("카페", 0) + counts.get("음식점", 0) + counts.get("편의점", 0)
    culture_count = counts.get("문화시설", 0) + counts.get("관광명소", 0)
    diversity_count = sum(1 for value in counts.values() if value > 0)

    nearest_transit = nearest_distance(places, {"대중교통"})
    nearest_commerce = nearest_distance(places, {"카페", "음식점", "편의점"})
    nearest_culture = nearest_distance(places, {"문화시설", "관광명소"})

    transit_score = round(proximity_score(nearest_transit, radius) * 0.68 + count_score(transit_count, 6) * 0.32)
    commerce_score = round(proximity_score(nearest_commerce, radius) * 0.42 + count_score(commerce_count, 14) * 0.58)
    culture_score = round(proximity_score(nearest_culture, radius) * 0.52 + count_score(culture_count, 6) * 0.48)
    balance_score = round(min(100, diversity_count * 17 + min(len(places), 20) * 1.5))
    total_score = round(transit_score * 0.32 + commerce_score * 0.28 + culture_score * 0.22 + balance_score * 0.18)
    interpretation = comparison_interpretation(transit_score, commerce_score, culture_score, balance_score)
    return {
        "후보지": name,
        "주소": address,
        "위도": round(lat, 7),
        "경도": round(lon, 7),
        "유형": candidate_type,
        "주변장소": len(places),
        "공간레이어": layer_count,
        "접근성": transit_score,
        "상권성": commerce_score,
        "문화성": culture_score,
        "균형성": balance_score,
        "종합점수": total_score,
        "대중교통": transit_count,
        "상업편의": commerce_count,
        "문화관광": culture_count,
        "최근접교통": format_distance(nearest_transit),
        "최근접상업": format_distance(nearest_commerce),
        "최근접문화": format_distance(nearest_culture),
        "비교해석": interpretation,
    }


def nearest_distance(places: list[dict], categories: set[str]) -> int | None:
    distances = [
        _to_int(place.get("distance"), 999999)
        for place in places
        if place.get("analysis_category") in categories
    ]
    distances = [distance for distance in distances if distance < 999999]
    return min(distances) if distances else None


def proximity_score(distance: int | None, radius: int) -> float:
    if distance is None:
        return 0
    if distance <= 80:
        return 100
    if distance >= radius:
        return 18
    return max(18, 100 - ((distance - 80) / max(radius - 80, 1)) * 82)


def count_score(count: int, target: int) -> float:
    if count <= 0:
        return 0
    return min(100, math.log1p(count) / math.log1p(target) * 100)


def format_distance(distance: int | None) -> str:
    return "-" if distance is None else f"{distance}m"


def infer_candidate_type(name: str, places: list[dict]) -> str:
    if "교통" in name:
        return "교통 접근형"
    if "상권" in name:
        return "생활 상권형"
    if "문화" in name:
        return "문화 연계형"
    counts: dict[str, int] = {}
    for place in places:
        category = place.get("analysis_category") or "기타"
        counts[category] = counts.get(category, 0) + 1
    commerce_count = counts.get("카페", 0) + counts.get("음식점", 0) + counts.get("편의점", 0)
    culture_count = counts.get("문화시설", 0) + counts.get("관광명소", 0)
    if counts.get("대중교통", 0) >= max(commerce_count, culture_count):
        return "교통 접근형"
    if commerce_count >= culture_count:
        return "생활 상권형"
    return "문화 연계형"


def comparison_interpretation(access: int, commerce: int, culture: int, balance: int) -> str:
    scores = {"접근": access, "상권": commerce, "문화": culture, "균형": balance}
    strongest = max(scores, key=scores.get)
    weakest = min(scores, key=scores.get)
    if scores[strongest] < 35:
        return "주변 데이터가 약해 현장 확인이 우선입니다."
    if scores[weakest] <= 25:
        return f"{strongest} 조건은 좋지만 {weakest} 조건 보완이 필요합니다."
    if balance >= 75:
        return f"{strongest} 조건이 두드러지고 프로그램 균형도 안정적입니다."
    return f"{strongest} 조건을 중심으로 특화 전략을 잡기 좋습니다."


def make_grouped_score_figure(chart_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(7.2, 3.4), dpi=120)
    names = [_short_label(name, 12) for name in chart_df["후보지"].tolist()]
    score_columns = [column for column in ["접근성", "상권성", "문화성", "균형성", "종합점수"] if column in chart_df.columns]
    colors = ["#ef4444", "#2563eb", "#7c3aed", "#10b981", "#111827"]
    x_positions = range(len(names))
    width = min(0.16, 0.72 / max(len(score_columns), 1))
    center = (len(score_columns) - 1) / 2
    offsets = [(idx - center) * width for idx in range(len(score_columns))]
    for column, color, offset in zip(score_columns, colors, offsets):
        values = chart_df[column].tolist()
        bars = ax.bar([x + offset for x in x_positions], values, width=width, label=column, color=color)
        if column == "종합점수":
            for bar, value in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2, value + 2, f"{value}", ha="center", va="bottom", fontsize=8, color="#111827")

    ax.set_ylim(0, 112)
    ax.set_ylabel("점수")
    ax.set_xticks(list(x_positions))
    ax.set_xticklabels(names, fontsize=8)
    ax.grid(axis="y", color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d1d5db")
    ax.spines["bottom"].set_color("#d1d5db")
    ax.legend(loc="upper left", ncols=4, frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


def make_total_rank_figure(chart_df: pd.DataFrame):
    names = [_short_label(name, 15) for name in chart_df["후보지"].tolist()]
    values = chart_df["종합점수"].tolist()
    colors = ["#2563eb" if value == max(values) else "#94a3b8" for value in values]
    height = max(3.0, 0.48 * len(names) + 1.0)
    fig, ax = plt.subplots(figsize=(6.4, height), dpi=120)
    bars = ax.barh(names, values, color=colors, height=0.58)
    ax.set_xlim(0, 100)
    ax.set_xlabel("종합점수")
    ax.set_title("후보지 종합 순위", fontsize=12, fontweight="bold", pad=10)
    ax.grid(axis="x", color="#e5e7eb", linewidth=0.8)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#d1d5db")
    ax.spines["bottom"].set_color("#d1d5db")
    ax.tick_params(axis="y", labelsize=8)
    ax.tick_params(axis="x", labelsize=8)
    for bar, value in zip(bars, values):
        ax.text(min(value + 2, 97), bar.get_y() + bar.get_height() / 2, f"{value}", va="center", fontsize=8, color="#111827")
    fig.tight_layout()
    return fig


def make_score_matrix_figure(chart_df: pd.DataFrame):
    criteria = ["접근성", "상권성", "문화성", "균형성"]
    matrix = chart_df[criteria].to_numpy()
    names = [_short_label(name, 13) for name in chart_df["후보지"].tolist()]
    height = max(3.0, 0.48 * len(names) + 1.0)
    fig, ax = plt.subplots(figsize=(6.8, height), dpi=120)
    image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_title("항목별 점수 매트릭스", fontsize=12, fontweight="bold", pad=10)
    ax.set_xticks(range(len(criteria)))
    ax.set_xticklabels(criteria, fontsize=9)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=8)
    for row_idx in range(matrix.shape[0]):
        for col_idx in range(matrix.shape[1]):
            value = int(matrix[row_idx, col_idx])
            text_color = "white" if value >= 62 else "#0f172a"
            ax.text(col_idx, row_idx, str(value), ha="center", va="center", fontsize=8, color=text_color, fontweight="bold")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8)
    cbar.set_label("점수", fontsize=8)
    fig.tight_layout()
    return fig


def places_to_csv(rows: list[dict]) -> str:
    columns = ["analysis_category", "place_name", "distance", "road_address_name", "address_name", "x", "y"]
    if not rows:
        return pd.DataFrame(columns=["분류", "장소명", "거리", "도로명주소", "지번주소", "경도", "위도"]).to_csv(index=False)
    df = pd.DataFrame(rows)
    for column in columns:
        if column not in df:
            df[column] = ""
    return df[columns].rename(
        columns={
            "analysis_category": "분류",
            "place_name": "장소명",
            "distance": "거리",
            "road_address_name": "도로명주소",
            "address_name": "지번주소",
            "x": "경도",
            "y": "위도",
        }
    ).to_csv(index=False)


def analysis_to_json(analysis, places_rows: list[dict], comparison_rows: list[dict]) -> str:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "site": {
            "name": analysis.site_name,
            "lat": analysis.lat,
            "lon": analysis.lon,
            "radius": analysis.radius,
            "address": analysis.address_text,
            "region": analysis.region_text,
        },
        "place_counts": analysis.place_counts,
        "nearest_places": analysis.nearest_places,
        "spatial_layer_counts": analysis.spatial_layer_counts,
        "population_summary": analysis.population_summary,
        "sun_analysis": serialize_sun_analysis(analysis.sun_analysis),
        "climate_summary": serialize_climate_summary(analysis.climate_summary),
        "insights": analysis.insights,
        "design_keywords": analysis.design_keywords,
        "opportunities": analysis.opportunities,
        "cautions": analysis.cautions,
        "places": places_rows,
        "comparison": comparison_rows,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def serialize_sun_analysis(sun_analysis) -> dict | None:
    if not sun_analysis:
        return None
    return {
        "daylight_hours": sun_analysis.daylight_hours,
        "samples": [
            {
                "label": sample.label,
                "time": sample.time_label,
                "altitude": sample.altitude,
                "azimuth": sample.azimuth,
            }
            for sample in sun_analysis.samples
        ],
        "insights": sun_analysis.insights,
    }


def serialize_climate_summary(climate_summary) -> dict | None:
    if not climate_summary:
        return None
    return {
        "mean_temp": climate_summary.mean_temp,
        "summer_mean_max_temp": climate_summary.summer_mean_max_temp,
        "winter_mean_min_temp": climate_summary.winter_mean_min_temp,
        "annual_precipitation": climate_summary.annual_precipitation,
        "annual_sunshine_hours": climate_summary.annual_sunshine_hours,
        "mean_wind_speed": climate_summary.mean_wind_speed,
        "source_period": climate_summary.source_period,
        "insights": climate_summary.insights,
    }


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    x = math.sin(delta_lon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta_lon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def bearing_to_direction_label(bearing: float) -> str:
    labels = ["북측", "북동측", "동측", "남동측", "남측", "남서측", "서측", "북서측"]
    return labels[int((bearing + 22.5) // 45) % 8]


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(a))


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value, fallback: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _short_label(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit] + "..."


if __name__ == "__main__":
    main()
