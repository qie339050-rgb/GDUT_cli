"""配置模块：路径、常量、学期代码工具函数"""

from pathlib import Path
from datetime import datetime
import logging

# ── 路径 ──
DATA_DIR = Path.home() / ".gdut"
COOKIES_FILE = DATA_DIR / "cookies.json"
LOG_FILE = DATA_DIR / "debug.log"

# ── URL ──
BASE_URL = "https://jxfw.gdut.edu.cn"
CAS_LOGIN_URL = (
    "https://authserver.gdut.edu.cn/authserver/login"
    "?service=https%3A%2F%2Fjxfw.gdut.edu.cn%2Fnew%2FssoLogin"
)
WELCOME_URL = f"{BASE_URL}/login!welcome.action"

# ── 请求头 ──
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# ── 日志 ──
logger = logging.getLogger("gdut")


def setup_logging(debug: bool = False):
    """设置日志级别"""
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.setLevel(level)


def ensure_data_dir():
    """确保数据目录存在"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


# ── 学期代码工具 ──

def current_semester() -> str:
    """自动推算当前学期代码
    
    规律：年份后缀 01=秋季(9月~1月), 02=春季(2月~6月)
    例: 202502 = 2025学年第2学期 = 2026年春季
    """
    now = datetime.now()
    year = now.year
    month = now.month

    if month >= 9:
        # 秋季学期：9月~12月 → 当年01
        return f"{year}01"
    elif month >= 2:
        # 春季学期：2月~6月 → 前一年02
        return f"{year - 1}02"
    else:
        # 1月：还是上一个秋季学期
        return f"{year - 1}01"


def semester_name(code: str) -> str:
    """学期代码转可读名称: 202502 → '2026春季'"""
    year = int(code[:4])
    term = code[4:]
    if term == "01":
        return f"{year}秋季"
    elif term == "02":
        return f"{year + 1}春季"
    return code


def all_semesters(start_year: int = 2020) -> list[dict]:
    """生成学期代码列表"""
    now = datetime.now()
    result = []
    for y in range(start_year, now.year + 1):
        result.append({"code": f"{y}01", "name": semester_name(f"{y}01")})
        result.append({"code": f"{y}02", "name": semester_name(f"{y}02")})
    return result


# ── 节次时间对照表 ──

PERIOD_TIMES = {
    "01": ("8:30", "9:15"),
    "02": ("9:20", "10:05"),
    "03": ("10:25", "11:10"),
    "04": ("11:15", "12:00"),
    "05": ("13:50", "14:35"),
    "06": ("14:40", "15:25"),
    "07": ("15:30", "16:15"),
    "08": ("16:30", "17:15"),
    "09": ("17:20", "18:05"),
    "10": ("18:30", "19:15"),
    "11": ("19:20", "20:05"),
    "12": ("20:10", "20:55"),
}


def period_to_time(period_str: str) -> str:
    """将节次代码转为具体时间范围
    
    Args:
        period_str: 如 "01,02" 或 "06,07" 或 "03"
    
    Returns:
        如 "8:30-10:05" 或 "14:40-16:15"
    """
    parts = [p.strip().zfill(2) for p in period_str.split(",") if p.strip()]
    if not parts:
        return period_str
    
    first = parts[0]
    last = parts[-1]
    
    start = PERIOD_TIMES.get(first, (first, first))[0]
    end = PERIOD_TIMES.get(last, (last, last))[1]
    
    return f"{start}-{end}"


# ── 周次计算 ──

# 当前学期第一周的周一日期
from datetime import date, timedelta

SEMESTER_WEEK1_MONDAY = date(2026, 3, 9)  # 2026春季第一周从3月9日(周一)开始

WEEKDAY_NAMES_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def calc_week_and_weekday(target_date: date = None) -> tuple[int, int]:
    """计算目标日期属于第几周、星期几
    
    Args:
        target_date: 目标日期，默认明天
        
    Returns:
        (week, weekday) — week 从 1 开始，weekday: 1=周一 7=周日
    """
    if target_date is None:
        target_date = date.today() + timedelta(days=1)

    delta = (target_date - SEMESTER_WEEK1_MONDAY).days
    if delta < 0:
        # 还没开学
        return (0, target_date.isoweekday())

    week = delta // 7 + 1
    weekday = target_date.isoweekday()  # 1=周一, 7=周日
    return (week, weekday)


def tomorrow_info() -> dict:
    """获取明天的日期、周次、星期几信息"""
    tomorrow = date.today() + timedelta(days=1)
    week, weekday = calc_week_and_weekday(tomorrow)
    return {
        "date": tomorrow,
        "date_str": tomorrow.strftime("%m月%d日"),
        "week": week,
        "weekday": weekday,
        "weekday_name": WEEKDAY_NAMES_CN[weekday - 1] if 1 <= weekday <= 7 else "?",
    }

