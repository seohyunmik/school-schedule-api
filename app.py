from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta
import calendar
import pytz

app = Flask(__name__)

API_KEY = '45b79ee5d9c640a299a2966db82ae7f4'
EDU_OFFICE_CODE = 'P10'
SCHOOL_CODE = '8321081'
KST = pytz.timezone('Asia/Seoul')

def get_kst_now():
    return datetime.now(KST)

def get_week_date_range(week_offset=0):
    today = get_kst_now()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    sunday = monday + timedelta(days=6)
    return monday.strftime('%Y%m%d'), sunday.strftime('%Y%m%d')

def get_month_date_range():
    today = get_kst_now()
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

def quick_replies():
    return [
        {"label": "오늘 급식", "action": "block", "blockId": "급식_오늘"},
        {"label": "내일 급식", "action": "block", "blockId": "급식_내일"},
        {"label": "이번주", "action": "block", "blockId": "일정_이번주"},
        {"label": "다음주", "action": "block", "blockId": "일정_다음주"},
        {"label": "이번달", "action": "block", "blockId": "일정_이번달"},
    ]

@app.route('/meal', methods=['POST'])
def meal():
    body = request.get_json()
    print("[meal 요청]", body)

    intent = body.get('intent', {}).get('id', '')  # block ID로 판단

    target_date = get_kst_now()
    if '내일' in intent:
        target_date += timedelta(days=1)

    date_str = target_date.strftime('%Y%m%d')
    meal_info = fetch_meal(date_str)

    response_body = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": meal_info
                    }
                }
            ]
        }
    }

    return jsonify(response_body)


@app.route('/schedule', methods=['POST'])
def schedule():
    body = request.get_json()
    print("[schedule 요청]", body)

    intent = body.get('intent', {}).get('id', '')  # block ID로 판단

    if '이번주' in intent:
        start, end = get_week_date_range(0)
        label = "이번주"
    elif '다음주' in intent:
        start, end = get_week_date_range(1)
        label = "다음주"
    elif '이번달' in intent:
        start, end = get_month_date_range()
        label = "이번달"
    else:
        return jsonify({
            "version": "2.0",
            "template": {
                "outputs": [{"simpleText": {"text": "잘못된 요청입니다."}}],
                "quickReplies": quick_replies()
            }
        })

    schedules = fetch_schedule(start, end)

    if not schedules:
        text = f"{label} 학사일정이 없습니다."
    else:
        def format_date(date_str):
            dt = datetime.strptime(date_str, '%Y%m%d')
            weekday = ['월', '화', '수', '목', '금', '토', '일'][dt.weekday()]
            return f"{dt.month}월 {dt.day}일({weekday})"

        text = f"[{label} 일정]\n" + "\n".join([f"{format_date(d)}: {e}" for d, e in schedules])

    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{
                "simpleText": {"text": text}
            }],
            "quickReplies": quick_replies()
        }
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
