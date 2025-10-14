from json import dump, load
from json.decoder import JSONDecodeError
from platform import system
from shutil import move
from types import SimpleNamespace
from typing import TYPE_CHECKING

from ..translation import _

if TYPE_CHECKING:
    from pathlib import Path

    from ..tools import ColorfulConsole

__all__ = ["Settings"]


class Settings:
    encode = "UTF-8-SIG" if system() == "Windows" else "UTF-8"
    default = {
        # ===== 批量下载账号配置 =====
        "accounts_urls": [  # 抖音账号批量下载配置
            {
                "mark": "",  # 自定义账号标识，用于文件夹命名
                "url": "",   # 抖音账号主页链接
                "tab": "",   # 下载类型: post(发布) favorite(喜欢) collection(收藏)
                "earliest": "",  # 最早日期筛选 格式: 2024-01-01
                "latest": "",    # 最新日期筛选 格式: 2024-12-31
                "enable": True,  # 是否启用此配置
            },
        ],
        "accounts_urls_tiktok": [  # TikTok账号批量下载配置
            {
                "mark": "",  # 自定义账号标识
                "url": "",   # TikTok账号主页链接
                "tab": "",   # 下载类型: post(发布) favorite(喜欢)
                "earliest": "",  # 最早日期筛选
                "latest": "",    # 最新日期筛选
                "enable": True,  # 是否启用此配置
            },
        ],
        # ===== 批量下载合集配置 =====
        "mix_urls": [  # 抖音合集批量下载配置
            {
                "mark": "",  # 自定义合集标识
                "url": "",   # 抖音合集链接
                "enable": True,  # 是否启用此配置
            },
        ],
        "mix_urls_tiktok": [  # TikTok合集批量下载配置
            {
                "mark": "",  # 自定义合集标识
                "url": "",   # TikTok合集链接
                "enable": True,  # 是否启用此配置
            },
        ],
        # ===== 收藏作品配置 =====
        "owner_url": {  # 当前登录账号信息(用于下载收藏作品)
            "mark": "",     # 账号标识
            "url": "",      # 账号主页链接
            "uid": "",      # 用户ID
            "sec_uid": "",  # 安全用户ID
            "nickname": "", # 昵称
        },
        "owner_url_tiktok": None,  # TikTok收藏配置(暂未支持)
        
        # ===== 文件存储配置 =====
        "root": "",  # 下载根目录，空则使用程序目录
        "folder_name": "Download",  # 下载文件夹名称
        "name_format": "create_time type nickname desc",  # 文件命名格式
        "date_format": "%Y-%m-%d %H:%M:%S",  # 日期格式
        "split": "-",  # 文件名分隔符
        "folder_mode": False,  # 是否按账号/合集创建子文件夹
        "music": False,  # 是否下载音乐文件
        "truncate": 50,  # 文件名长度限制(字符数)
        "storage_format": "",  # 数据存储格式: csv/xlsx/sqlite
        
        # ===== 登录凭证配置 =====
        "cookie": "",  # 抖音Cookie(字符串或字典格式)
        "cookie_tiktok": "",  # TikTok Cookie
        
        # ===== 下载内容配置 =====
        "dynamic_cover": False,  # 是否下载动态封面
        "static_cover": False,   # 是否下载静态封面
        
        # ===== 网络配置 =====
        "proxy": "",  # 抖音代理设置 格式: http://127.0.0.1:7890
        "proxy_tiktok": "",  # TikTok代理设置
        "twc_tiktok": "",  # TikTok网络配置
        
        # ===== 下载控制配置 =====
        "download": True,  # 是否实际下载文件(False仅获取数据)
        "max_size": 0,  # 文件大小上限(字节) 0表示无限制
        "chunk": 1024 * 1024 * 2,  # 下载块大小(2MB)
        "timeout": 10,  # 网络请求超时时间(秒)
        "max_retry": 5,  # 请求失败最大重试次数
        "max_pages": 0,  # 最大请求页数 0表示无限制
        
        # ===== 程序运行配置 =====
        "run_command": "",  # 启动命令参数
        "ffmpeg": "",  # FFmpeg路径(用于直播下载)
        "live_qualities": "",  # 直播画质选择
        "douyin_platform": True,  # 是否启用抖音平台功能
        "tiktok_platform": True,  # 是否启用TikTok平台功能
        "browser_info": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "pc_libra_divert": "Windows",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "136.0.0.0",
            "engine_name": "Blink",
            "engine_version": "136.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "webid": "",
        },
        "browser_info_tiktok": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "app_language": "zh-Hans",
            "browser_language": "zh-SG",
            "browser_name": "Mozilla",
            "browser_platform": "Win32",
            "browser_version": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "language": "zh-Hans",
            "os": "windows",
            "priority_region": "CN",
            "region": "US",
            "tz_name": "Asia/Shanghai",
            "webcast_language": "zh-Hans",
            "device_id": "",
        },
    }  # 默认配置
    rename_params = (
        (
            "default_mode",
            "run_command",
            "",
        ),
        (
            "update_cookie",
            "douyin_platform",
            True,
        ),
        (
            "update_cookie_tiktok",
            "tiktok_platform",
            True,
        ),
        (
            "original_cover",
            "static_cover",
            False,
        ),
    )  # 兼容旧版本配置文件

    def __init__(self, root: "Path", console: "ColorfulConsole"):
        self.root = root
        self.file = "settings.json"
        self.path = root.joinpath(self.file)  # 配置文件
        self.console = console

    def __create(self) -> dict:
        """创建默认配置文件"""
        with self.path.open("w", encoding=self.encode) as f:
            dump(self.default, f, indent=4, ensure_ascii=False)
        self.console.info(
            _(
                "创建默认配置文件 settings.json 成功！\n"
                "请参考项目文档的快速入门部分，设置 Cookie 后重新运行程序！\n"
                "建议根据实际使用需求修改配置文件 settings.json！\n"
            ),
        )
        return self.default

    def read(self) -> dict:
        """读取配置文件，如果没有配置文件，则生成配置文件"""
        self.compatible()
        try:
            if self.path.exists():
                with self.path.open("r", encoding=self.encode) as f:
                    return self.__check(load(f))
            return self.__create()  # 生成的默认配置文件必须设置 cookie 才可以正常运行
        except JSONDecodeError:
            self.console.error(
                _("配置文件 settings.json 格式错误，请检查 JSON 格式！"),
            )
            return self.default  # 读取配置文件发生错误时返回空配置

    def __check(self, data: dict) -> dict:
        data = self.__compatible_with_old_settings(data)
        update = False
        for i, j in self.default.items():
            if i not in data:
                data[i] = j
                update = True
                self.console.info(
                    _("配置文件 settings.json 缺少参数 {i}，已自动添加该参数！").format(
                        i=i
                    ),
                )
        if update:
            self.update(data)
        return data

    def update(self, settings: dict | SimpleNamespace):
        """更新配置文件"""
        with self.path.open("w", encoding=self.encode) as f:
            dump(
                settings if isinstance(settings, dict) else vars(settings),
                f,
                indent=4,
                ensure_ascii=False,
            )
        self.console.info(
            _("保存配置成功！"),
        )

    def __compatible_with_old_settings(
        self,
        data: dict,
    ) -> dict:
        """兼容旧版本配置文件"""
        for old, new_, default in self.rename_params:
            if old in data:
                self.console.info(
                    _(
                        "配置文件 {old} 参数已变更为 {new} 参数，请注意修改配置文件！"
                    ).format(old=old, new=new_),
                )
                data[new_] = data.get(
                    new_,
                    data.get(
                        old,
                        default,
                    ),
                )
        return data

    def compatible(self):
        if (
            old := self.root.parent.joinpath(self.file)
        ).exists() and not self.path.exists():
            move(old, self.path)
