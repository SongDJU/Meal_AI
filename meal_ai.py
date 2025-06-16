import sqlite3
import pandas as pd
import os
from dotenv import load_dotenv
import google.generativeai as genai
import streamlit as st
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import random
import xlsxwriter

# 환경 변수 로드 (.env 파일에서 GOOGLE_API_KEY 로드)
load_dotenv()

# Google Gemini API 설정
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
else:
    model = None


def init_db():
    """
    SQLite 데이터베이스 초기화 및 menus 테이블 생성
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # menus 테이블 생성 (없는 경우에만)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS menus (
            name TEXT PRIMARY KEY,
            category TEXT,
            calories REAL,
            protein REAL,
            fat REAL,
            carbs REAL,
            sodium REAL
        )
    """
    )

    conn.commit()
    conn.close()


def get_db_connection():
    """
    데이터베이스 연결 객체 반환
    """
    return sqlite3.connect("meal.db")


def add_menu(menu_info: Dict[str, Any]):
    """
    단일 메뉴 정보를 데이터베이스에 추가

    Args:
        menu_info (Dict[str, Any]): 메뉴 정보를 담은 딕셔너리
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT OR REPLACE INTO menus (name, category, calories, protein, fat, carbs, sodium)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                menu_info["name"],
                menu_info["category"],
                menu_info["calories"],
                menu_info["protein"],
                menu_info["fat"],
                menu_info["carbs"],
                menu_info["sodium"],
            ),
        )
        conn.commit()
    except Exception as e:
        st.error(f"메뉴 추가 중 오류 발생: {str(e)}")
    finally:
        conn.close()


def classify_menu(menu_name: str) -> Dict[str, Any]:
    """
    Gemini API를 사용하여 메뉴를 분류하고 영양 정보 추출

    Args:
        menu_name (str): 분류할 메뉴 이름

    Returns:
        Dict[str, Any]: 메뉴의 카테고리와 영양 정보
    """
    prompt = f"""
    다음 메뉴의 카테고리와 영양 정보를 JSON 형식으로 반환해주세요:
    메뉴: {menu_name}
    
    응답 형식:
    {{
        "name": "{menu_name}",
        "category": "국/수프|메인|사이드|밥",
        "calories": 숫자,
        "protein": 숫자,
        "fat": 숫자,
        "carbs": 숫자,
        "sodium": 숫자
    }}

    주의사항:
    1. 모든 숫자는 정수여야 합니다.
    2. category는 반드시 "국/수프", "메인", "사이드", "밥" 중 하나여야 합니다.
    3. calories는 50-1000 사이의 값이어야 합니다.
    4. protein, fat, carbs는 0-100 사이의 값이어야 합니다.
    5. sodium은 0-2000 사이의 값이어야 합니다.
    6. 1인분을 기준으로 합니다.
    """

    try:
        response = model.generate_content(prompt)

        # 응답에서 JSON 추출
        import re

        json_str = re.search(r"```json\n(.*?)\n```", response.text, re.DOTALL)
        if not json_str:
            json_str = re.search(r"\{.*\}", response.text, re.DOTALL)

        if json_str:
            menu_info = json.loads(
                json_str.group(0)
                if json_str.group(0).startswith("{")
                else json_str.group(1)
            )

            # 필수 필드 검증
            required_fields = [
                "name",
                "category",
                "calories",
                "protein",
                "fat",
                "carbs",
                "sodium",
            ]
            if not all(field in menu_info for field in required_fields):
                raise ValueError("API 응답에 필수 필드가 누락되었습니다.")

            # 값 검증
            if menu_info["category"] not in ["국/수프", "메인", "사이드", "밥"]:
                menu_info["category"] = "메인"  # 기본값 설정

            # 숫자 값 검증 및 변환
            for field in ["calories", "protein", "fat", "carbs", "sodium"]:
                try:
                    menu_info[field] = int(
                        float(str(menu_info[field]).replace(",", ""))
                    )
                except (ValueError, TypeError):
                    # 기본값 설정
                    defaults = {
                        "calories": 300,
                        "protein": 10,
                        "fat": 5,
                        "carbs": 50,
                        "sodium": 500,
                    }
                    menu_info[field] = defaults[field]

            return menu_info
        else:
            raise ValueError("API 응답에서 JSON을 찾을 수 없습니다.")

    except Exception as e:
        print(f"메뉴 분류 중 오류 발생: {str(e)}")
        # 기본값 반환
        return {
            "name": menu_name,
            "category": "메인",
            "calories": 300,
            "protein": 10,
            "fat": 5,
            "carbs": 50,
            "sodium": 500,
        }


def add_default_korean_menus():
    existing_menus = get_all_menus()
    existing_menu_names = (
        set(existing_menus["name"].tolist()) if not existing_menus.empty else set()
    )

    # AI를 통해 한식 메뉴 생성
    prompt = """
    다음 조건에 맞는 한식 메뉴 15개를 생성해주세요:
    1. 구내식당에서 제공하는 메뉴여야 합니다.
    2. 국/수프, 메인, 사이드, 밥 카테고리 중 하나여야 합니다.
    3. 각 메뉴는 기존 메뉴와 중복되지 않아야 합니다.
    4. 각 메뉴의 영양 정보(칼로리, 단백질, 지방, 탄수화물, 나트륨)를 포함해야 합니다.
    5. JSON 형식으로 응답해주세요.
    6. 1인분을 기준으로 합니다.
    7. 구체적인 메뉴 이름을 작성해주세요.
    8. 메뉴 이름은 한국어로 작성해주세요.
    9. 김치를 활용한 음식은 괜찮지만, 김치 자체를 메뉴로 추가하지 말아주세요.
    10. 밥종류도 제외해주세요.

    응답 형식:
    [
        {{
            "name": "메뉴이름",
            "category": "국/수프|메인|사이드|밥",
            "calories": 숫자,
            "protein": 숫자,
            "fat": 숫자,
            "carbs": 숫자,
            "sodium": 숫자
        }},
        ...
    ]

    주의사항:
    1. 모든 숫자는 정수여야 합니다.
    2. category는 반드시 "국/수프", "메인", "사이드", "밥" 중 하나여야 합니다.
    3. calories는 50-1000 사이의 값이어야 합니다.
    4. protein, fat, carbs는 0-100 사이의 값이어야 합니다.
    5. sodium은 0-2000 사이의 값이어야 합니다.
    6. 1인분을 기준으로 합니다.

    기존 메뉴 목록:
    {existing_menus}
    """

    try:
        # Gemini API를 사용하여 메뉴 생성
        response = model.generate_content(
            prompt.format(existing_menus=list(existing_menu_names))
        )

        # 응답에서 JSON 추출
        import re
        import json

        # 응답 텍스트 정리
        response_text = response.text.strip()
        print("API 응답 원본:", response_text)  # 디버깅용

        # JSON 문자열 추출 시도
        json_str = None

        # 방법 1: ```json 블록에서 추출
        json_match = re.search(r"```json\n(.*?)\n```", response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
            print("방법 1로 추출된 JSON:", json_str)  # 디버깅용

        # 방법 2: 일반 JSON 배열에서 추출
        if not json_str:
            json_match = re.search(r"\[\s*\{.*?\}\s*\]", response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0).strip()
                print("방법 2로 추출된 JSON:", json_str)  # 디버깅용

        # 방법 3: 여러 JSON 객체를 배열로 결합
        if not json_str:
            json_objects = re.findall(r"\{[^{}]*\}", response_text)
            if json_objects:
                json_str = f"[{','.join(json_objects)}]"
                print("방법 3으로 추출된 JSON:", json_str)  # 디버깅용

        if json_str:
            try:
                # JSON 문자열 정리
                json_str = re.sub(r"\s+", " ", json_str)  # 여러 공백을 하나로
                json_str = re.sub(r",\s*}", "}", json_str)  # 마지막 쉼표 제거
                json_str = re.sub(r",\s*]", "]", json_str)  # 배열 마지막 쉼표 제거

                print("정리된 JSON 문자열:", json_str)  # 디버깅용

                # JSON 파싱
                menus = json.loads(json_str)
                print("파싱된 메뉴 목록:", menus)  # 디버깅용

                # 메뉴 추가
                added_count = 0
                for menu in menus:
                    if menu["name"] not in existing_menu_names:
                        # 값 검증 및 변환
                        if menu["category"] not in ["국/수프", "메인", "사이드", "밥"]:
                            menu["category"] = "메인"

                        for field in ["calories", "protein", "fat", "carbs", "sodium"]:
                            try:
                                menu[field] = int(
                                    float(str(menu[field]).replace(",", ""))
                                )
                            except (ValueError, TypeError):
                                defaults = {
                                    "calories": 300,
                                    "protein": 10,
                                    "fat": 5,
                                    "carbs": 50,
                                    "sodium": 500,
                                }
                                menu[field] = defaults[field]

                        add_menu(menu)
                        added_count += 1
                        existing_menu_names.add(menu["name"])

                return added_count
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류: {str(e)}")
                print(f"문제가 있는 JSON 문자열: {json_str}")
                print(f"오류 위치: {e.pos}")
                print(f"오류 라인: {e.lineno}")
                print(f"오류 컬럼: {e.colno}")
                return 0
        else:
            print("메뉴 생성 실패: JSON 형식의 응답을 찾을 수 없습니다.")
            print(f"API 응답: {response_text}")
            return 0

    except Exception as e:
        print(f"메뉴 생성 중 오류 발생: {str(e)}")
        print(f"오류 타입: {type(e)}")
        import traceback

        print(f"상세 오류 정보:\n{traceback.format_exc()}")
        return 0


def bulk_add(menu_names: List[str]):
    """
    여러 메뉴를 일괄 추가

    Args:
        menu_names (List[str]): 추가할 메뉴 이름 리스트
    """
    for menu_name in menu_names:
        menu_info = classify_menu(menu_name)
        if menu_info:
            add_menu(menu_info)


def get_all_menus() -> pd.DataFrame:
    """
    데이터베이스의 모든 메뉴 정보를 DataFrame으로 반환
    """
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM menus", conn)
    conn.close()
    return df


def delete_menu(menu_name: str):
    """
    특정 메뉴 삭제

    Args:
        menu_name (str): 삭제할 메뉴 이름
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menus WHERE name = ?", (menu_name,))
    conn.commit()
    conn.close()


def make_plan(meal_type: str = "점심", days: int = 5) -> pd.DataFrame:
    """
    주간 식단 계획 생성

    Args:
        meal_type (str): 식사 유형 ("점심" 또는 "점심저녁")
        days (int): 계획할 일수 (5 또는 7)

    Returns:
        pd.DataFrame: 생성된 식단 계획
    """
    # 데이터베이스에서 모든 메뉴 가져오기
    all_menus = get_all_menus()

    # 요일 리스트 생성
    weekdays = ["월", "화", "수", "목", "금", "토", "일"][:days]

    # 메뉴 카테고리별 분류
    available_soup = all_menus[all_menus["category"] == "국/수프"]["name"].tolist()
    available_main = all_menus[all_menus["category"] == "메인"]["name"].tolist()
    available_side = all_menus[all_menus["category"] == "사이드"]["name"].tolist()

    # 사용된 메뉴 추적
    used_menus = set()

    # 식단 계획 데이터 저장
    plan_data = []

    for day in weekdays:
        day_plan = {"요일": day}

        # 점심 메뉴 선택
        day_plan["잡곡밥"] = "잡곡밥"  # 항상 잡곡밥 포함

        # 국/수프 선택
        available_soup_filtered = [s for s in available_soup if s not in used_menus]
        if available_soup_filtered:
            day_plan["국/수프"] = random.choice(available_soup_filtered)
        else:
            day_plan["국/수프"] = random.choice(available_soup)
        used_menus.add(day_plan["국/수프"])

        # 메인 메뉴 선택
        available_main_filtered = [m for m in available_main if m not in used_menus]
        if available_main_filtered:
            day_plan["메인"] = random.choice(available_main_filtered)
        else:
            day_plan["메인"] = random.choice(available_main)
        used_menus.add(day_plan["메인"])

        # 사이드 메뉴 선택 (2개)
        for i in range(2):
            available_side_filtered = [s for s in available_side if s not in used_menus]
            if available_side_filtered:
                day_plan[f"사이드{i+1}"] = random.choice(available_side_filtered)
            else:
                day_plan[f"사이드{i+1}"] = random.choice(available_side)
            used_menus.add(day_plan[f"사이드{i+1}"])

        # 저녁 메뉴 선택 (점심저녁 타입인 경우)
        if meal_type == "점심저녁":
            day_plan["저녁_잡곡밥"] = "잡곡밥"

            # 저녁 국/수프
            available_soup_filtered = [s for s in available_soup if s not in used_menus]
            if available_soup_filtered:
                day_plan["저녁_국/수프"] = random.choice(available_soup_filtered)
            else:
                day_plan["저녁_국/수프"] = random.choice(available_soup)
            used_menus.add(day_plan["저녁_국/수프"])

            # 저녁 메인
            available_main_filtered = [m for m in available_main if m not in used_menus]
            if available_main_filtered:
                day_plan["저녁_메인"] = random.choice(available_main_filtered)
            else:
                day_plan["저녁_메인"] = random.choice(available_main)
            used_menus.add(day_plan["저녁_메인"])

            # 저녁 사이드 (2개)
            for i in range(2):
                available_side_filtered = [
                    s for s in available_side if s not in used_menus
                ]
                if available_side_filtered:
                    day_plan[f"저녁_사이드{i+1}"] = random.choice(
                        available_side_filtered
                    )
                else:
                    day_plan[f"저녁_사이드{i+1}"] = random.choice(available_side)
                used_menus.add(day_plan[f"저녁_사이드{i+1}"])

        plan_data.append(day_plan)

    return pd.DataFrame(plan_data)


def export_plan(plan_df: pd.DataFrame, filename: str) -> str:
    """
    식단 계획을 Excel 파일로 내보내기

    Args:
        plan_df (pd.DataFrame): 식단 계획 데이터
        filename (str): 저장할 파일 이름

    Returns:
        str: 저장된 파일 경로
    """
    # exports 디렉토리 생성
    os.makedirs("exports", exist_ok=True)

    # 파일 경로 설정
    filepath = os.path.join(
        "exports", f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    )

    # Excel 작성기 생성
    with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
        # 점심 시트 작성
        lunch_df = plan_df[["요일", "잡곡밥", "국/수프", "메인", "사이드1", "사이드2"]]
        lunch_df = lunch_df.set_index("요일").T  # 요일을 열로 변경
        lunch_df.to_excel(writer, sheet_name="점심")

        # 저녁 시트 작성 (있는 경우)
        if "저녁_잡곡밥" in plan_df.columns:
            dinner_df = plan_df[
                [
                    "요일",
                    "저녁_잡곡밥",
                    "저녁_국/수프",
                    "저녁_메인",
                    "저녁_사이드1",
                    "저녁_사이드2",
                ]
            ]
            dinner_df = dinner_df.set_index("요일").T  # 요일을 열로 변경
            dinner_df.to_excel(writer, sheet_name="저녁")

        # 영양 정보 분석 및 저장
        nutrition_df = analyze_menu_plan(plan_df)

        # 영양소 컬럼명을 한국어로 변경
        nutrition_df = nutrition_df.rename(
            columns={
                "calories": "칼로리",
                "protein": "단백질",
                "fat": "지방",
                "carbs": "탄수화물",
                "sodium": "나트륨",
            }
        )

        # 영양 정보 피벗 테이블 생성
        nutrition_pivot = nutrition_df.pivot_table(
            index="구분",
            columns="요일",
            values=["칼로리", "단백질", "지방", "탄수화물", "나트륨"],
            aggfunc="sum",
        )
        nutrition_pivot.to_excel(writer, sheet_name="영양 정보")

        # 일일 영양소 합계 계산 및 저장
        daily_nutrition = nutrition_df.groupby("요일").agg(
            {
                "칼로리": "sum",
                "단백질": "sum",
                "지방": "sum",
                "탄수화물": "sum",
                "나트륨": "sum",
            }
        )
        daily_nutrition = daily_nutrition.T  # 요일을 열로 변경
        daily_nutrition.to_excel(writer, sheet_name="일일 영양소 합계")

    return filepath


def analyze_menu_plan(plan_df: pd.DataFrame) -> pd.DataFrame:
    """
    식단 계획의 영양 정보 분석

    Args:
        plan_df (pd.DataFrame): 식단 계획 데이터

    Returns:
        pd.DataFrame: 영양 정보 분석 결과
    """
    # 데이터베이스의 기존 메뉴 가져오기
    existing_menus = set(get_all_menus()["name"])

    # 영양 정보 데이터 저장
    nutrition_data = []

    # 점심 메뉴 분석
    lunch_columns = ["잡곡밥", "국/수프", "메인", "사이드1", "사이드2"]
    for _, row in plan_df.iterrows():
        for col in lunch_columns:
            menu_name = row[col]
            if menu_name not in existing_menus:
                menu_info = classify_menu(menu_name)
                if menu_info:
                    add_menu(menu_info)

            menu_data = get_all_menus()[get_all_menus()["name"] == menu_name].iloc[0]
            nutrition_data.append(
                {
                    "요일": row["요일"],
                    "구분": f"점심_{col}",
                    "메뉴": menu_name,
                    "칼로리": menu_data["calories"],
                    "단백질": menu_data["protein"],
                    "지방": menu_data["fat"],
                    "탄수화물": menu_data["carbs"],
                    "나트륨": menu_data["sodium"],
                }
            )

    # 저녁 메뉴 분석 (있는 경우)
    if "저녁_잡곡밥" in plan_df.columns:
        dinner_columns = [
            "저녁_잡곡밥",
            "저녁_국/수프",
            "저녁_메인",
            "저녁_사이드1",
            "저녁_사이드2",
        ]
        for _, row in plan_df.iterrows():
            for col in dinner_columns:
                menu_name = row[col]
                if menu_name not in existing_menus:
                    menu_info = classify_menu(menu_name)
                    if menu_info:
                        add_menu(menu_info)

                menu_data = get_all_menus()[get_all_menus()["name"] == menu_name].iloc[
                    0
                ]
                nutrition_data.append(
                    {
                        "요일": row["요일"],
                        "구분": f"저녁_{col}",
                        "메뉴": menu_name,
                        "칼로리": menu_data["calories"],
                        "단백질": menu_data["protein"],
                        "지방": menu_data["fat"],
                        "탄수화물": menu_data["carbs"],
                        "나트륨": menu_data["sodium"],
                    }
                )

    return pd.DataFrame(nutrition_data)


def update_menu_nutrition(menu_name: str, nutrition: Dict[str, float]):
    """
    메뉴의 영양 정보 업데이트

    Args:
        menu_name (str): 업데이트할 메뉴 이름
        nutrition (Dict[str, float]): 새로운 영양 정보
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE menus
        SET calories = ?, protein = ?, fat = ?, carbs = ?, sodium = ?
        WHERE name = ?
    """,
        (
            nutrition["calories"],
            nutrition["protein"],
            nutrition["fat"],
            nutrition["carbs"],
            nutrition["sodium"],
            menu_name,
        ),
    )

    conn.commit()
    conn.close()


def update_menu_category(menu_name: str, category: str):
    """
    메뉴의 카테고리 업데이트

    Args:
        menu_name (str): 업데이트할 메뉴 이름
        category (str): 새로운 카테고리
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE menus
        SET category = ?
        WHERE name = ?
    """,
        (category, menu_name),
    )

    conn.commit()
    conn.close()


def get_seasonal_menus() -> List[Dict[str, Any]]:
    """
    계절별 메뉴 추천을 위해 AI를 활용하여 메뉴 생성

    Returns:
        List[Dict[str, Any]]: 계절별 추천 메뉴 목록
    """
    current_month = datetime.now().month
    season = (
        "봄"
        if 3 <= current_month <= 5
        else (
            "여름"
            if 6 <= current_month <= 8
            else "가을" if 9 <= current_month <= 11 else "겨울"
        )
    )

    prompt = f"""
    {season}에 어울리는 한식 메뉴 5개를 추천해주세요.
    계절에 맞는 제철 식재료를 활용한 메뉴여야 합니다.
    
    응답 형식:
    [
        {{
            "name": "메뉴이름",
            "category": "국/수프|메인|사이드|밥",
            "calories": 숫자,
            "protein": 숫자,
            "fat": 숫자,
            "carbs": 숫자,
            "sodium": 숫자,
            "seasonal_ingredients": ["제철재료1", "제철재료2", ...]
        }},
        ...
    ]
    """

    try:
        response = model.generate_content(prompt)
        menus = json.loads(response.text)
        return menus
    except Exception as e:
        print(f"계절별 메뉴 생성 중 오류 발생: {str(e)}")
        return []


def optimize_nutrition_balance(plan_df: pd.DataFrame) -> pd.DataFrame:
    """
    식단 계획의 영양 균형을 최적화

    Args:
        plan_df (pd.DataFrame): 현재 식단 계획

    Returns:
        pd.DataFrame: 최적화된 식단 계획
    """
    # 현재 영양 정보 분석
    current_nutrition = analyze_menu_plan(plan_df)
    daily_nutrition = current_nutrition.groupby("요일").agg(
        {
            "calories": "sum",
            "protein": "sum",
            "fat": "sum",
            "carbs": "sum",
            "sodium": "sum",
        }
    )

    # 목표 영양소 기준
    target_nutrition = {
        "calories": 2000,  # 일일 권장 칼로리
        "protein": 60,  # 일일 권장 단백질(g)
        "fat": 65,  # 일일 권장 지방(g)
        "carbs": 250,  # 일일 권장 탄수화물(g)
        "sodium": 2000,  # 일일 권장 나트륨(mg)
    }

    # 영양소 균형이 맞지 않는 요일 찾기
    imbalanced_days = []
    for day in daily_nutrition.index:
        day_nutrition = daily_nutrition.loc[day]
        if any(
            abs(day_nutrition[nutrient] - target_nutrition[nutrient])
            / target_nutrition[nutrient]
            > 0.2
            for nutrient in target_nutrition
        ):
            imbalanced_days.append(day)

    # 균형이 맞지 않는 요일의 메뉴 최적화
    for day in imbalanced_days:
        day_nutrition = daily_nutrition.loc[day]
        for nutrient in target_nutrition:
            if day_nutrition[nutrient] < target_nutrition[nutrient] * 0.8:
                # 부족한 영양소를 보완할 수 있는 메뉴 찾기
                alternative_menus = get_all_menus()
                alternative_menus = alternative_menus[
                    alternative_menus[nutrient] > day_nutrition[nutrient] / 3
                ]
                if not alternative_menus.empty:
                    # 현재 메뉴와 다른 카테고리의 메뉴 선택
                    current_categories = set(
                        plan_df.loc[plan_df["요일"] == day].iloc[0].drop("요일").values
                    )
                    alternative_menus = alternative_menus[
                        ~alternative_menus["category"].isin(current_categories)
                    ]
                    if not alternative_menus.empty:
                        new_menu = alternative_menus.sample(1).iloc[0]
                        # 메뉴 교체
                        for col in plan_df.columns:
                            if (
                                col != "요일"
                                and plan_df.loc[plan_df["요일"] == day, col].iloc[0]
                                in current_categories
                            ):
                                plan_df.loc[plan_df["요일"] == day, col] = new_menu[
                                    "name"
                                ]
                                break

    return plan_df


def manage_menu_diversity(plan_df: pd.DataFrame) -> pd.DataFrame:
    """
    메뉴의 다양성을 관리하고 중복을 최소화

    Args:
        plan_df (pd.DataFrame): 현재 식단 계획

    Returns:
        pd.DataFrame: 다양성이 개선된 식단 계획
    """
    # 메뉴 사용 빈도 계산
    menu_counts = {}
    for col in plan_df.columns:
        if col != "요일":
            for menu in plan_df[col]:
                menu_counts[menu] = menu_counts.get(menu, 0) + 1

    # 2회 이상 사용된 메뉴 찾기
    overused_menus = {menu: count for menu, count in menu_counts.items() if count >= 2}

    # 중복 메뉴 교체
    for menu, count in overused_menus.items():
        # 대체 가능한 메뉴 찾기
        menu_category = get_all_menus()[get_all_menus()["name"] == menu][
            "category"
        ].iloc[0]
        alternative_menus = get_all_menus()[
            (get_all_menus()["category"] == menu_category)
            & (get_all_menus()["name"] != menu)
        ]

        if not alternative_menus.empty:
            # 중복 메뉴가 있는 위치 찾기
            for col in plan_df.columns:
                if col != "요일":
                    for idx in plan_df[plan_df[col] == menu].index:
                        new_menu = alternative_menus.sample(1).iloc[0]["name"]
                        plan_df.at[idx, col] = new_menu

    return plan_df


def generate_monthly_report(plan_df: pd.DataFrame) -> str:
    """
    월간 식단 보고서 생성

    Args:
        plan_df (pd.DataFrame): 식단 계획 데이터

    Returns:
        str: 생성된 보고서 파일 경로
    """
    # 보고서 디렉토리 생성
    os.makedirs("reports", exist_ok=True)

    # 파일 경로 설정
    filepath = os.path.join(
        "reports", f"월간_식단_보고서_{datetime.now().strftime('%Y%m')}.xlsx"
    )

    # Excel 작성기 생성
    with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
        # 기본 식단 계획
        plan_df.to_excel(writer, sheet_name="식단 계획", index=False)

        # 영양 정보 분석
        nutrition_df = analyze_menu_plan(plan_df)
        nutrition_df.to_excel(writer, sheet_name="영양 정보", index=False)

        # 메뉴 사용 통계
        menu_stats = pd.DataFrame()
        for col in plan_df.columns:
            if col != "요일":
                menu_counts = plan_df[col].value_counts()
                menu_stats[col] = menu_counts

        menu_stats.to_excel(writer, sheet_name="메뉴 사용 통계")

        # 영양소 목표 달성률
        daily_nutrition = nutrition_df.groupby("요일").agg(
            {
                "calories": "sum",
                "protein": "sum",
                "fat": "sum",
                "carbs": "sum",
                "sodium": "sum",
            }
        )

        target_nutrition = {
            "calories": 2000,
            "protein": 60,
            "fat": 65,
            "carbs": 250,
            "sodium": 2000,
        }

        achievement_rate = pd.DataFrame()
        for nutrient in target_nutrition:
            achievement_rate[nutrient] = (
                daily_nutrition[nutrient] / target_nutrition[nutrient] * 100
            ).round(1)

        achievement_rate.to_excel(writer, sheet_name="영양소 목표 달성률")

    return filepath


def auto_update_menu_db():
    """
    메뉴 데이터베이스 자동 업데이트
    - 새로운 트렌드 메뉴 추가
    - 계절별 메뉴 업데이트
    - 인기도 기반 메뉴 관리
    """
    # 계절별 메뉴 추가
    seasonal_menus = get_seasonal_menus()
    for menu in seasonal_menus:
        if menu["name"] not in set(get_all_menus()["name"]):
            add_menu(menu)

    # 트렌드 메뉴 생성
    prompt = """
    최근 인기 있는 한식 메뉴 5개를 추천해주세요.
    트렌디하고 현대적인 메뉴여야 합니다.
    
    응답 형식:
    [
        {{
            "name": "메뉴이름",
            "category": "국/수프|메인|사이드|밥",
            "calories": 숫자,
            "protein": 숫자,
            "fat": 숫자,
            "carbs": 숫자,
            "sodium": 숫자,
            "trend_reason": "인기 이유"
        }},
        ...
    ]
    """

    try:
        response = model.generate_content(prompt)
        trend_menus = json.loads(response.text)
        for menu in trend_menus:
            if menu["name"] not in set(get_all_menus()["name"]):
                add_menu(menu)
    except Exception as e:
        print(f"트렌드 메뉴 생성 중 오류 발생: {str(e)}")

    # 인기도가 낮은 메뉴 제거 (선택적)
    menu_usage = pd.DataFrame()
    for col in get_all_menus().columns:
        if col != "name":
            menu_usage[col] = get_all_menus()[col].value_counts()

    # 3개월 이상 사용되지 않은 메뉴 제거
    unused_menus = menu_usage[menu_usage.sum(axis=1) == 0].index
    for menu in unused_menus:
        delete_menu(menu)


if __name__ == "__main__":
    # 데이터베이스 초기화
    init_db()

    # Streamlit UI 설정
    st.title("식단 계획 및 영양 분석 시스템")

    # 기본 한식 메뉴 추가 버튼
    if st.button("기본 한식 메뉴 추가"):
        added_count = add_default_korean_menus()
        st.success(f"{added_count}개의 새로운 한식 메뉴가 추가되었습니다.")

    # 메뉴판 업로드 섹션
    st.header("메뉴판 분석")
    st.markdown(
        """
    엑셀 파일을 업로드하여 메뉴판을 분석하세요.
    파일은 '점심'과 '저녁' 시트를 포함해야 합니다.
    """
    )

    uploaded_file = st.file_uploader("엑셀 파일 선택", type=["xlsx", "xls"])

    if uploaded_file:
        try:
            # 엑셀 파일 파싱
            excel_file = pd.ExcelFile(uploaded_file)
            sheet_names = excel_file.sheet_names

            if not any(sheet in sheet_names for sheet in ["점심", "저녁"]):
                st.error("'점심' 또는 '저녁' 시트가 필요합니다.")
            else:
                # 데이터 병합을 위한 준비
                final_columns = [
                    "요일",
                    "잡곡밥",
                    "국/수프",
                    "메인",
                    "사이드1",
                    "사이드2",
                    "저녁_잡곡밥",
                    "저녁_국/수프",
                    "저녁_메인",
                    "저녁_사이드1",
                ]

                valid_days = ["월", "화", "수", "목", "금", "토", "일"]
                merged_df = pd.DataFrame(columns=final_columns)

                # 각 시트 처리
                for sheet_name in ["점심", "저녁"]:
                    if sheet_name in sheet_names:
                        df = pd.read_excel(uploaded_file, sheet_name=sheet_name)

                        # 컬럼명 정리
                        if sheet_name == "저녁":
                            df = df.rename(
                                columns={
                                    "잡곡밥": "저녁_잡곡밥",
                                    "국/수프": "저녁_국/수프",
                                    "메인": "저녁_메인",
                                    "사이드1": "저녁_사이드1",
                                }
                            )

                        # 요일 필터링
                        df = df[df["요일"].isin(valid_days)]

                        # 데이터 병합
                        for _, row in df.iterrows():
                            day = row["요일"]
                            if day not in merged_df["요일"].values:
                                merged_df = pd.concat(
                                    [merged_df, pd.DataFrame([row])], ignore_index=True
                                )
                            else:
                                idx = merged_df[merged_df["요일"] == day].index[0]
                                for col in df.columns:
                                    if pd.isna(merged_df.at[idx, col]):
                                        merged_df.at[idx, col] = row[col]

                # NaN 값 처리 및 컬럼 정렬
                merged_df = merged_df.fillna("")
                merged_df = merged_df[final_columns]

                if not merged_df.empty:
                    st.dataframe(merged_df)

                    if st.button("영양 정보 분석"):
                        nutrition_df = analyze_menu_plan(merged_df)
                        st.success("영양 정보 분석이 완료되었습니다.")
                        st.dataframe(nutrition_df)

                        # Excel 파일로 내보내기
                        filepath = export_plan(merged_df, "식단_계획")
                        with open(filepath, "rb") as f:
                            st.download_button(
                                label="Excel 파일 다운로드",
                                data=f,
                                file_name=os.path.basename(filepath),
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            )
                else:
                    st.error("유효한 데이터가 없습니다.")

        except Exception as e:
            st.error(f"파일 처리 중 오류 발생: {str(e)}")
