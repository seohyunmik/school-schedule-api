from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import calendar

app = Flask(__name__)

# NEIS API 정보
API_KEY = '45b79ee5d9c640a299a2966db82ae7f4'
EDU_OFFICE_CODE = 'P10'       # 전북특별자치도교육청
SCHOOL_CODE = '8321081'       # 해당 학교 고유 코드

# 주간 날짜 범위 계산
def get_week_date_range(week_offset=0):
    today = datetime.now()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y%m%d'), sunday.strftime('%Y%m%d')

# 월간 날짜 범위 계산
def get_month_date_range():
    today = datetime.now()
    first_day = today.replace(day=1)
    last_day_num = calendar.monthrange(today.year, today.month)[1]
    last_day = today.replace(day=last_day_num)
    return first_day.strftime('%Y%m%d'), last_day.strftime('%Y%m%d')

# 학사일정 API 호출
def fetch_schedule(start_date, end_date):
    url = (
        f"https://open.neis.go.kr/hub/SchoolSchedule?"
        f"KEY={API_KEY}&Type=json&"
        f"ATPT_OFCDC_SC_CODE={EDU_OFFICE_CODE}&"
        f"SD_SCHUL_CODE={SCHOOL_CODE}&"
        f"AA_FROM_YMD={start_date}&AA_TO_YMD={end_date}"
    )
    res = requests.get(url)
    data = res.json()

    if 'SchoolSchedule' not in data:
        return []

    schedules = data['SchoolSchedule'][1]['row']
    filtered = []
    for item in schedules:
        date = item.get('AA_YMD')
        event = item.get('EVENT_NM')
        if event.strip():
            filtered.append((date, event))
    return filtered

@app.route('/schedule', methods=['POST'])
def schedule():
    body = request.get_json()
    action = body.get('action', '').strip()

    if action == '이번주':
        start, end = get_week_date_range(0)
    elif action == '다음주':
        start, end = get_week_date_range(1)
    elif action == '이번달':
        start, end = get_month_date_range()
    else:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "잘못된 요청입니다. '이번주', '다음주', '이번달' 중 하나를 선택해 주세요."}}]
            }
        })

    schedules = fetch_schedule(start, end)

    if not schedules:
        text = f"{action} 학사일정이 없습니다."
    else:
        def format_date(date_str):
            dt = datetime.strptime(date_str, '%Y%m%d')
            weekday = ['월', '화', '수', '목', '금', '토', '일'][dt.weekday()]
            return f"{dt.month}월 {dt.day}일({weekday})"

        lines = [f"{format_date(date)}: {event}" for date, event in schedules]
        text = "\n".join(lines)

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
            "quickReplies": [
                {"label": "이번주", "action": "message", "messageText": "이번주"},
                {"label": "다음주", "action": "message", "messageText": "다음주"},
                {"label": "이번달", "action": "message", "messageText": "이번달"},
            ]
        }
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
