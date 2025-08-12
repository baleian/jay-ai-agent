import datetime
from typing import Literal

from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """
    현재 시각을 가져올 때 사용합니다.
    예: '지금 몇시야?', '오늘 몇일이야?'
    """
    now = datetime.datetime.now()
    return now.isoformat()


@tool
def get_weather(city: Literal["seoul", "newyork"], current_time: str) -> str:
    """특정 도시의 현재 날씨 정보를 가져옵니다.
    Args:
    - city: 'seoul' 또는 'newyork'.
    - current_time: 현재 시각을 나타내는 '%Y-%m-%d %H:%M:%S' 포맷의 문자열.
    """
    if city.lower() == "seoul":
        return "맑음, 28°C"
    elif city.lower() == "newyork":
        return "안개, 15°C"
    else:
        return "알 수 없는 도시입니다."


all_tools = [
    get_current_time,
    get_weather
]
