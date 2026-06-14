# AI Site Analysis Assistant

대한민국 좌표를 입력하면 브이월드 공간정보를 중심으로 주소, 행정구역, 주변 장소, 인구 통계, 일조, 기후 데이터를 수집하고 실내건축 설계 초기 단계에 사용할 수 있는 대지 분석 보고서를 생성하는 Streamlit 프로토타입입니다.

## 주요 기능

- 브이월드 기반 주소 및 행정구역 조회
- 브이월드 검색 기반 반경 내 주변 시설 검색
- SGIS 기반 인구 요약 통계 조회
- 브이월드 기반 필지/용도지역 등 공간정보 레이어 조회
- 계절별 태양고도, 방위각, 일장 기반 일조 분석
- Open-Meteo 기반 연간 기온, 강수량, 일조 시간, 풍속 요약
- 주변 시설의 방위와 거리를 반영한 접근 동선 다이어그램
- 복수 후보 좌표의 접근성, 상권성, 문화성 자동 비교
- 규칙 기반 설계 인사이트, 키워드, 주의사항 생성
- HTML 보고서, 주변 장소 CSV, 분석 데이터 JSON 다운로드

## 실행

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m streamlit run app.py
```

## 필요한 API 키

- `VWORLD_API_KEY`: 주소, 행정구역, 주변 장소, 연속지적도, 용도지역 등 국가공간정보를 조회합니다.
- `SGIS_CONSUMER_KEY`, `SGIS_CONSUMER_SECRET`: 좌표 기반 행정구역 코드와 인구 통계를 조회합니다.
- `KAKAO_REST_API_KEY`: 선택 사항입니다. 브이월드 결과가 부족할 때 보조 데이터 소스로 사용할 수 있습니다.
- Open-Meteo 기후 데이터는 별도 API 키 없이 사용합니다.

카카오 로컬 API는 어드민 키가 아니라 REST API 키를 사용합니다. 카카오 응답에 `disabled OPEN_MAP_AND_LOCAL service`가 나오면 Kakao Developers 콘솔에서 해당 앱의 카카오맵/로컬 API 사용 설정을 활성화해야 합니다.

`.env` 파일은 개인 API 키가 들어가므로 Git에 올리지 않습니다.

## 후보지 비교 입력 형식

사이드바의 `비교 후보 좌표`에는 한 줄에 하나씩 후보지를 입력합니다.

```text
후보지 B,37.5700,126.9820
후보지 C,37.5610,126.9770
```

이름을 생략하면 `후보지 1`, `후보지 2`처럼 자동 이름을 붙입니다.

## 서버 배포

이 프로젝트는 Streamlit 기반이라 Render, Railway, Hugging Face Spaces, Streamlit Community Cloud 같은 Python 웹앱 호스팅에 올릴 수 있습니다. 현재 저장소에는 Render 배포용 `render.yaml`, 일반 Python 웹앱용 `Procfile`, 서버 실행용 `.streamlit/config.toml`이 포함되어 있습니다.

Render 기준 절차:

1. GitHub 저장소에 이 프로젝트를 올립니다.
2. Render에서 `New Web Service`를 만들고 저장소를 연결합니다.
3. 환경변수에 `VWORLD_API_KEY`, `SGIS_CONSUMER_KEY`, `SGIS_CONSUMER_SECRET`, 선택적으로 `KAKAO_REST_API_KEY`를 등록합니다.
4. `render.yaml`을 사용하거나, 수동 설정 시 start command를 아래처럼 입력합니다.

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
```

로컬 실행은 기존처럼 `python -m streamlit run app.py`를 사용하면 됩니다.
