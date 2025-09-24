from selenium import webdriver as wd
from selenium.webdriver.chrome.service import Service as sv
from webdriver_manager.chrome import ChromeDriverManager as cdm 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
import os
from sqlalchemy import text


# SQLite 데이터베이스 라이브러리 추가
import sqlite3

# 현재 스크래핑할 사이트를 구분하는 변수 (현대차: 0)
SOURCE_ID = 0  # 현대: 0, 기아: 1

url = 'https://www.hyundai.com/kr/ko/faq.html'
service = sv(cdm().install())
driver = wd.Chrome(service=service)

wait = WebDriverWait(driver, 10)
# faq_data 리스트의 튜플 구조를 (카테고리, 질문, 답변, 출처)로 변경
faq_data = []

try:
    print("웹사이트에 접속 중...")
    driver.get(url)
    driver.maximize_window()
    time.sleep(2)

    page_number = 1
    while True:
        print(f"\n--- {page_number} 페이지 ---")

        # FAQ 항목 로드
        faq_items = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.ui_accordion > dl"))
        )
        print(f"FAQ {len(faq_items)}개 발견")

        for item in faq_items:
            try:
                item_index = faq_items.index(item)
                
                cat_text = item.find_element(By.CSS_SELECTOR, "dt i").text.strip()
                q_text = item.find_element(By.CSS_SELECTOR, "dt .brief").text.strip()

                if item_index == 0:
                    print(" - 첫 번째 항목은 클릭하지 않고 텍스트만 추출합니다.")
                    a_elem = item.find_element(By.CSS_SELECTOR, "dd .exp")
                    a_text = a_elem.text.strip()
                else:
                    # 질문 버튼 요소
                    btn = item.find_element(By.CSS_SELECTOR, "dt > button.more")
                    
                    # 클릭해서 답변 열기
                    driver.execute_script("arguments[0].click();", btn)
                    wait.until(lambda d: "on" in item.find_element(By.CSS_SELECTOR, "dt").get_attribute("class"))
                    
                    # 답변 추출
                    a_elem = item.find_element(By.CSS_SELECTOR, "dd .exp")
                    a_text = a_elem.text.strip()

                    # 다음 항목을 위해 답변 닫기
                    driver.execute_script("arguments[0].click();", btn)
                    wait.until(lambda d: "on" not in item.find_element(By.CSS_SELECTOR, "dt").get_attribute("class"))

                # 튜플에 카테고리, 질문, 답변, 출처(SOURCE_ID) 추가
                faq_data.append((cat_text, q_text, a_text, SOURCE_ID))
                print(f"  - {q_text[:30]}...")

            except Exception as e:
                print(f"  ❗ FAQ 처리 오류: {e}")
                continue

        # 다음 페이지 버튼
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "nav.pagination button.navi.next")
            if next_btn.get_attribute("disabled"):
                print("마지막 페이지 도달")
                break
            else:
                driver.execute_script("arguments[0].click();", next_btn)
                page_number += 1
                wait.until(EC.staleness_of(faq_items[0]))  # 새 페이지 로딩 대기
                time.sleep(1)
        except Exception:
            print("다음 페이지 버튼 없음 → 종료")
            break

finally:
    print("\n\n--- 스크래핑 완료 ---")
    print(f"총 {len(faq_data)}개 FAQ 수집")

    if faq_data:
        # DB에 데이터 삽입 로직 추가 (MySQL 연결 방식)
        try:
            print("\n--- DB에 데이터 삽입 중 ---")
            
            # .env 파일에서 MySQL 연결 정보 로드
            load_dotenv()
            
            # create_engine을 사용해 MySQL 데이터베이스에 연결
            engine = create_engine(
                f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:3306/{os.getenv('DB_NAME')}?charset=utf8mb4"
            )
            
            # 연결 테스트
            with engine.connect() as conn:
                print("MySQL 데이터베이스 연결 성공!")

                # 테이블명을 'faq'로 변경하고 source 컬럼 추가
                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS faq (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        category VARCHAR(255),
                        question TEXT,
                        answer TEXT,
                        source INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                '''))
                
                # 데이터 삽입 쿼리에서 테이블명과 컬럼 변경
                
                
                print(f"총 {len(faq_data)}개 FAQ 데이터 삽입을 시작합니다.")
                conn.execute(
                    text("INSERT INTO faq (category, question, answer, source) VALUES (:category, :question, :answer, :source)"),
                    [
                        {"category": cat, "question": q, "answer": a, "source": s}
                        for cat, q, a, s in faq_data
                    ]
                )
                conn.commit()
                print(f"DB에 {len(faq_data)}개 데이터 삽입 완료: faq 테이블")
                
            engine.dispose()
            
        except Exception as e:
            print(f"❗ DB 작업 오류: {e}")

    driver.quit()