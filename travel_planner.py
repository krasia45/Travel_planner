import argparse
import sys
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import requests
from google import genai

# 1. 환경변수 로드
load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
NAVER_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# 에러 목록을 전역에서 관리하여 최종 JSON 및 리포트에 포함시킴
ERROR_LIST = []

def record_error(step, err_type, message):
    """과제 요구 규격에 맞춰 에러 세션을 추적하고 기록하는 함수"""
    error_entry = {
        "step": step,
        "type": err_type,
        "message": message
    }
    ERROR_LIST.append(error_entry)

def save_emergency_json(target_date):
    """프로그램이 예외로 중간에 강제 종료될 때도 에러 배열을 JSON 파일로 즉시 저장하는 함수"""
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        
    emergency_data = {
        "search_date": target_date,
        "recommendation_info": {
            "destination": "데이터 없음",
            "weather_summary": "데이터 없음",
            "local_events": [],
            "recommendation_reason": "데이터 없음"
        },
        "naver_restaurants": [],
        "errors": ERROR_LIST
    }
    
    json_path = os.path.join(results_dir, f"travel_report_{target_date}.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(emergency_data, jf, ensure_ascii=False, indent=4)

# API 키 필수 미설정 조건 검증
if not GEMINI_KEY or not NAVER_ID or not NAVER_SECRET:
    print("[오류] API 키 설정이 누락되었습니다. .env 파일을 확인해 주세요.")
    record_error("init", "AUTH_ERROR", "API credentials missing in .env")
    save_emergency_json("unknown_date")
    sys.exit(1)

# Gemini 클라이언트 초기화
ai_client = genai.Client(api_key=GEMINI_KEY)

def validate_date(date_string):
    """입력 날짜 형식 검증 및 위반 시 에러 기록 후 파일 저장하고 종료"""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
        return date_string
    except ValueError:
        print("\n[오류] 날짜 형식이 올바르지 않습니다!")
        print("사용법: python travel_planner.py --date \"YYYY-MM-DD\"")
        
        # 에러를 기록하고 즉시 results/ 폴더에 에러 JSON 파일을 생성합니다.
        record_error("input_validation", "INVALID_FORMAT", f"Wrong date input: {date_string}")
        save_emergency_json(date_string)
        sys.exit(1)

def ask_gemini_travel_recommendation(travel_date):
    print(f"\n[1/3] 1차 추천 생성 중(LLM)...")
    
    prompt = f"""
    사용자가 {travel_date}에 국내 여행을 가려고 합니다. 
    이 시기에 여행하기 좋은 국내 도시 1곳을 추천하고 관련 정보를 제공해주세요.
    
    반드시 아래의 JSON 포맷으로만 답변해야 하며, 다른 설명이나 markdown 태그(```json 등)는 절대 포함하지 마세요.
    {{
        "recommended_city": "도시 이름만 (예: 제주, 강릉, 부산)",
        "weather": "해당 시기의 일반적인 날씨 요약",
        "events": ["행사나 축제 후보 목록"],
        "reason": "추천 근거를 2~4문장으로 작성"
    }}
    """
    
    for attempt in range(1, 3):
        try:
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            ai_response_text = response.text.strip()
            
            if ai_response_text.startswith("```"):
                lines = ai_response_text.splitlines()
                ai_response_text = "\n".join(lines[1:-1]) if "json" in lines[0] else "\n".join(lines[1:-1])
            
            return json.loads(ai_response_text.strip())
        except Exception as e:
            if attempt == 1:
                print(f" -> [경고] Gemini 1차 파싱 실패. 즉시 재시도 1회를 수행합니다.")
            else:
                record_error("llm_generation", "PARSING_ERROR", f"Gemini Parsing Failed: {str(e)}")
                return None

def search_naver_restaurants(city_name):
    print(f"[2/3] 맛집 검색 중(지도/장소 API)...")
    if not city_name:
        record_error("place_search", "EMPTY_INPUT", "City name is empty.")
        return []

    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET
    }
    params = {
        "query": f"{city_name} 맛집",
        "display": 5,
        "start": 1,
        "sort": "comment"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 401 or response.status_code == 403:
            record_error("place_search", "AUTH_ERROR", f"HTTP {response.status_code}")
            print(f" - 인증 실패({response.status_code}): '데이터 없음' 상태로 계속 진행합니다.")
            return []
        elif response.status_code != 200:
            record_error("place_search", "NETWORK_ERROR", f"HTTP {response.status_code}")
            return []
            
        data = response.json()
        items = data.get("items", [])
        
        if not items:
            record_error("place_search", "EMPTY_RESULT", f"0 results for query={city_name} 맛집")
            return []
            
        restaurant_list = []
        for item in items:
            restaurant_list.append({
                "name": item['title'].replace("<b>", "").replace("</b>", ""),
                "address": item.get("address", "주소 없음"),
                "category": item.get("category", "분류 없음"),
                "url": item.get("link", ""),
                "x": item.get("mapx", "0"),
                "y": item.get("mapy", "0")
            })
        return restaurant_list
    except Exception as e:
        record_error("place_search", "UNKNOWN_ERROR", str(e))
        return []

def generate_markdown_report(valid_date, ai_data, restaurants):
    city = ai_data.get("recommended_city", "데이터 없음")
    weather = ai_data.get("weather", "데이터 없음")
    reason = ai_data.get("reason", "데이터 없음")
    events_list = ai_data.get("events", [])
    
    md = f"# {valid_date} 국내 여행 추천 리포트\n\n"
    md += f"## 추천 지역\n- {city}\n\n"
    md += f"## 추천 이유\n- {reason}\n\n"
    md += f"## 날씨 요약\n- {weather}\n\n"
    
    md += f"## 행사/축제\n"
    if events_list:
        for ev in events_list:
            md += f"- {ev}\n"
    else:
        md += "- 데이터 없음\n"
    md += "\n"
    
    md += f"## 맛집 추천\n"
    if restaurants:
        for idx, r in enumerate(restaurants, 1):
            md += f"### {idx}. {r['name']} ({r['category']})\n"
            md += f"- **주소**: {r['address']}\n"
            if r['url']:
                md += f"- **링크**: [{r['url']}]({r['url']})\n"
            md += f"- **좌표**: X={r['x']}, Y={r['y']}\n\n"
    else:
        md += "- 데이터 없음 (장소 검색 결과 0건)\n\n"
        
    md += f"## 1일 일정 제안\n"
    md += f"- **오전**: {city} 도착 후 주변 명소 및 산책\n"
    md += "- **오후**: 추천 맛집에서 점심 식사 후 대표 축제/행사 참여\n"
    md += "- **저녁**: 지역 야경 명소 관람 후 복귀\n\n"
    
    md += f"## 오류 요약(errors)\n"
    if ERROR_LIST:
        for e in ERROR_LIST:
            md += f"- [{e['step'].upper()}] {e['type']}: {e['message']}\n"
    else:
        md += "- 발생한 오류가 없습니다. (정상 완료)\n"
        
    return md

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Python 응답형 국내 여행지 플래너")
    parser.add_argument("--date", required=True, help="Date format YYYY-MM-DD")
    args = parser.parse_args()
    
    # 1. 날짜 검증
    target_date = validate_date(args.date)
    
    # 2. LLM 질의
    ai_response = ask_gemini_travel_recommendation(target_date)
    
    if not ai_response:
        ai_response = {
            "recommended_city": "데이터 없음",
            "weather": "데이터 없음",
            "events": [],
            "reason": "데이터 없음"
        }
        
    # 3. 맛집 검색
    city_target = ai_response.get("recommended_city")
    restaurant_results = search_naver_restaurants(city_target) if city_target != "데이터 없음" else []
    
    # 4. 규격 바인딩 통합 JSON 구조 생성
    final_json_data = {
        "search_date": target_date,
        "recommendation_info": {
            "destination": ai_response.get("recommended_city"),
            "weather_summary": ai_response.get("weather"),
            "local_events": ai_response.get("events"),
            "recommendation_reason": ai_response.get("reason")
        },
        "naver_restaurants": restaurant_results,
        "errors": ERROR_LIST
    }
    
    # 5. 파일 디렉터리 저장 제어
    print(f"[3/3] 최종 리포트 생성 중...")
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        
    # JSON 원본 파일 저장
    json_path = os.path.join(results_dir, f"travel_report_{target_date}.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(final_json_data, jf, ensure_ascii=False, indent=4)
        
    # Markdown 파일 변환 저장
    markdown_content = generate_markdown_report(target_date, ai_response, restaurant_results)
    md_path = os.path.join(results_dir, f"{target_date}_travel_plan.md")
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write(markdown_content)
        
    print(f"\n완료! {md_path} 를 확인하세요.\n")