"""SDK 层：所有教务系统接口的 Python 封装

每个方法返回纯 Python 数据结构 (dict/list)，不做任何终端输出。
方便 OpenClaw AI Agent 直接 import 调用。

使用方式:
    from jw.auth import JWAuth
    from jw.api import JWClient

    auth = JWAuth()
    session = auth.get_session()  # 自动登录或复用 Cookie
    client = JWClient(session)

    schedule = client.get_schedule(week=5)
    grades = client.get_grades()
"""

import requests
from .config import BASE_URL, current_semester, logger
from .parser import parse_schedule_html, parse_student_info_html, parse_plan_list_html


class JWClient:
    """教务系统 API 客户端"""

    def __init__(self, session: requests.Session):
        self.session = session
        self.base = BASE_URL
        self._initialized = False

    def _ensure_init(self):
        """首次请求前先访问首页，激活 session 并设置 Referer"""
        if not self._initialized:
            self.session.headers["Referer"] = f"{self.base}/"
            try:
                self.session.get(f"{self.base}/login!welcome.action", timeout=10)
            except Exception:
                pass
            self._initialized = True

    def _url(self, path: str) -> str:
        return f"{self.base}/{path}"

    def _get(self, path: str, params: dict = None) -> requests.Response:
        """发送 GET 请求"""
        self._ensure_init()
        url = self._url(path)
        logger.debug(f"GET {url} params={params}")
        resp = self.session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp

    def _post(self, path: str, data: dict = None) -> requests.Response:
        """发送 POST 请求"""
        self._ensure_init()
        url = self._url(path)
        logger.debug(f"POST {url} data={data}")
        resp = self.session.post(url, data=data, timeout=15)
        resp.raise_for_status()
        return resp

    def _post_json(self, path: str, data: dict = None) -> dict:
        """发送 POST 请求并解析 JSON 响应"""
        resp = self._post(path, data)
        try:
            return resp.json()
        except ValueError:
            logger.error(f"JSON 解析失败，响应内容: {resp.text[:200]}")
            return {"total": 0, "rows": []}

    # ═══════════════════════════════════════════
    # 课表查询
    # ═══════════════════════════════════════════

    def get_schedule(self, semester: str = None, week: int = None) -> list[dict]:
        """获取个人课表
        
        Args:
            semester: 学期代码，如 "202502"，默认当前学期
            week: 周次 1~20，默认全部周次
            
        Returns:
            课程列表 [{"weekday", "period", "course", "weeks", "room"}, ...]
        """
        sem = semester or current_semester()

        if week:
            resp = self._get(
                "xsgrkbcx!xskbList.action",
                params={"xnxqdm": sem, "zc": str(week)},
            )
        else:
            resp = self._get(
                "xsgrkbcx!xsAllKbList.action",
                params={"xnxqdm": sem},
            )

        return parse_schedule_html(resp.text)

    # ═══════════════════════════════════════════
    # 学习计划
    # ═══════════════════════════════════════════

    def get_study_plans(self) -> list[dict]:
        """获取教学计划列表"""
        resp = self._get("xsjxjhxx!xsjxjhList.action", params={"lx": "01"})
        return parse_plan_list_html(resp.text)

    def get_plan_courses(self, plan_code: str) -> list[dict]:
        """获取某个教学计划的课程列表
        
        Args:
            plan_code: 教学计划代码 (jxjhdm)
        """
        result = self._post_json(
            f"xsjxjhxx!getKcDataList.action?jxjhdm={plan_code}",
        )
        return result.get("rows", []) if isinstance(result, dict) else result

    # ═══════════════════════════════════════════
    # 课程成绩
    # ═══════════════════════════════════════════

    def get_grades(self, semester: str = None) -> list[dict]:
        """获取课程成绩
        
        Args:
            semester: 学期代码，空=全部学期
        """
        data = {
            "xnxqdm": semester or "",
            "page": "1",
            "rows": "200",
            "sort": "xnxqdm",
            "order": "asc",
        }
        result = self._post_json("xskccjxx!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 考试安排
    # ═══════════════════════════════════════════

    def get_exams(self, semester: str = None, exam_type: str = None) -> list[dict]:
        """获取考试安排
        
        Args:
            semester: 学期代码，默认当前学期
            exam_type: 考试类型 01=随堂考 02=学院停课考 03=学校停课考 04=学院合考
        """
        data = {
            "xnxqdm": semester or current_semester(),
            "ksaplxdm": exam_type or "",
            "page": "1",
            "rows": "200",
            "sort": "zc,xq,jcdm2",
            "order": "asc",
        }
        result = self._post_json("xsksap!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 学籍信息
    # ═══════════════════════════════════════════

    def get_student_info(self) -> dict:
        """获取学籍卡片信息"""
        resp = self._get("xjkpxx!xjkpxx.action")
        # [临时 Debug] 写入到本地文件以供分析
        with open("temp_xjkpxx.html", "w", encoding="utf-8") as f:
            f.write(resp.text)
        
        return parse_student_info_html(resp.text)

    # ═══════════════════════════════════════════
    # 考级成绩（四六级等）
    # ═══════════════════════════════════════════

    def get_grade_exams(self) -> list[dict]:
        """获取考级成绩（英语四六级等）"""
        data = {"page": "1", "rows": "100", "sort": "", "order": "asc"}
        result = self._post_json("xskjcjxx!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 上课任务
    # ═══════════════════════════════════════════

    def get_class_tasks(self, semester: str = None) -> list[dict]:
        """获取上课任务"""
        data = {
            "xnxqdm": semester or current_semester(),
            "page": "1",
            "rows": "200",
            "sort": "",
            "order": "asc",
        }
        result = self._post_json("skrwcx!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 考勤情况
    # ═══════════════════════════════════════════

    def get_attendance(self, semester: str = None) -> list[dict]:
        """获取考勤记录"""
        data = {
            "xnxqdm": semester or current_semester(),
            "page": "1",
            "rows": "200",
            "sort": "",
            "order": "asc",
        }
        result = self._post_json("xsgrkqxx!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 体测成绩
    # ═══════════════════════════════════════════

    def get_physical_test(self) -> list[dict]:
        """获取体测成绩"""
        data = {"page": "1", "rows": "100", "sort": "", "order": "asc"}
        result = self._post_json("xstccjxx!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 学籍预警
    # ═══════════════════════════════════════════

    def get_warnings(self) -> list[dict]:
        """获取学籍预警"""
        data = {"page": "1", "rows": "100", "sort": "", "order": "asc"}
        result = self._post_json("xsyjxx!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 学期注册
    # ═══════════════════════════════════════════

    def get_semester_reg(self) -> list[dict]:
        """获取学期注册状态"""
        data = {"page": "1", "rows": "100", "sort": "", "order": "asc"}
        result = self._post_json("xsxqzccx!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 消息通知
    # ═══════════════════════════════════════════

    def get_notices(self) -> list[dict]:
        """获取消息通知"""
        result = self._post_json("notice!getNotice.action")
        if isinstance(result, list):
            return result
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 培养方案
    # ═══════════════════════════════════════════

    def get_training_plan(self) -> list[dict]:
        """获取培养方案"""
        data = {"page": "1", "rows": "100", "sort": "", "order": "asc"}
        result = self._post_json("xsjhcx!getDataList.action", data)
        return result.get("rows", [])

    # ═══════════════════════════════════════════
    # 操作日志
    # ═══════════════════════════════════════════

    def get_operation_log(self) -> list[dict]:
        """获取操作日志"""
        data = {"page": "1", "rows": "50", "sort": "", "order": "asc"}
        result = self._post_json("xsczrz!getDataList.action", data)
        return result.get("rows", [])
