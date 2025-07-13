from flask import Flask, request, make_response
import requests
from datetime import datetime, timedelta
import calendar
import json

app = Flask(__name__)

API_KEY = '45b79ee5d9c640a299a2966db82ae7f4'
EDU_OFFICE_CODE = 'P10'     # 전북특별자치도교육청
SCHOOL_CODE = '8321081'     # 학교 고유 코드


### 🔹 학사일정 기능

def get_week_date_range(week_offset=0):
    today = datetime.now()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y%m%d'), sunday.strftime('%Y%m%d')

def get_month_date_range():
    today = datetime.now()
    first_day = today.replace(day=1)
    last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return first_day.strftime('%Y%m%d'), last_day.strftime('%Y%m%d')

def fetch_schedule(start_date, end_date):
    url = f"https://open.neis.go.kr/hub/SchoolSchedule?KEY={API_KEY}&Type=json&ATPT_OFCDC_SC_CODE={EDU_OFFICE_CODE}&SD_SCHUL_CODE={SCHOOL_CODE}&AA_FROM_YMD={start_date}&AA_TO_YMD={end_date}"
    res = requests.get(url)
    data = res.json()

    if 'SchoolSchedule' not in data:
        return []

    schedules = data['SchoolSchedule'][1]['row']
    return [(item['AA_YMD'], item['EVENT_NM']) for item in schedules if item['EVENT_NM'].strip()]

@app.route('/schedule', methods=['POST'])
def schedule():
    body = request.get_json()
    print("[DEBUG] 받은 요청:", body)

    action = body.get('action', '')

    if action == '이번주':
        start, end = get_week_date_range(0)
    elif action == '다음주':
        start, end = get_week_date_range(1)
    elif action == '이번달':
        start, end = get_month_date_range()
    else:
        result = {
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "잘못된 요청입니다."}}]
            }
        }
        return make_json_response(result)

    schedules = fetch_schedule(start, end)

    if not schedules:
        text = f"{action} 학사일정이 없습니다."
    else:
        def format_date(date_str):
            dt = datetime.strptime(date_str, '%Y%m%d')
            weekday = ['월', '화', '수', '목', '금', '토', '일'][dt.weekday()]
            return f"{dt.month}월 {dt.day}일({weekday})"
        
        text = "\n".join([f"{format_date(d)}: {e}" for d, e in schedules])

    result = {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
            "quickReplies": [
                {"label": "오늘 급식", "action": "block", "blockId": "급식_오늘"},
                {"label": "내일 급식", "action": "block", "blockId": "급식_내일"},
                {"label": "이번주", "action": "block", "blockId": "일정_이번주"},
                {"label": "다음주", "action": "block", "blockId": "일정_다음주"},
                {"label": "이번달", "action": "block", "blockId": "일정_이번달"},
            ]
        }
    }
    return make_json_response(result)


### 🔹 급식 기능

def fetch_meal(date_str):
    url = f'https://open.neis.go.kr/hub/mealServiceDietInfo?KEY={API_KEY}&Type=json&pIndex=1&pSize=30&ATPT_OFCDC_SC_CODE={EDU_OFFICE_CODE}&SD_SCHUL_CODE={SCHOOL_CODE}&MLSV_YMD={date_str}'
    res = requests.get(url)
    data = res.json()

    if 'mealServiceDietInfo' not in data or len(data['mealServiceDietInfo']) <= 1:
        return "급식 정보가 없습니다."

    rows = data['mealServiceDietInfo'][1].get('row', [])
    if not rows:
        return "급식 정보가 없습니다."

    result = []
    meals = ['조식', '중식', '석식']
    for i in range(min(3, len(rows))):
        name = meals[i]
        menu = rows[i]['DDISH_NM'].replace('<br/>', '\n').replace('<br />', '\n').replace('<br>', '\n')
        cal = rows[i].get('CAL_INFO', '')
        result.append(f"{name}\n{menu}\n총 {cal}")

    return "\n\n".join(result)

@app.route('/meal', methods=['POST'])
def meal():
    body = request.get_json()
    print("[DEBUG] 받은 요청:", body)

    action = body.get('action', '오늘')

    target_date = datetime.now()
    if action == '내일':
        target_date += timedelta(days=1)

    date_str = target_date.strftime('%Y%m%d')
    meal_info = fetch_meal(date_str)

    result = {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": meal_info}}],
            "quickReplies": [
                {"label": "오늘 급식", "action": "block", "blockId": "급식_오늘"},
                {"label": "내일 급식", "action": "block", "blockId": "급식_내일"},
                {"label": "이번주", "action": "block", "blockId": "일정_이번주"},
                {"label": "다음주", "action": "block", "blockId": "일정_다음주"},
                {"label": "이번달", "action": "block", "blockId": "일정_이번달"},
            ]
        }
    }

    return make_json_response(result)


### 🔹 공통: JSON 응답 함수

def make_json_response(data_dict):
    response = make_response(json.dumps(data_dict, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


### 🔹 실행

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
