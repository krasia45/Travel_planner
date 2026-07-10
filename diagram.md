```mermaid
sequenceDiagram
    autonumber
    actor User as 사용자 (CLI)
    participant Script as travel_planner.py
    participant Env as 환경변수 (.env)
    participant Gemini as Google GenAI (Gemini)
    participant Naver as 네이버 지역 API
    participant FS as 파일 시스템 (results/)

    User->>Script: python travel_planner.py --date <날짜>
    activate Script
    
    Script->>Env: load_dotenv() 및 API 키 로드
    Env-->>Script: GEMINI_KEY, NAVER_ID/SECRET 반환
    
    Script->>Gemini: 여행 추천 및 이벤트 정보 요청 (LLM)
    alt Gemini 호출 성공
        Gemini-->>Script: 도시 정보 및 Fallback 맛집 데이터 반환
    else Gemini 호출 실패/예외
        Script->>Script: record_error() 에러 기록 및 비상 JSON 저장
    end

    loop 각 추천 도시별 맛집 검색
        Script->>Naver: search_naver_restaurants(city_name)
        alt 네이버 API 성공 및 결과 존재
            Naver-->>Script: 실시간 맛집 리스트 반환
        else 네이버 API 실패 또는 결과 없음 (3번 단계)
            Script->>Script: record_error()를 통한 에러 기록 (ERROR_LIST)
            Script->>Script: AI 백업 데이터(fallback_restaurants)로 대체 바인딩
        end
    end

    Script->>FS: os.makedirs() 및 results/ 디렉터리 확인
    Script->>FS: json.dump() (JSON 원본 저장, errors 포함)
    Script->>FS: write() (최종 마크다운 리포트 저장)
    
    Script-->>User: 리포트 생성 완료 메시지 출력
    deactivate Script
   