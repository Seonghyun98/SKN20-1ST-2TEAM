from selenium import webdriver as wd
from selenium.webdriver.chrome.service import Service as sv
from webdriver_manager.chrome import ChromeDriverManager as cdm 
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
import time
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os

# .env 파일 로드 (DB 연결 시 사용)
load_dotenv()

# 현재 스크래핑할 사이트를 구분하는 변수 (기아차: 1)
SOURCE_ID = 1

url = 'https://www.kia.com/kr/customer-service/center/faq'
service = sv(cdm().install())
driver = wd.Chrome(service=service)

wait = WebDriverWait(driver, 10)
faq_data = []

try:
    print("웹사이트에 접속 중...")
    driver.get(url)
    driver.maximize_window()
    time.sleep(2)

    # '전체' 버튼 클릭 (최초 1회만 실행)
    try:
        all_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, '#tab-list > li:nth-child(2) > button')))
        print("'전체' 버튼 클릭 중...")
        driver.execute_script("arguments[0].click();", all_btn)
        time.sleep(2) # 콘텐츠 로딩을 위한 충분한 대기 시간
    except Exception as e:
        print(f"오류: '전체' 버튼을 찾을 수 없습니다. 계속 진행합니다. {e}")

    page_number = 1
    while True:
        print(f"\n--- {page_number} 페이지 ---")
        
        # 현재 페이지의 모든 FAQ 항목을 가져와서 개수 파악
        faq_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.cmp-accordion__item")))
        num_faq_items = len(faq_elements)
        print(f"FAQ {num_faq_items}개 발견")

        for item_index in range(num_faq_items):
            try:
                # 질문 텍스트와 버튼을 고유 ID로 직접 찾기
                q_text = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f"#accordion-item-{item_index}-button > span.cmp-accordion__title"))).text.strip()
                btn = wait.until(EC.presence_of_element_located((By.ID, f"accordion-item-{item_index}-button")))
                
                # 답변 패널 ID 설정
                panel_id = f"accordion-item-{item_index}-panel"

                # 클릭해서 답변 열기
                driver.execute_script("arguments[0].click();", btn)
                wait.until(EC.visibility_of_element_located((By.ID, panel_id)))
                
                # 답변 추출 (텍스트와 이미지 URL 포함)
                panel_element = driver.find_element(By.ID, panel_id)
                content_list = []
                
                # 패널 내부의 모든 자식 요소(p, img 등)를 찾아 처리
                for child in panel_element.find_elements(By.XPATH, ".//*"):
                    if child.tag_name == 'p':
                        content_list.append(child.text.strip())
                    elif child.tag_name == 'img':
                        img_url = child.get_attribute('src')
                        if img_url:
                            content_list.append(f"[이미지: {img_url}]")
                
                a_text = "\n".join(content_list)
                
                # 다음 항목을 위해 답변 닫기
                driver.execute_script("arguments[0].click();", btn)
                wait.until(EC.invisibility_of_element_located((By.ID, panel_id)))

                faq_data.append((None, q_text, a_text, SOURCE_ID))
                print(f"  - {q_text[:30]}...")

            except Exception as e:
                print(f"  ❗ FAQ 처리 오류: {e}")
                continue

        # 다음 페이지 버튼 로직
        try:
            # 현재 페이지 번호를 확인
            current_page_link = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.faq-bottom-paging > div > ul > li.is-active > a')))
            current_page_number = int(current_page_link.text)

            # 5의 배수 페이지는 화살표 버튼을, 그 외 페이지는 숫자 링크를 클릭
            if current_page_number % 5 == 0:
                next_btn = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.faq-bottom-paging > div > button.pagigation-btn-next')))
                driver.execute_script("arguments[0].click();", next_btn)
                print("5의 배수 페이지: 화살표 버튼 클릭")
                
                # 화살표 클릭 후, 새 페이지네이션 목록이 나타날 때까지 기다림
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, f'div.faq-bottom-paging > div > ul > li.is-active > a')))
            else:
                next_page_link_selector = f'div.faq-bottom-paging > div > ul > li:nth-child({(current_page_number % 5) + 1}) > a'
                try:
                    next_page_link = driver.find_element(By.CSS_SELECTOR, next_page_link_selector)
                    driver.execute_script("arguments[0].click();", next_page_link)
                    print(f"{page_number} -> {page_number + 1}: 숫자 페이지 버튼 클릭")
                except NoSuchElementException:
                    print("더 이상 다음 페이지가 없습니다. 스크래핑 종료.")
                    break

            # 다음 페이지의 첫 번째 항목이 완전히 로드될 때까지 기다림
            wait.until(EC.staleness_of(faq_elements[0]))
            
            page_number += 1
            time.sleep(1) # 추가 대기
            
        except StaleElementReferenceException:
            # StaleElementReferenceException이 발생하면 요소를 다시 찾아서 재시도
            print("❗ StaleElementReferenceException 발생. 페이지 요소 재로딩 후 재시도합니다.")
            time.sleep(2)
            continue
        except Exception as e:
            print(f"다음 페이지 로직 실행 오류: {e}")
            break

finally:
    print("\n\n--- 스크래핑 완료 ---")
    print(f"총 {len(faq_data)}개 FAQ 수집")

    if faq_data:
        try:
            print("\n--- DB에 데이터 삽입 중 ---")
            engine = create_engine(
                f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:3306/{os.getenv('DB_NAME')}?charset=utf8mb4"
            )
            
            with engine.connect() as conn:
                print("MySQL 데이터베이스 연결 성공!")

                conn.execute(text('''
                    CREATE TABLE IF NOT EXISTS faq (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        category TEXT,
                        question TEXT,
                        answer TEXT,
                        source INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                '''))
                
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