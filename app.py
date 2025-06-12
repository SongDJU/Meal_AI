import streamlit as st
import pandas as pd
from meal_ai import (
    init_db,
    add_default_korean_menus,
    make_plan,
    export_plan,
    get_all_menus,
    add_menu,
    delete_menu,
    update_menu_nutrition,
    update_menu_category,
    bulk_add,
    classify_menu,
)
import os
import google.generativeai as genai

# 페이지 설정
st.set_page_config(
    page_title="식단 계획 및 영양 분석 시스템", page_icon="🍱", layout="wide"
)

# 데이터베이스 초기화
init_db()

# 사이드바 - API 키 확인
st.sidebar.title("API 키 확인")
api_key = st.sidebar.text_input("Google API 키", type="password")
if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key
    genai.configure(api_key=api_key)
    st.sidebar.success("API 키가 설정되었습니다.")
else:
    st.sidebar.warning("Google API 키를 입력해주세요.")

# 기본 한식 메뉴 추가 버튼
if st.sidebar.button("기본 한식 메뉴 추가"):
    added_count = add_default_korean_menus()
    st.sidebar.success(f"{added_count}개의 새로운 한식 메뉴가 추가되었습니다.")

# 메인 탭
tab1, tab2, tab3 = st.tabs(["홈 / 식단 계획", "메뉴 DB", "메뉴판 분석"])

# 홈 / 식단 계획 탭
with tab1:
    st.header("식단 계획 생성")

    col1, col2 = st.columns(2)

    with col1:
        days = st.radio("기간 선택", ["5일", "7일"], horizontal=True)
        days = int(days[0])

    with col2:
        meal_type = st.radio("식사 유형", ["점심", "점심저녁"], horizontal=True)

    if st.button("식단표 생성"):
        plan_df = make_plan(meal_type=meal_type, days=days)
        st.dataframe(plan_df)

        # Excel 파일로 내보내기
        filepath = export_plan(plan_df, "식단_계획")
        with open(filepath, "rb") as f:
            st.download_button(
                label="Excel 파일 다운로드",
                data=f,
                file_name=filepath.split("/")[-1],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

# 메뉴 DB 탭
with tab2:
    st.header("메뉴 데이터베이스 관리")

    sub_tab1, sub_tab2 = st.tabs(["메뉴 추가", "메뉴 관리"])

    # 메뉴 추가 탭
    with sub_tab1:
        st.subheader("새 메뉴 추가")

        # 텍스트 입력으로 메뉴 추가
        menu_input = st.text_area("메뉴 이름 입력 (한 줄에 하나씩)")
        if st.button("메뉴 추가"):
            if menu_input:
                menu_names = [
                    name.strip() for name in menu_input.split("\n") if name.strip()
                ]
                added_menus = []
                for menu_name in menu_names:
                    menu_info = classify_menu(menu_name)
                    if menu_info:
                        add_menu(menu_info)
                        added_menus.append(menu_info)

                if added_menus:
                    st.success(f"{len(added_menus)}개의 메뉴가 추가되었습니다.")
                    st.write("추가된 메뉴 정보:")
                    added_df = pd.DataFrame(added_menus)
                    st.dataframe(added_df)
                else:
                    st.error("메뉴 추가에 실패했습니다.")

        # 엑셀 파일로 메뉴 추가
        st.subheader("엑셀 파일로 메뉴 추가")
        uploaded_file = st.file_uploader(
            "엑셀 파일 선택", type=["xlsx", "xls"], key="menu_upload"
        )
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                if "name" in df.columns:
                    menu_names = df["name"].tolist()
                    added_menus = []
                    for menu_name in menu_names:
                        menu_info = classify_menu(menu_name)
                        if menu_info:
                            add_menu(menu_info)
                            added_menus.append(menu_info)

                    if added_menus:
                        st.success(f"{len(added_menus)}개의 메뉴가 추가되었습니다.")
                        st.write("추가된 메뉴 정보:")
                        added_df = pd.DataFrame(added_menus)
                        st.dataframe(added_df)
                    else:
                        st.error("메뉴 추가에 실패했습니다.")
                else:
                    st.error("엑셀 파일에 'name' 컬럼이 필요합니다.")
            except Exception as e:
                st.error(f"파일 처리 중 오류 발생: {str(e)}")

    # 메뉴 관리 탭
    with sub_tab2:
        st.subheader("메뉴 목록")

        # 모든 메뉴 가져오기
        menus_df = get_all_menus()

        if not menus_df.empty:
            # 메뉴 검색
            search_term = st.text_input("메뉴 검색")
            if search_term:
                menus_df = menus_df[
                    menus_df["name"].str.contains(search_term, case=False)
                ]

            # 메뉴 목록 표시
            st.dataframe(menus_df)

            # 메뉴 수정/삭제
            st.subheader("메뉴 수정/삭제")
            selected_menu = st.selectbox("메뉴 선택", menus_df["name"].tolist())

            if selected_menu:
                menu_data = menus_df[menus_df["name"] == selected_menu].iloc[0]

                col1, col2 = st.columns(2)

                with col1:
                    st.write("영양 정보 수정")
                    new_calories = st.number_input(
                        "칼로리", value=float(menu_data["calories"])
                    )
                    new_protein = st.number_input(
                        "단백질", value=float(menu_data["protein"])
                    )
                    new_fat = st.number_input("지방", value=float(menu_data["fat"]))
                    new_carbs = st.number_input(
                        "탄수화물", value=float(menu_data["carbs"])
                    )
                    new_sodium = st.number_input(
                        "나트륨", value=float(menu_data["sodium"])
                    )

                    if st.button("영양 정보 업데이트"):
                        nutrition = {
                            "calories": new_calories,
                            "protein": new_protein,
                            "fat": new_fat,
                            "carbs": new_carbs,
                            "sodium": new_sodium,
                        }
                        update_menu_nutrition(selected_menu, nutrition)
                        st.success("영양 정보가 업데이트되었습니다.")

                with col2:
                    st.write("카테고리 수정")
                    new_category = st.selectbox(
                        "카테고리",
                        ["국/수프", "메인", "사이드", "밥"],
                        index=["국/수프", "메인", "사이드", "밥"].index(
                            menu_data["category"]
                        ),
                    )

                    if st.button("카테고리 업데이트"):
                        update_menu_category(selected_menu, new_category)
                        st.success("카테고리가 업데이트되었습니다.")

                if st.button("메뉴 삭제", type="primary"):
                    delete_menu(selected_menu)
                    st.success("메뉴가 삭제되었습니다.")
        else:
            st.info("등록된 메뉴가 없습니다.")

# 메뉴판 분석 탭
with tab3:
    st.header("메뉴판 분석")
    st.markdown(
        """
    엑셀 파일을 업로드하여 메뉴판을 분석하세요.
    파일은 '점심'과 '저녁' 시트를 포함해야 합니다.
    """
    )

    uploaded_file = st.file_uploader(
        "엑셀 파일 선택", type=["xlsx", "xls"], key="menu_analysis_upload"
    )

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
                        from meal_ai import analyze_menu_plan

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
