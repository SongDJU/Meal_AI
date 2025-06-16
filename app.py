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
    get_seasonal_menus,
    optimize_nutrition_balance,
    manage_menu_diversity,
    generate_monthly_report,
    auto_update_menu_db,
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
    db_tabs = st.tabs(["메뉴 추가", "메뉴 목록"])

    with db_tabs[0]:
        st.subheader("새 메뉴 추가")

        # 텍스트 입력으로 메뉴 추가
        menu_name = st.text_input("메뉴 이름")
        if st.button("메뉴 추가"):
            if menu_name:
                menu_info = classify_menu(menu_name)
                if menu_info:
                    add_menu(menu_info)
                    st.success(f"메뉴 '{menu_name}'이(가) 추가되었습니다.")
            else:
                st.warning("메뉴 이름을 입력해주세요.")

        # 엑셀 파일로 메뉴 일괄 추가
        st.subheader("엑셀 파일로 메뉴 일괄 추가")
        uploaded_file = st.file_uploader("엑셀 파일 선택", type=["xlsx", "xls"])
        if uploaded_file:
            try:
                df = pd.read_excel(uploaded_file)
                if "name" in df.columns:
                    menu_names = df["name"].tolist()
                    bulk_add(menu_names)
                    st.success(f"{len(menu_names)}개의 메뉴가 추가되었습니다.")
                else:
                    st.error("엑셀 파일에 'name' 열이 필요합니다.")
            except Exception as e:
                st.error(f"파일 처리 중 오류 발생: {str(e)}")

    with db_tabs[1]:
        st.subheader("메뉴 목록")

        # 메뉴 검색
        search_query = st.text_input("메뉴 검색")

        # 모든 메뉴 가져오기
        all_menus = get_all_menus()

        # 검색어가 있는 경우 필터링
        if search_query:
            all_menus = all_menus[
                all_menus["name"].str.contains(search_query, case=False)
            ]

        # 메뉴 목록 표시
        if not all_menus.empty:
            st.dataframe(all_menus)

            # 메뉴 수정/삭제
            selected_menu = st.selectbox(
                "수정/삭제할 메뉴 선택", all_menus["name"].tolist()
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("메뉴 삭제"):
                    delete_menu(selected_menu)
                    st.success(f"메뉴 '{selected_menu}'이(가) 삭제되었습니다.")
                    st.rerun()

            with col2:
                # 영양 정보 수정
                st.subheader("영양 정보 수정")
                nutrition = {
                    "calories": st.number_input(
                        "칼로리",
                        value=all_menus[all_menus["name"] == selected_menu][
                            "calories"
                        ].iloc[0],
                    ),
                    "protein": st.number_input(
                        "단백질",
                        value=all_menus[all_menus["name"] == selected_menu][
                            "protein"
                        ].iloc[0],
                    ),
                    "fat": st.number_input(
                        "지방",
                        value=all_menus[all_menus["name"] == selected_menu]["fat"].iloc[
                            0
                        ],
                    ),
                    "carbs": st.number_input(
                        "탄수화물",
                        value=all_menus[all_menus["name"] == selected_menu][
                            "carbs"
                        ].iloc[0],
                    ),
                    "sodium": st.number_input(
                        "나트륨",
                        value=all_menus[all_menus["name"] == selected_menu][
                            "sodium"
                        ].iloc[0],
                    ),
                }

                if st.button("영양 정보 업데이트"):
                    update_menu_nutrition(selected_menu, nutrition)
                    st.success("영양 정보가 업데이트되었습니다.")
                    st.rerun()

                # 카테고리 수정
                st.subheader("카테고리 수정")
                new_category = st.selectbox(
                    "새 카테고리",
                    ["국/수프", "메인", "사이드", "밥"],
                    index=["국/수프", "메인", "사이드", "밥"].index(
                        all_menus[all_menus["name"] == selected_menu]["category"].iloc[
                            0
                        ]
                    ),
                )

                if st.button("카테고리 업데이트"):
                    update_menu_category(selected_menu, new_category)
                    st.success("카테고리가 업데이트되었습니다.")
                    st.rerun()
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
                    "저녁_사이드2",
                ]

                valid_days = ["월", "화", "수", "목", "금", "토", "일"]
                merged_df = pd.DataFrame(columns=final_columns)

                # 각 시트 처리
                for sheet_name in ["점심", "저녁"]:
                    if sheet_name in sheet_names:
                        try:
                            df = pd.read_excel(uploaded_file, sheet_name=sheet_name)
                            st.write(f"{sheet_name} 시트 데이터 미리보기:")
                            st.dataframe(df.head())
                            st.write(f"{sheet_name} 시트 컬럼명:", df.columns.tolist())

                            # 만약 '요일' 컬럼이 없고, '월'~'일'이 컬럼명에 있다면 전치
                            if "요일" not in df.columns and set(
                                ["월", "화", "수", "목", "금", "토", "일"]
                            ).issubset(set(df.columns)):
                                df = df.set_index(df.columns[0]).T.reset_index()
                                df = df.rename(columns={"index": "요일"})
                                st.info(
                                    f"{sheet_name} 시트가 가로형이어서 세로형으로 변환했습니다."
                                )
                                st.dataframe(df.head())

                            # 컬럼명 정리
                            if sheet_name == "저녁":
                                df = df.rename(
                                    columns={
                                        "잡곡밥": "저녁_잡곡밥",
                                        "국/수프": "저녁_국/수프",
                                        "메인": "저녁_메인",
                                        "사이드1": "저녁_사이드1",
                                        "사이드2": "저녁_사이드2",
                                    }
                                )

                            # 요일 필터링
                            if "요일" not in df.columns:
                                st.error(f"{sheet_name} 시트에 '요일' 컬럼이 없습니다.")
                                continue

                            df = df[df["요일"].isin(valid_days)]

                            if df.empty:
                                st.warning(
                                    f"{sheet_name} 시트에 유효한 요일 데이터가 없습니다."
                                )
                                continue

                            # 데이터 병합
                            for _, row in df.iterrows():
                                try:
                                    day = row["요일"]
                                    if day not in merged_df["요일"].values:
                                        merged_df = pd.concat(
                                            [merged_df, pd.DataFrame([row])],
                                            ignore_index=True,
                                        )
                                    else:
                                        idx = merged_df[merged_df["요일"] == day].index[
                                            0
                                        ]
                                        for col in df.columns:
                                            if pd.isna(merged_df.at[idx, col]):
                                                merged_df.at[idx, col] = row[col]
                                except Exception as e:
                                    st.error(f"행 처리 중 오류 발생: {str(e)}")
                                    st.write("문제가 된 행:", row)
                                    continue
                        except Exception as e:
                            st.error(f"{sheet_name} 시트 처리 중 오류 발생: {str(e)}")
                            continue

                # NaN 값 처리 및 컬럼 정렬
                merged_df = merged_df.fillna("")

                # 최종 컬럼 확인
                st.write("최종 데이터프레임 컬럼:", merged_df.columns.tolist())

                # 누락된 컬럼 확인
                missing_columns = [
                    col for col in final_columns if col not in merged_df.columns
                ]
                if missing_columns:
                    st.warning(f"누락된 컬럼: {missing_columns}")
                    for col in missing_columns:
                        merged_df[col] = ""

                merged_df = merged_df[final_columns]

                if not merged_df.empty:
                    st.write("병합된 데이터:")
                    st.dataframe(merged_df)
                    if st.button("영양 정보 분석"):
                        nutrition_df = analyze_menu_plan(merged_df)
                        st.success("영양 정보 분석이 완료되었습니다.")
                        st.dataframe(nutrition_df)
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
            import traceback

            st.error(f"상세 오류: {traceback.format_exc()}")
