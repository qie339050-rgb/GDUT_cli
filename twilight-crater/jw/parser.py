"""HTML 解析模块：将教务系统返回的 HTML 解析为结构化数据"""

import re
from bs4 import BeautifulSoup
from .config import logger


def parse_schedule_html(html: str) -> list[dict]:
    """解析课表 HTML，从内嵌 JS 变量 kbxx 提取课程数据
    
    教务系统课表页面的课程数据存储在 `var kbxx = [...]` 中，
    HTML table 只是空壳，由 JS 动态填充。

    Returns:
        [
            {
                "weekday": 2,           # 星期几 (1=周一, 7=周日)
                "period": "01,02",      # 节次
                "course": "高等数学",   # 课程名
                "course_code": "TMP1234", # 课程编号
                "weeks": "1,3,5",       # 周次
                "room": "教3-202",      # 教室
                "teacher": "张三",      # 教师
                "class_name": "...",     # 教学班
            },
            ...
        ]
    """
    import json as json_mod

    # 从 HTML 中提取 var kbxx = [...] 
    match = re.search(r'var\s+kbxx\s*=\s*(\[.*?\])\s*;', html, re.DOTALL)
    if not match:
        logger.warning("未找到课表数据 (var kbxx)")
        return []

    try:
        raw_data = json_mod.loads(match.group(1))
    except (json_mod.JSONDecodeError, ValueError) as e:
        logger.error(f"课表 JSON 解析失败: {e}")
        return []

    from .config import period_to_time

    result = []
    for item in raw_data:
        period = item.get("jcdm2", "")
        result.append({
            "weekday": int(item.get("xq", 0)),
            "period": period,
            "time": period_to_time(period),
            "course": item.get("kcmc", ""),
            "course_code": item.get("kcbh", ""),
            "weeks": item.get("zcs", ""),
            "room": item.get("jxcdmcs", ""),
            "teacher": item.get("teaxms", ""),
            "class_name": item.get("jxbmc", ""),
            "task_code": item.get("kcrwdm", ""),
        })

    logger.debug(f"解析到 {len(result)} 条课程记录")
    return result


def parse_student_info_html(html: str) -> dict:
    """解析学籍卡片 HTML 为结构化数据"""
    soup = BeautifulSoup(html, "lxml")
    info = {}

    # 先移除所有 <select> 下拉框（避免误抓选项文本）
    for select in soup.find_all("select"):
        # 提取 select 中被选中的 option 值
        selected = select.find("option", selected=True)
        if selected:
            select.replace_with(selected.get_text(strip=True))
        else:
            select.decompose()

    # 终极奥义：完全无视诡异的 colspan/rowspan 和标签嵌套
    # 直接按顺序提取出所有含有实际内容的区块，拼成一个扁平化的一维列表
    # 然后两两匹配！（这是因为教务排版中属性和值一定是一前一后毗邻出现的）

    elements = []
    
    # 获取表格内所有的 td 或 th
    for cell in soup.find_all(["td", "th"]):
        # 1. 如果它是图片，忽略
        if cell.find("img"):
            continue
            
        # 2. 如果里面有 input，优先取输入框的真实 value
        input_vals = []
        for inp in cell.find_all("input", attrs={"type": ["text", "hidden"]}):
            if inp.has_attr("value") and inp["value"].strip() and inp["value"].strip() != "1": # 规避无意义隐藏字段
                input_vals.append(inp["value"].strip())
                
        # 3. 提取自身全部可视文本
        text = cell.get_text(separator=' ', strip=True)
        import re
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 混合两者
        if input_vals:
            final_str = " ".join(input_vals)
        else:
            final_str = text
            
        # 4. 删除无意义占位符
        final_str = final_str.replace(" ", "").strip()
        if final_str and final_str != "(无)" and final_str != "无":
            elements.append(final_str)

    # 从一维列表中成对提取（属性通常带着冒号，或者长度较短）
    i = 0
    while i < len(elements) - 1:
        potential_label = elements[i]
        
        # 判断它像不像一个字段名（包含冒号，或者少于8个字）
        is_label = False
        if "：" in potential_label or ":" in potential_label:
            is_label = True
        elif len(potential_label) <= 8 and "大学" not in potential_label:
            is_label = True
            
        if is_label:
            label = re.sub(r'[\s：:]+', '', potential_label)
            val = elements[i+1]
            
            # 如果下一条也像是一个 label（连续出现），说明可能这里没有值被略过了，i 只进一格
            if len(val) <= 8 and ("：" in val or ":" in val):
                i += 1
                continue
                
            if label and val:
                info[label] = val
            i += 2
        else:
            i += 1

    logger.debug(f"解析到 {len(info)} 个学籍字段")
    return info


def parse_plan_list_html(html: str) -> list[dict]:
    """解析学习计划列表页面"""
    soup = BeautifulSoup(html, "lxml")
    plans = []

    table = soup.find("table")
    if not table:
        return plans

    rows = table.find_all("tr")
    headers = []

    for row in rows:
        ths = row.find_all("th")
        if ths:
            headers = [th.get_text(strip=True) for th in ths]
            continue

        cells = row.find_all("td")
        if not cells or not headers:
            continue

        plan = {}
        for i, cell in enumerate(cells):
            if i < len(headers):
                plan[headers[i]] = cell.get_text(strip=True)

            # 提取链接中的计划代码
            link = cell.find("a")
            if link and link.get("onclick"):
                match = re.search(r"['\"](\d+)['\"]", link.get("onclick", ""))
                if match:
                    plan["jxjhdm"] = match.group(1)

        if plan:
            plans.append(plan)

    return plans
