"""CLI 入口：使用 Click 注册所有终端命令

命令前缀: gdut
所有命令支持 --json 输出原始 JSON（方便 OpenClaw Agent 解析）
Session 过期时自动弹出浏览器重新登录
"""

import json
import click
from rich.console import Console

from .config import setup_logging, current_semester, semester_name, tomorrow_info
from .auth import JWAuth
from .api import JWClient
from . import display

console = Console()
auth = JWAuth()


def _get_client() -> JWClient:
    """获取 API 客户端（自动处理登录）"""
    session = auth.get_session(auto_login=True)
    return JWClient(session)


@click.group()
@click.option("--debug", is_flag=True, default=False, help="开启调试日志")
def cli(debug):
    """广东工业大学教务系统 CLI 工具 🎓"""
    setup_logging(debug)


# ═══════════════════════════════════════════
# 登录 / 退出
# ═══════════════════════════════════════════

@cli.command()
def login():
    """打开浏览器进行登录"""
    auth.login()


@cli.command()
def logout():
    """退出登录，清除本地 Session"""
    auth.logout()


@cli.command(name="open")
def open_sys():
    """在浏览器中打开教务系统 (复用登录状态)"""
    auth.open_browser()


# ═══════════════════════════════════════════
# 课表查询
# ═══════════════════════════════════════════

def _parse_weeks(weeks_str: str) -> list[int]:
    """解析周次字符串为整数列表"""
    return [int(w.strip()) for w in weeks_str.split(",") if w.strip().isdigit()]


def _filter_schedule(data: list[dict], week: int = None, weekday: int = None) -> list[dict]:
    """从全学期课表中筛选

    Args:
        data: 全部课表数据
        week: 周次 (1~20)，None=不筛选
        weekday: 星期几 (1=周一, 7=周日)，None=不筛选
    """
    result = []
    for d in data:
        if weekday is not None and d["weekday"] != weekday:
            continue
        if week is not None:
            if week not in _parse_weeks(d.get("weeks", "")):
                continue
        result.append(d)
    return result


def _filter_schedule_date_range(data: list[dict], start_date, end_date) -> list[dict]:
    """按日期范围筛选课程"""
    from .config import calc_week_and_weekday, SEMESTER_WEEK1_MONDAY
    from datetime import timedelta

    result = []
    current = start_date
    seen = set()

    while current <= end_date:
        week, weekday = calc_week_and_weekday(current)
        if week > 0:
            for d in data:
                key = (d["course"], d["weekday"], d["period"], d.get("weeks", ""))
                if key in seen:
                    continue
                if d["weekday"] == weekday and week in _parse_weeks(d.get("weeks", "")):
                    result.append(d)
                    seen.add(key)
        current += timedelta(days=1)

    return result


@cli.command()
@click.option("--date", "-d", "target_date", default=None,
              help="查指定日期 (YYYY-MM-DD)")
@click.option("--week", "-w", type=int, default=None,
              help="查指定周次 (1~20)")
@click.option("--day", type=int, default=None,
              help="星期几 (1=周一, 7=周日), 配合 --week 使用")
@click.option("--from", "date_from", default=None,
              help="起始日期 (YYYY-MM-DD)")
@click.option("--to", "date_to", default=None,
              help="结束日期 (YYYY-MM-DD)")
@click.option("--all", "show_all", is_flag=True, default=False,
              help="显示全学期课表")
@click.option("--semester", "-s", default=None,
              help="学期代码 (如 202502)")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="输出 JSON")
def schedule(target_date, week, day, date_from, date_to, show_all, semester, as_json):
    """查询课表

    \b
    默认查明天的课。支持多种查询方式：
      gdut schedule                    # 明天的课
      gdut schedule --date 2026-03-15  # 3月15号的课
      gdut schedule --week 3           # 第3周全部课
      gdut schedule --week 3 --day 1   # 第3周周一
      gdut schedule --from 2026-03-10 --to 2026-03-14  # 日期范围
      gdut schedule --all              # 全学期
    """
    from datetime import date as date_cls, timedelta
    from .config import calc_week_and_weekday, WEEKDAY_NAMES_CN

    client = _get_client()
    sem = semester or current_semester()

    # 获取全部课表数据
    all_data = client.get_schedule(semester=sem)
    display_week = None

    if show_all:
        # ── 全学期 ──
        console.print(f"[dim]查询: {semester_name(sem)} 全部周次[/dim]")
        data = all_data

    elif target_date:
        # ── 查指定日期 ──
        try:
            d = date_cls.fromisoformat(target_date)
        except ValueError:
            console.print(f"[red]❌ 日期格式错误: {target_date}，请用 YYYY-MM-DD[/red]")
            return
        w, wd = calc_week_and_weekday(d)
        if w <= 0:
            console.print(f"[yellow]📭 {d.strftime('%m月%d日')} 还没开学[/yellow]")
            return
        wd_name = WEEKDAY_NAMES_CN[wd - 1] if 1 <= wd <= 7 else "?"
        console.print(f"[dim]查询: {d.strftime('%m月%d日')} {wd_name} (第{w}周)[/dim]")
        data = _filter_schedule(all_data, week=w, weekday=wd)
        display_week = w

    elif date_from or date_to:
        # ── 日期范围 ──
        today = date_cls.today()
        try:
            start = date_cls.fromisoformat(date_from) if date_from else today
            end = date_cls.fromisoformat(date_to) if date_to else start + timedelta(days=6)
        except ValueError:
            console.print("[red]❌ 日期格式错误，请用 YYYY-MM-DD[/red]")
            return
        console.print(f"[dim]查询: {start.strftime('%m月%d日')} ~ {end.strftime('%m月%d日')}[/dim]")
        data = _filter_schedule_date_range(all_data, start, end)

    elif week:
        # ── 指定周次 ──
        if day:
            wd_name = WEEKDAY_NAMES_CN[day - 1] if 1 <= day <= 7 else "?"
            console.print(f"[dim]查询: {semester_name(sem)} 第{week}周 {wd_name}[/dim]")
            data = _filter_schedule(all_data, week=week, weekday=day)
        else:
            console.print(f"[dim]查询: {semester_name(sem)} 第{week}周[/dim]")
            data = _filter_schedule(all_data, week=week)
        display_week = week

    else:
        # ── 默认: 明天 ──
        info = tomorrow_info()
        if info["week"] <= 0:
            console.print(f"[yellow]📭 还没开学（明天是{info['date_str']}）[/yellow]")
            return
        console.print(
            f"[dim]查询: {info['date_str']} {info['weekday_name']} "
            f"(第{info['week']}周)[/dim]"
        )
        data = _filter_schedule(all_data, week=info["week"], weekday=info["weekday"])
        display_week = info["week"]

    if as_json:
        display.print_json(data)
    else:
        display.print_schedule(data, week=display_week, semester=sem)


# ═══════════════════════════════════════════
# 学习计划
# ═══════════════════════════════════════════

@cli.command()
@click.option("--json", "as_json", is_flag=True, default=False, help="输出 JSON")
def plan(as_json):
    """查询学习计划"""
    client = _get_client()

    # 先获取计划列表
    plans = client.get_study_plans()

    if not plans:
        console.print("[yellow]📭 没有找到教学计划[/yellow]")
        return

    # 如果有计划代码，获取第一个计划的课程详情
    plan_code = None
    for p in plans:
        if "jxjhdm" in p:
            plan_code = p["jxjhdm"]
            break

    if plan_code:
        data = client.get_plan_courses(plan_code)
        if as_json:
            display.print_json(data)
        else:
            display.print_plan(data)
    else:
        if as_json:
            display.print_json(plans)
        else:
            display.print_generic_table(plans, "教学计划列表")


# ═══════════════════════════════════════════
# 成绩查询
# ═══════════════════════════════════════════

@cli.command()
@click.option("--semester", "-s", default=None, help="学期代码 (留空=全部)")
@click.option("--json", "as_json", is_flag=True, default=False, help="输出 JSON")
def grades(semester, as_json):
    """查询课程成绩"""
    client = _get_client()

    if semester:
        console.print(f"[dim]查询: {semester_name(semester)}[/dim]")
    else:
        console.print("[dim]查询: 全部学期成绩[/dim]")

    data = client.get_grades(semester=semester)

    if as_json:
        display.print_json(data)
    else:
        display.print_grades(data)


# ═══════════════════════════════════════════
# 考试安排
# ═══════════════════════════════════════════

@cli.command()
@click.option("--semester", "-s", default=None, help="学期代码")
@click.option("--json", "as_json", is_flag=True, default=False, help="输出 JSON")
def exams(semester, as_json):
    """查询考试安排"""
    client = _get_client()
    sem = semester or current_semester()
    console.print(f"[dim]查询: {semester_name(sem)} 考试安排[/dim]")

    data = client.get_exams(semester=sem)

    if as_json:
        display.print_json(data)
    else:
        display.print_exams(data)


# ═══════════════════════════════════════════
# 学籍信息
# ═══════════════════════════════════════════

@cli.command()
@click.option("--json", "as_json", is_flag=True, default=False, help="输出 JSON")
def info(as_json):
    """查询学籍信息"""
    client = _get_client()
    data = client.get_student_info()

    if as_json:
        display.print_json(data)
    else:
        display.print_student_info(data)


# ═══════════════════════════════════════════
# 考级成绩
# ═══════════════════════════════════════════

@cli.command("cet")
@click.option("--json", "as_json", is_flag=True, default=False, help="输出 JSON")
def grade_exams(as_json):
    """查询考级成绩（四六级等）"""
    client = _get_client()
    data = client.get_grade_exams()

    if as_json:
        display.print_json(data)
    else:
        display.print_generic_table(data, "🏅 考级成绩")


# ═══════════════════════════════════════════
# 考勤
# ═══════════════════════════════════════════

@cli.command()
@click.option("--semester", "-s", default=None, help="学期代码")
@click.option("--json", "as_json", is_flag=True, default=False, help="输出 JSON")
def attendance(semester, as_json):
    """查询考勤情况"""
    client = _get_client()
    data = client.get_attendance(semester=semester)

    if as_json:
        display.print_json(data)
    else:
        display.print_generic_table(data, "📋 考勤情况")


# ═══════════════════════════════════════════
# 体测成绩
# ═══════════════════════════════════════════

@cli.command("pe")
@click.option("--json", "as_json", is_flag=True, default=False, help="输出 JSON")
def physical_test(as_json):
    """查询体测成绩"""
    client = _get_client()
    data = client.get_physical_test()

    if as_json:
        display.print_json(data)
    else:
        display.print_generic_table(data, "🏃 体测成绩")


# ═══════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════

def main():
    cli()


if __name__ == "__main__":
    main()
