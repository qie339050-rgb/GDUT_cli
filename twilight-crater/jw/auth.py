"""认证模块：Playwright 浏览器登录 + Cookie/Session 管理

登录流程：
1. 弹出真实 Chrome 窗口到 CAS 登录页
2. 用户手动完成登录
3. 检测到跳转至 welcome.action 后自动抓取 Cookie
4. 保存 Cookie 到 ~/.gdut/cookies.json
5. 后续请求使用 requests.Session 复用 Cookie

自动重登：
- 任何 API 调用前检查 Session 是否有效
- 发现过期时自动触发 login 流程
"""

import json
import sys
import requests
from rich.console import Console

from .config import (
    BASE_URL, CAS_LOGIN_URL, WELCOME_URL,
    COOKIES_FILE, DEFAULT_HEADERS,
    ensure_data_dir, logger,
)

console = Console()


class SessionExpiredError(Exception):
    """Session 过期异常"""
    pass


class JWAuth:
    """教务系统认证管理"""

    def login(self) -> requests.Session:
        """弹出浏览器让用户手动登录，抓取 Cookie 并返回 Session"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            console.print(
                "[red]❌ 需要安装 playwright[/red]\n"
                "请执行: [cyan]pip install playwright && playwright install chromium[/cyan]"
            )
            sys.exit(1)

        console.print("[cyan]🌐 正在打开浏览器登录页面...[/cyan]")
        console.print("[yellow]💡 如果没看到浏览器窗口，请检查任务栏[/yellow]")

        with sync_playwright() as p:
            from .config import DATA_DIR
            # 使用持久化上下文（Persistent Context），让浏览器记住登录状态
            user_data_dir = str(DATA_DIR / "browser_data")
            
            launch_args = [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ]

            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    args=launch_args,
                    no_viewport=True,
                    ignore_https_errors=True,
                )
            except Exception as e:
                console.print(f"[red]❌ 启动浏览器失败: {e}[/red]")
                console.print("[yellow]可能是因为浏览器仍在后台运行，请先关闭其他 gdut 进程。[/yellow]")
                sys.exit(1)

            # If there are existing pages, use the first one, otherwise create a new one.
            # This handles cases where the browser was closed but the persistent context still has pages.
            page = context.pages[0] if context.pages else context.new_page()

            # 注入 JS 隐藏 WebDriver 特征（在每个页面加载前执行）
            context.add_init_script("""
                // 删除 webdriver 标记
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // 删除自动化相关属性
                delete window.__driver_evaluate;
                delete window.__webdriver_evaluate;
                delete window.__selenium_evaluate;
                delete window.__fxdriver_evaluate;
                delete window.__driver_unwrapped;
                delete window.__webdriver_unwrapped;
                delete window.__selenium_unwrapped;
                delete window.__fxdriver_unwrapped;
                delete window.__webdriver_script_function;
                delete window.__webdriver_script_func;
                delete window.__webdriver_script_fn;
                delete document.__webdriver_evaluate;
                delete document.__selenium_evaluate;
                delete document.__fxdriver_evaluate;
            """)

            # Navigate to CAS login page only if not already on a relevant page
            if not ("authserver" in page.url or "jxfw.gdut.edu.cn" in page.url):
                page.goto(CAS_LOGIN_URL, wait_until="domcontentloaded")
            page.bring_to_front()

            # 自动切换到"手机号登录"标签
            try:
                # 尝试多种可能的选择器
                phone_tab = (
                    page.locator("text=手机号登录").first
                    or page.locator("text=短信登录").first
                    or page.locator("[data-tab='sms']").first
                )
                if phone_tab:
                    phone_tab.click(timeout=3000)
                    logger.debug("已切换到手机号登录")
            except Exception as e:
                logger.debug(f"切换手机号登录标签失败: {e}，用户可手动切换")

            console.print("[yellow]⏳ 请在浏览器中完成登录，登录成功后窗口会自动关闭[/yellow]")

            try:
                # 等待用户完成登录，最多 5 分钟
                # 匹配多种可能的登录成功跳转 URL
                page.wait_for_url(
                    lambda url: "welcome" in url or ("jxfw.gdut.edu.cn" in url and "login" not in url.split("/")[-1]),
                    timeout=300_000,
                )
            except Exception as e:
                logger.debug(f"等待登录异常: {e}")
                # 检查是否已经到达教务系统（可能URL匹配没生效但实际已登录）
                current_url = page.url
                if "jxfw.gdut.edu.cn" in current_url and "authserver" not in current_url:
                    logger.debug(f"虽然超时但已到达教务系统: {current_url}")
                else:
                    console.print("[red]❌ 登录超时（5分钟），请重试[/red]")
                    context.close() # Changed from browser.close()
                    sys.exit(1)

            # 等一下确保所有 Cookie 都已设置
            page.wait_for_timeout(2000)

            # 保存 Cookie 到文件（供 request 稍后复用）
            self._save_cookies(context)
            
            # 给一点时间让持久化目录落地
            time.sleep(2)
            context.close() # Changed from browser.close()

        # 验证
        # The login method now returns the session directly after saving cookies
        # and closing the browser. The validation will happen in get_session.
        return self.get_session(auto_login=False)

    def open_browser(self):
        """打开教务系统供手动使用，复用本地免密登录状态"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            console.print("[red]❌ 需要安装 playwright[/red]")
            return

        console.print("[cyan]🌐 正在打开教务系统...[/cyan]")
        console.print("[yellow]💡 请直接在弹出的浏览器中使用，使用完毕后关闭浏览器窗口即可[/yellow]")

        with sync_playwright() as p:
            from .config import DATA_DIR
            user_data_dir = str(DATA_DIR / "browser_data")
            
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
                    no_viewport=True,
                    ignore_https_errors=True,
                )
            except Exception as e:
                console.print(f"[red]❌ 启动浏览器失败: {e}[/red]")
                return

            page = context.pages[0] if context.pages else context.new_page()
            
            # 隐藏特征
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)
            
            page.goto(WELCOME_URL)
            page.bring_to_front()
            
            try:
                # 挂起进程直到用户主动关掉页面
                page.wait_for_event("close", timeout=0)
            except Exception:
                pass
                
            # 保存一下走之前可能发生的刷新产生的 Cookie
            self._save_cookies(context)
            context.close()


    def get_session(self, auto_login: bool = True) -> requests.Session:
        """获取有效的 Session
        
        Args:
            auto_login: 如果 Session 过期，是否自动弹出浏览器重新登录
            
        Returns:
            有效的 requests.Session
            
        Raises:
            SessionExpiredError: auto_login=False 时 Session 过期
        """
        # 尝试加载已保存的 Cookie
        cookies = self._load_cookies()
        if cookies:
            session = self._build_session(cookies)
            if self._is_logged_in(session):
                logger.debug("Session 有效，复用已保存的 Cookie")
                return session
            else:
                logger.debug("Session 已过期")

        # Session 无效
        if auto_login:
            console.print("[yellow]🔑 Session 已过期，需要重新登录[/yellow]")
            return self.login()
        else:
            raise SessionExpiredError("Session 已过期，请执行 gdut login")

    def logout(self):
        """清除本地 Session"""
        if COOKIES_FILE.exists():
            COOKIES_FILE.unlink()
            console.print("[green]✅ 已退出登录[/green]")
        else:
            console.print("[yellow]未找到登录信息[/yellow]")

    def _save_cookies(self, context): # Changed signature
        """保存 Playwright Cookie 到文件"""
        ensure_data_dir()
        cookies = context.cookies() # Added this line
        # 只保存教务系统和认证系统的 Cookie
        relevant = [
            c for c in cookies
            if "gdut.edu.cn" in c.get("domain", "")
        ]
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump(relevant, f, ensure_ascii=False, indent=2)
        logger.debug(f"已保存 {len(relevant)} 个 Cookie 到 {COOKIES_FILE}")

    def _load_cookies(self) -> list[dict] | None:
        """从文件加载 Cookie"""
        if not COOKIES_FILE.exists():
            logger.debug("Cookie 文件不存在")
            return None
        try:
            with open(COOKIES_FILE, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            logger.debug(f"加载了 {len(cookies)} 个 Cookie")
            return cookies
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"读取 Cookie 文件失败: {e}")
            return None

    def _build_session(self, cookies: list[dict]) -> requests.Session:
        """用 Playwright 格式的 Cookie 构建 requests.Session"""
        import http.cookiejar

        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)

        for c in cookies:
            domain = c.get("domain", "")
            # requests 需要域名以 . 开头来做域名匹配
            if domain and not domain.startswith("."):
                domain_initial_dot = False
            else:
                domain_initial_dot = True

            cookie = http.cookiejar.Cookie(
                version=0,
                name=c["name"],
                value=c["value"],
                port=None,
                port_specified=False,
                domain=domain,
                domain_specified=bool(domain),
                domain_initial_dot=domain_initial_dot,
                path=c.get("path", "/"),
                path_specified=True,
                secure=c.get("secure", False),
                expires=int(c["expires"]) if c.get("expires", -1) > 0 else None,
                discard=True,
                comment=None,
                comment_url=None,
                rest={"HttpOnly": str(c.get("httpOnly", False))},
            )
            session.cookies.set_cookie(cookie)

        logger.debug(f"Session 构建完成，Cookie 数: {len(session.cookies)}")
        return session

    def _is_logged_in(self, session: requests.Session) -> bool:
        """检查 Session 是否有效（发一个轻量请求看是否被重定向到登录页）"""
        try:
            resp = session.get(
                WELCOME_URL,
                allow_redirects=True,
                timeout=10,
            )
            # 如果被重定向到登录页或认证服务器，说明已过期
            final_url = resp.url
            if "authserver" in final_url or "login" in final_url.split("/")[-1]:
                if "welcome" not in final_url:
                    logger.debug(f"Session 过期，被重定向到: {final_url}")
                    return False
            # 检查页面内容
            if "请求超时" in resp.text or "统一身份认证" in resp.text:
                return False
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.warning(f"检查登录状态失败: {e}")
            return False
