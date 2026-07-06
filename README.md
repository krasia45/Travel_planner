# ✈️ Python 응용 API 활용 국내 여행지 추천 프로그램

사용자가 입력한 특정 날짜를 기준으로 최적의 국내 여행지를 추천하고 실시간 맛집 정보를 결합하여 맞춤형 여정 보고서를 자동으로 생성해 주는 CLI 기반 파이썬 애플리케이션입니다.

## 1. 프로그램 개요 및 흐름
1. **CLI 인터페이스**: `argparse` 모듈을 통해 사용자가 입력한 날짜(`--date "YYYY-MM-DD"`)를 수집하고 유효성을 검증합니다.
2. **LLM 지식 연동**: Google Gemini API(`gemini-2.5-flash`)를 활용하여 해당 시즌에 최적화된 추천 도시, 날씨 요약, 축제 정보를 구조화된 JSON 데이터로 1차 추출합니다.
3. **지역 데이터 연동**: 수집된 추천 도시 명칭을 네이버 지역 검색 API(Naver Local Search API)로 전달하여 평점 및 리뷰 기반의 검증된 맛집 5곳을 탐색합니다.
4. **결과 영구 저장**: 수집된 통합 원본 데이터와 가독성을 높인 인쇄용 리포트를 생성하여 `results/` 하위 폴더에 각각 저장합니다.

## 2. 결과물 확인 방법 (`results/` 폴더 구성)
프로그램을 가동하면 프로젝트 루트 하위에 `results/` 디렉터리가 생성되며 다음 파일이 영구 기록됩니다.
- **원본 통합 JSON**: `travel_report_YYYY-MM-DD.json` (1차 추천 결과 + 네이버 데이터 + 오류 수집 스키마 포함)
- **최종 여행 리포트**: `YYYY-MM-DD_travel_plan.md` (마크다운 포맷 보고서)
## 🔑 API Key 설정 방법

이 프로그램은 **Google Gemini API**와 **Naver Search API**를 사용합니다. 
보안을 위해 API 키는 소스 코드에 직접 작성하지 않으며, 프로젝트 루트 디렉토리에 `.env` 파일을 생성하여 환경변수로 관리합니다.

### 1. `.env` 파일 생성
프로젝트 최상위 폴더(travel_planner.py가 있는 위치)에 `.env` 파일을 새로 만들고 아래 내용을 입력합니다.

```env
GEMINI_API_KEY="your_gemini_api_key_here"
NAVER_CLIENT_ID="your_naver_client_id_here"
NAVER_CLIENT_SECRET="your_naver_client_secret_here"

## 3. 실행 방법
```bash
# 가상환경 진입 상태에서 파이썬 스크립트 가동 (날짜 파라미터 필수 입력)
./venv/bin/python travel_planner.py --date "2026-10-15"

