"""终端美化输出模块：使用 rich 库渲染彩色表格"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from .config import semester_name

console = Console()

# ── 课表颜色映射 ──
COURSE_COLORS = [
    "cyan", "green", "yellow", "magenta", "blue",
    "red", "bright_cyan", "bright_green", "bright_yellow", "bright_magenta",
]
WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def print_schedule(data: list[dict], week: int = None, semester: str = None):
    """以课程列表形式输出（更适合终端宽度）"""
    if not data:
        console.print("[yellow]📭 该时段没有课程[/yellow]")
        return

    # 去重：合并同课程同时段
    seen = set()
    unique = []
    for d in data:
        key = (d["course"], d["weekday"], d["period"])
        if key not in seen:
            seen.add(key)
            unique.append(d)
    unique.sort(key=lambda x: (x["weekday"], x["period"]))

    # 标题
    title = "📅 课表"
    if week:
        title += f" · 第{week}周"
    if semester:
        title += f" · {semester_name(semester)}"

    table = Table(title=title, show_lines=True)
    table.add_column("星期", style="bold cyan", justify="center", width=6)
    table.add_column("时间", justify="center", width=14)
    table.add_column("课程", style="bold", min_width=14)
    table.add_column("教室", min_width=10)
    table.add_column("教师", min_width=6)
    table.add_column("周次", style="dim", min_width=8)

    course_names = list(set(d["course"] for d in unique))
    color_map = {name: COURSE_COLORS[i % len(COURSE_COLORS)] for i, name in enumerate(course_names)}

    for d in unique:
        wd = WEEKDAY_NAMES[d["weekday"] - 1] if 1 <= d["weekday"] <= 7 else "?"
        time_str = d.get("time", d["period"])
        color = color_map.get(d["course"], "white")
        table.add_row(
            wd,
            time_str,
            f"[{color}]{d['course']}[/{color}]",
            d.get("room", ""),
            d.get("teacher", ""),
            d.get("weeks", ""),
        )

    console.print(table)
    console.print(f"[dim]共 {len(unique)} 条记录[/dim]")


def print_grades(data: list[dict]):
    """输出成绩表格"""
    if not data:
        console.print("[yellow]📭 没有成绩数据[/yellow]")
        return

    table = Table(title="📊 课程成绩", show_lines=True)
    table.add_column("学期", style="cyan", min_width=10)
    table.add_column("课程名称", style="bold", min_width=16)
    table.add_column("学分", justify="center", min_width=4)
    table.add_column("成绩", justify="center", min_width=6)
    table.add_column("绩点", justify="center", min_width=4)

    for row in data:
        score = str(row.get("zcj", row.get("cj", "")))
        gpa = str(row.get("cjjd", row.get("jd", "")))
        # 颜色标记
        score_style = "green" if _is_pass(score) else "red"
        table.add_row(
            str(row.get("xnxqmc", row.get("xnxqdm", ""))),
            str(row.get("kcmc", "")),
            str(row.get("xf", "")),
            f"[{score_style}]{score}[/{score_style}]",
            gpa,
        )

    console.print(table)


def print_exams(data: list[dict]):
    """输出考试安排表"""
    if not data:
        console.print("[yellow]📭 没有考试安排[/yellow]")
        return

    table = Table(title="📝 考试安排", show_lines=True)
    table.add_column("课程", style="bold", min_width=14)
    table.add_column("时间", style="cyan", min_width=18)
    table.add_column("地点", min_width=10)
    table.add_column("座位号", justify="center")
    table.add_column("类型", min_width=8)

    for row in data:
        table.add_row(
            str(row.get("kcmc", "")),
            str(row.get("kssj", row.get("ksrq", ""))),
            str(row.get("ksdd", "")),
            str(row.get("zwh", "")),
            str(row.get("ksaplxmc", "")),
        )

    console.print(table)


def print_plan(data: list[dict]):
    """输出学习计划课程表"""
    if not data:
        console.print("[yellow]📭 没有学习计划数据[/yellow]")
        return

    table = Table(title="📚 学习计划", show_lines=True)
    table.add_column("课程代码", style="dim", min_width=10)
    table.add_column("课程名称", style="bold", min_width=16)
    table.add_column("学分", justify="center", min_width=4)
    table.add_column("课程性质", min_width=8)
    table.add_column("建议学期", min_width=8)

    for row in data:
        table.add_row(
            str(row.get("kcdm", row.get("kcbh", ""))),
            str(row.get("kcmc", "")),
            str(row.get("xf", "")),
            str(row.get("kcxzmc", row.get("kcxz", ""))),
            str(row.get("jyxq", row.get("nj", ""))),
        )

    console.print(table)


def print_student_info(data: dict):
    """输出学籍信息"""
    if not data:
        console.print("[yellow]📭 没有学籍信息[/yellow]")
        return

    # 关键字段映射 (模糊包含匹配)
    fields = [
        ("学号", ["学号", "xh"]),
        ("姓名", ["姓名", "xm"]),
        ("入学年份", ["入学年份", "rxnf"]),
        ("学院", ["院系", "学院", "xy"]),
        ("专业", ["专业", "zy"]),
        ("班级", ["班级", "bj"]),
        ("年级", ["年级", "nj"]),
        ("校区", ["校区", "xq"]),
        ("学生状态", ["学生状态"]),
        ("学籍状态", ["学籍状态"]),
    ]

    from rich.table import Table
    table = Table(title="🎓 学籍信息", show_lines=True, show_header=False)
    table.add_column("项目", style="bold cyan", min_width=10)
    table.add_column("内容", min_width=20)

    for label, search_keys in fields:
        matched_value = None
        for search_key in search_keys:
            for actual_key in data.keys():
                if search_key in actual_key:
                    matched_value = data[actual_key]
                    break
            if matched_value is not None:
                break
                
        if matched_value is not None:
            table.add_row(label, str(matched_value))
            
    console.print(table)


def print_json(data):
    """输出 JSON 格式（供 AI Agent 使用）"""
    import json
    console.print(json.dumps(data, ensure_ascii=False, indent=2))


def print_generic_table(data: list[dict], title: str = "查询结果"):
    """通用表格输出（用于没有专用 display 函数的接口）"""
    if not data:
        console.print(f"[yellow]📭 没有{title}数据[/yellow]")
        return

    table = Table(title=title, show_lines=True)
    # 用第一行的 key 作为列名
    keys = list(data[0].keys())[:8]  # 最多显示8列
    for key in keys:
        table.add_column(key, min_width=8)

    for row in data[:50]:  # 最多显示50行
        table.add_row(*[str(row.get(k, "")) for k in keys])

    console.print(table)


def _is_pass(score: str) -> bool:
    """判断成绩是否及格"""
    try:
        return float(score) >= 60
    except (ValueError, TypeError):
        return score in ("合格", "通过", "优秀", "良好", "中等", "及格", "P")
