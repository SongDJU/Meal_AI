# 식단 계획 및 영양 분석 시스템

AI 기반의 식단 계획 및 영양 분석 시스템입니다. Google Gemini API를 활용하여 메뉴를 분류하고 영양 정보를 추출하며, 주간 식단을 효율적으로 관리할 수 있습니다.

## 주요 기능

1. **식단 계획 생성**
   - 5일/7일 주간 식단 계획 생성
   - 점심/점심저녁 식사 유형 선택
   - 메뉴 중복 최소화
   - Excel 파일로 내보내기

2. **메뉴 데이터베이스 관리**
   - 기본 한식 메뉴 10종 자동 추가
   - 텍스트/엑셀 파일로 메뉴 일괄 추가
   - 메뉴 검색, 수정, 삭제
   - 영양 정보 및 카테고리 관리

3. **메뉴판 분석**
   - 엑셀 파일 업로드로 메뉴판 분석
   - 점심/저녁 시트 자동 병합
   - 영양 정보 분석 및 Excel 파일 생성

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/yourusername/Meal_AI.git
cd Meal_AI
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

4. 환경 변수 설정
`.env` 파일을 생성하고 Google API 키를 설정합니다:
```
GOOGLE_API_KEY=your_api_key_here
```

## 실행 방법

```bash
streamlit run app.py
```

## 사용 방법

1. **식단 계획 생성**
   - "홈 / 식단 계획" 탭에서 기간과 식사 유형 선택
   - "식단표 생성" 버튼 클릭
   - 생성된 식단을 Excel 파일로 다운로드

2. **메뉴 관리**
   - "메뉴 DB" 탭에서 메뉴 추가/수정/삭제
   - 텍스트 입력 또는 엑셀 파일로 메뉴 추가
   - 메뉴 검색 및 영양 정보 수정

3. **메뉴판 분석**
   - "메뉴판 분석" 탭에서 엑셀 파일 업로드
   - "영양 정보 분석" 버튼 클릭
   - 분석 결과를 Excel 파일로 다운로드

## 기술 스택

- Python 3.8+
- Streamlit
- Pandas
- SQLite3
- Google Generative AI (Gemini API)
- XlsxWriter

## 라이선스

MIT License 