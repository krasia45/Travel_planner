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
        "recommendations": [
            {
                "destination": "데이터 없음",
                "weather_summary": "데이터 없음",
                "local_events": [],
                "recommendation_reason": "데이터 없음",
                "restaurants": []
            }
        ],
        "errors": ERROR_LIST
    }
    
    json_path = os.path.join(results_dir, f"travel_report_{target_date}.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(emergency_data, jf, ensure_ascii=False, indent=4)
    print(f"[비상 저장] 예외 상황 발생으로 비상 백업 JSON이 {json_path}에 저장되었습니다.")

def search_naver_restaurants(query_keyword):
    """네이버 지역 검색 API를 이용하여 실시간 맛집을 조회하는 함수 (최소 필드 규격 반영)"""
    if not NAVER_ID or not NAVER_SECRET:
        record_error("Naver API", "Authentication Missing", "네이버 API Client ID 또는 Secret Key 설정이 안 되어 있습니다.")
        return []
        
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET
    }
    params = {
        "query": f"{query_keyword} 맛집",
        "display": 5,  # 권장 5곳 검색
        "start": 1,
        "sort": "comment"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            formatted_items = []
            for item in items:
                title_clean = item.get('title', '').replace('<b>', '').replace('</b>', '')
                formatted_items.append({
                    "name": title_clean,
                    "address": item.get('roadAddress') or item.get('address', '정보 없음'),
                    "category": item.get('category', '음식점'),
                    "url": item.get('link', '')
                })
            return formatted_items
        else:
            record_error(
                "Naver API", 
                "HTTP Error Status", 
                f"네이버 API 요청 실패 (Status Code: {response.status_code}, Response: {response.text})"
            )
            return []
    except Exception as e:
        record_error("Naver API", "Network Exception", f"네이버 API 연동 중 네트워크 예외 발생: {str(e)}")
        return []

def generate_markdown_report(final_json_data, target_date):
    """저장된 JSON 데이터를 기반으로 마크다운 리포트를 생성하는 함수"""
    results_dir = "results"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        
    md_content = f"# 🗺️ {target_date} 국내 여행 추천 리포트\n\n"
    
    for idx, rec in enumerate(final_json_data.get("recommendations", []), 1):
        md_content += f"## 📍 후보 {idx}: {rec.get('destination', '데이터 없음')}\n"
        md_content += f"### 🌤️ 날씨 요약\n- {rec.get('weather_summary', '데이터 없음')}\n\n"
        
        md_content += f"### 🥳 주요 행사/축제\n"
        events = rec.get('local_events', [])
        if events:
            for ev in events:
                md_content += f"- {ev}\n"
        else:
            md_content += f"- 진행 예정인 주요 축제 정보가 없습니다.\n"
        md_content += "\n"
        
        md_content += f"### 💡 추천 이유\n{rec.get('recommendation_reason', '데이터 없음')}\n\n"
        
        md_content += f"### 🍕 추천 맛집 및 먹거리\n"
        restaurants = rec.get('restaurants', [])
        if restaurants:
            for rest in restaurants:
                name = rest.get('name') or rest.get('title', '').replace('<b>', '').replace('</b>', '')
                addr = rest.get('address') or rest.get('roadAddress', '정보 없음')
                cat = rest.get('category', '음식점')
                link = rest.get('url', '')
                link_str = f" - *링크: {link}*" if link else ""
                md_content += f"- **{name}** ({cat}) - *주소: {addr}*{link_str}\n"
        else:
            md_content += f"- 추천 맛집 정보를 불러오지 못했습니다.\n"
        md_content += "\n"
        md_content += "---\n\n"
        
    # 에러 및 예외 로그 세션 추가
    md_content += "## 🛡️ 시스템 에러 및 폴백 로그 요약(errors)\n"
    errors = final_json_data.get("errors", [])
    if errors:
        for err in errors:
            md_content += f"- **[{err.get('step')}]** {err.get('type')}: {err.get('message')}\n"
    else:
        md_content += "- 에러 없이 모든 시스템이 정상적이고 안정적으로 구동되었습니다.\n"
        
    md_path = os.path.join(results_dir, f"{target_date}_travel_plan.md")
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write(md_content)
    print(f"[캐싱/재생성] 마크다운 리포트가 {md_path}에 재생성되었습니다.")

def main():
    # 인자 파싱 및 검증
    parser = argparse.ArgumentParser(description="AI 기반 국내 복수 여행지 추천 및 자동 폴백 플래너")
    parser.add_argument('--date', required=True, help="조회할 날짜를 입력하세요 (형식: YYYY-MM-DD)")
    args = parser.parse_args()
    target_date = args.date
    
    results_dir = "results"
    json_path = os.path.join(results_dir, f"travel_report_{target_date}.json")
    
    # [결과 캐싱 기능] 이미 저장된 원본 JSON이 존재하면 API 호출을 건너뛰고 리포트 재생성
    if os.path.exists(json_path):
        print(f"[캐싱 감지] '{target_date}'에 대한 기존 원본 JSON이 존재합니다. API 호출을 건너뛰고 리포트를 재생성합니다.")
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                cached_data = json.load(jf)
            generate_markdown_report(cached_data, target_date)
            print(f"\n완료 ! results/{target_date}_travel_plan.md 를 확인하세요.\n")
            return
        except Exception as e:
            print(f"[경고] 기존 캐시 파일 로드 중 오류 발생, 새로 실행합니다: {str(e)}")

    # 필수 API 인증 검증 및 강제종료 제어
    if not GEMINI_KEY:
        print("[오류] API 키 설정이 누락되었습니다. .env 파일을 다시 확인해 주세요.")
        record_error("Environment Init", "Key Missing", "GEMINI_API_KEY가 존재하지 않아 프로세스를 중단합니다.")
        save_emergency_json(target_date)
        sys.exit(1)
        
    print(f"[1/3] {target_date} 날짜에 맞는 최적의 복수 국내 여행지 선정 및 분석 시작...")
    
    prompt = f"""
    You are a professional travel planner expert in South Korea. 
    Based on the user's requested date, analyze the seasonal characteristics, weather conditions, and major local festivals or events in South Korea during that specific time.

    Please recommend 2 to 3 optimal travel destinations (cities/counties) in South Korea that are best to visit on this date.
    Additionally, provide a list of 3 recommended local restaurants or famous food items for each destination as a fallback in case external search APIs fail, including name, address, category, and url if available.

    You MUST respond strictly in valid JSON format. Do not include any markdown formatting like ```json or any conversational text. The JSON structure must strictly follow the schema below:

    {{
      "recommended_cities": [
        {{
          "recommended_city": "Name of the city (e.g., '제주', '강릉', '부산')",
          "weather": "A brief summary of the typical weather condition for this destination around the given date.",
          "events": [
            "Candidate event or festival name 1",
            "Candidate event or festival name 2"
          ],
          "reason": "Provide a well-written detailed reason (2-4 sentences in Korean) explaining why this specific destination is highly recommended for this time.",
          "fallback_restaurants": [
            {{
              "name": "Name of the restaurant or food item (e.g., '자매국수')",
              "category": "Food category (e.g., '한식')",
              "address": "Approximate location or main street area",
              "url": ""
            }}
          ]
        }}
      ]
    }}

    User requested date: "{target_date}"
    """
    
    # 2. Gemini 클라이언트 초기화 및 API 호출
    client = genai.Client(api_key=GEMINI_KEY)
    
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        raw_text = response.text.strip()
        ai_response = json.loads(raw_text)
    except json.JSONDecodeError:
        print("[경고] Gemini 1차 파싱 실패. 형식을 정제하여 재시도합니다.")
        record_error("LLM Generation", "Format Warning", "1차 응답 파싱 에러 발생으로 백업 포맷 정제 프로세스를 수행합니다.")
        try:
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()
            ai_response = json.loads(raw_text)
        except Exception as retry_err:
            record_error("LLM Generation", "Parsing Error", f"최종 JSON 파싱 실패: {str(retry_err)}")
            ai_response = {
                "recommended_cities": [
                    {
                        "recommended_city": "데이터 없음",
                        "weather": "데이터 없음",
                        "events": [],
                        "reason": "데이터 없음",
                        "fallback_restaurants": []
                    }
                ]
            }
    except Exception as e:
        record_error("LLM Generation", "API Connection Error", f"Gemini 요청 실패: {str(e)}")
        ai_response = {
            "recommended_cities": [
                {
                    "recommended_city": "데이터 없음",
                    "weather": "데이터 없음",
                    "events": [],
                    "reason": "데이터 없음",
                    "fallback_restaurants": []
                }
            ]
        }
        
    print(f"[2/3] 장소별 실시간 네이버 맛집 연동 및 안정화 데이터 검증 진행 중...")
    
    # 3. 복수 지역 반복문 및 맛집 검색 (폴백 로직 포함)
    final_recommendations = []
    cities_list = ai_response.get("recommended_cities", [])
    
    for city_info in cities_list:
        city_name = city_info.get("recommended_city", "데이터 없음")
        
        restaurant_results = []
        if city_name != "데이터 없음":
            restaurant_results = search_naver_restaurants(city_name)
            
        # 검색 결과가 0건이거나 실패하면 프로그램이 중단되지 않고 AI 백업 데이터로 대체
        if not restaurant_results:
            record_error(
                "Restaurant Search", 
                "Fallback Triggered", 
                f"'{city_name}' 지역의 실시간 네이버 API 결과가 없거나 실패하여 LLM 백업 데이터로 대체 바인딩합니다."
            )
            restaurant_results = city_info.get("fallback_restaurants", [])
            
        final_recommendations.append({
            "destination": city_name,
            "weather_summary": city_info.get("weather", "데이터 없음"),
            "local_events": city_info.get("events", []),
            "recommendation_reason": city_info.get("reason", "데이터 없음"),
            "restaurants": restaurant_results
        })
        
    # 4. 규격 바인딩 통합 JSON 구조 생성
    final_json_data = {
        "search_date": target_date,
        "recommendations": final_recommendations,
        "errors": ERROR_LIST
    }
    
    # 5. 파일 디렉터리 저장 제어
    print(f"[3/3] 최종 여행 마크다운 및 JSON 리포트 생성 중...")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        
    # JSON 원본 파일 저장
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(final_json_data, jf, ensure_ascii=False, indent=4)
        
    # Markdown 파일 변환
    generate_markdown_report(final_json_data, target_date)
    print(f"\n완료 ! results/{target_date}_travel_plan.md 및 JSON 파일을 확인하세요.\n")

if __name__ == "__main__":
    main()