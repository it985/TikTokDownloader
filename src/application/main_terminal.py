from datetime import date
from pathlib import Path
from platform import system
from time import time
from types import SimpleNamespace
from typing import TYPE_CHECKING, Union

from ..custom import suspend
from ..downloader import Downloader
from ..extract import Extractor
from ..interface import (
    API,
    Account,
    AccountTikTok,
    Info,
    InfoTikTok,
)
from ..link import Extractor as LinkExtractor
from ..link import ExtractorTikTok
from ..manager import Cache
from ..storage import RecordManager, FailedLogger
from ..tools import choose
from ..translation import _

if TYPE_CHECKING:
    from ..config import Parameter
    from ..manager import Database

__all__ = [
    "TikTok",
]


class TikTok:
    ENCODE = "UTF-8-SIG" if system() == "Windows" else "UTF-8"

    def __init__(
        self,
        parameter: "Parameter",
        database: "Database",
        server_mode: bool = False,
    ):
        self.run_command = None
        self.parameter = parameter
        self.database = database
        self.console = parameter.console
        self.logger = parameter.logger
        API.init_progress_object(server_mode)
        self.links = LinkExtractor(parameter)
        self.links_tiktok = ExtractorTikTok(parameter)
        self.downloader = Downloader(parameter, server_mode)
        self.extractor = Extractor(parameter)
        self.storage = bool(parameter.storage_format)
        self.record = RecordManager()
        self.settings = parameter.settings
        self.accounts = parameter.accounts_urls
        self.accounts_tiktok = parameter.accounts_urls_tiktok
        self.running = True
        self.cache = Cache(
            parameter,
            self.database,
            "mark" in parameter.name_format,
            "nickname" in parameter.name_format,
        )
        self.__function = (
            (
                _("批量下载账号作品(抖音)"),
                self.account_acquisition_interactive,
            ),
            (
                _("批量下载账号作品(TikTok)"),
                self.account_acquisition_interactive_tiktok,
            ),
        )
        self.__function_account = (
            (_("使用 accounts_urls 参数的账号链接(推荐)"), self.account_detail_batch),
            (_("手动输入待采集的账号链接"), self.account_detail_inquire),
            (_("从文本文档读取待采集的账号链接"), self.account_detail_txt),
        )
        self.__function_account_tiktok = (
            (
                _("使用 accounts_urls_tiktok 参数的账号链接(推荐)"),
                self.account_detail_batch_tiktok,
            ),
            (_("手动输入待采集的账号链接"), self.account_detail_inquire_tiktok),
            (_("从文本文档读取待采集的账号链接"), self.account_detail_txt_tiktok),
        )

    def _inquire_input(self, tip: str = "", problem: str = "") -> str:
        text = self.console.input(problem or _("请输入{tip}链接: ").format(tip=tip))
        if not text:
            return ""
        elif text.upper() == "Q":
            self.running = False
            return ""
        return text

    async def account_acquisition_interactive_tiktok(self, select=""):
        await self.__secondary_menu(
            _("请选择账号链接来源"),
            function=self.__function_account_tiktok,
            select=select or (self.run_command.pop() if self.run_command else None),
        )
        self.logger.info(_("已退出批量下载账号作品(TikTok)模式"))

    def __summarize_results(self, count: SimpleNamespace, name=_("账号")):
        time_ = time() - count.time
        self.logger.info(
            _(
                "程序共处理 {0} 个{1}，成功 {2} 个，失败 {3} 个，耗时 {4} 分钟 {5} 秒"
            ).format(
                count.success + count.failed,
                name,
                count.success,
                count.failed,
                int(time_ // 60),
                int(time_ % 60),
            )
        )

    async def account_acquisition_interactive(self, select=""):
        await self.__secondary_menu(
            _("请选择账号链接来源"),
            function=self.__function_account,
            select=select or (self.run_command.pop() if self.run_command else None),
        )
        self.logger.info(_("已退出批量下载账号作品(抖音)模式"))

    async def __secondary_menu(
        self,
        problem=_("请选择账号链接来源"),
        function=...,
        select: str | int = ...,
        *args,
        **kwargs,
    ):
        if not select:
            select = choose(
                problem,
                [i[0] for i in function],
                self.console,
            )
        if select.upper() == "Q":
            self.running = False
        try:
            n = int(select) - 1
        except ValueError:
            return
        if n in range(len(function)):
            await function[n][1](*args, **kwargs)

    async def account_detail_batch(self, *args):
        await self.__account_detail_batch(
            self.accounts,
            "accounts_urls",
            False,
        )

    async def account_detail_batch_tiktok(self, *args):
        await self.__account_detail_batch(
            self.accounts_tiktok,
            "accounts_urls_tiktok",
            True,
        )

    async def __account_detail_batch(
        self,
        accounts: list[SimpleNamespace],
        params_name: str,
        tiktok: bool,
    ) -> None:
        count = SimpleNamespace(time=time(), success=0, failed=0)
        self.logger.info(
            _("共有 {count} 个账号的作品等待下载").format(count=len(accounts))
        )
        
        async with FailedLogger(self.parameter.root, self.console) as failed_logger:
            for index, data in enumerate(accounts, start=1):
                if not (
                    sec_user_id := await self.check_sec_user_id(
                        data.url,
                        tiktok,
                    )
                ):
                    reason = "提取账号ID失败，链接无效或格式错误"
                    self.logger.warning(
                        _(
                            "配置文件 {name} 参数的 url {url} 提取 sec_user_id 失败，错误配置：{data}"
                        ).format(
                            name=params_name,
                            url=data.url,
                            data=vars(data),
                        )
                    )
                    await failed_logger.log_failed_link(data.url, reason, "TikTok账号" if tiktok else "抖音账号")
                    count.failed += 1
                    continue
                    
                result = await self.deal_account_detail(
                    index,
                    **vars(data) | {"sec_user_id": sec_user_id},
                    tiktok=tiktok,
                )
                if not result:
                    reason = "账号数据获取失败，可能是私密账号或需要登录"
                    await failed_logger.log_failed_link(data.url, reason, "TikTok账号" if tiktok else "抖音账号")
                    count.failed += 1
                    continue
                count.success += 1
                if index != len(accounts):
                    await suspend(index, self.console)
                    
        self.__summarize_results(count, _("账号"))

    async def check_sec_user_id(self, sec_user_id: str, tiktok=False) -> str:
        match tiktok:
            case True:
                sec_user_id = await self.links_tiktok.run(sec_user_id, "user")
            case False:
                sec_user_id = await self.links.run(sec_user_id, "user")
        return sec_user_id[0] if len(sec_user_id) > 0 else ""

    async def account_detail_inquire(self, *args):
        while url := self._inquire_input(_("账号主页")):
            links = await self.links.run(url, "user")
            if not links:
                self.logger.warning(
                    _("{url} 提取账号 sec_user_id 失败").format(url=url)
                )
                continue
            await self.__account_detail_handle(links, False, *args)

    async def account_detail_inquire_tiktok(self, *args):
        while url := self._inquire_input(_("账号主页")):
            links = await self.links_tiktok.run(url, "user")
            if not links:
                self.logger.warning(
                    _("{url} 提取账号 sec_user_id 失败").format(url=url)
                )
                continue
            await self.__account_detail_handle(links, True, *args)

    async def account_detail_txt(self):
        await self._read_from_txt(
            tiktok=False,
            type_="user",
            error=_("从文本文档提取账号 sec_user_id 失败"),
            callback=self.__account_detail_handle,
        )

    async def _read_from_txt(
        self,
        tiktok=False,
        type_: str = ...,
        error: str = ...,
        callback = ...,
        *args,
        **kwargs,
    ):
        if not (url := self.txt_inquire()):
            return
        link_obj = self.links_tiktok if tiktok else self.links
        links = await link_obj.run(url, type_)
        if not links or not isinstance(links[0], bool | None):
            links = [links]
        if not links[-1]:
            self.logger.warning(error)
            return
        await callback(*links, *args, tiktok=tiktok, **kwargs)

    async def account_detail_txt_tiktok(self):
        await self._read_from_txt(
            tiktok=True,
            type_="user",
            error=_("从文本文档提取账号 sec_user_id 失败"),
            callback=self.__account_detail_handle,
        )

    async def __account_detail_handle(
        self,
        links: list[str],
        tiktok=False,
        *args,
        **kwargs,
    ):
        count = SimpleNamespace(time=time(), success=0, failed=0)
        
        async with FailedLogger(self.parameter.root, self.console) as failed_logger:
            for index, sec in enumerate(links, start=1):
                result = await self.deal_account_detail(
                    index,
                    sec_user_id=sec,
                    tiktok=tiktok,
                    *args,
                    **kwargs,
                )
                if not result:
                    reason = "账号数据获取失败，可能是私密账号或需要登录"
                    await failed_logger.log_failed_link(sec, reason, "TikTok账号" if tiktok else "抖音账号")
                    count.failed += 1
                    continue
                count.success += 1
                if index != len(links):
                    await suspend(index, self.console)
                    
        self.__summarize_results(count, _("账号"))

    async def deal_account_detail(
        self,
        index: int,
        sec_user_id: str,
        mark="",
        tab="post",
        earliest="",
        latest="",
        pages: int = None,
        api=False,
        source=False,
        cookie: str = None,
        proxy: str = None,
        tiktok=False,
        *args,
        **kwargs,
    ):
        self.logger.info(
            _("开始处理第 {index} 个账号").format(index=index)
            if index
            else _("开始处理账号")
        )
        if api:
            info = None
        elif not (
            info := await self.get_user_info_data(
                tiktok,
                cookie,
                proxy,
                sec_user_id=sec_user_id,
            )
        ):
            self.logger.info(
                _("{sec_user_id} 获取账号信息失败，请检查 Cookie 登录状态！").format(
                    sec_user_id=sec_user_id
                )
            )
            if tab in {"favorite", "collection"}:
                return
            self.logger.info(
                _(
                    "如果账号发布作品均为共创作品且该账号均不是作品作者时，请配置已登录的 Cookie 后重新运行程序，其余情况请无视该提示！"
                )
            )
        acquirer = self._get_account_data_tiktok if tiktok else self._get_account_data
        account_data, earliest, latest = await acquirer(
            cookie=cookie,
            proxy=proxy,
            sec_user_id=sec_user_id,
            tab=tab,
            earliest=earliest,
            latest=latest,
            pages=pages,
            **kwargs,
        )
        if not any(account_data):
            return None
        if source:
            return self.extractor.source_date_filter(
                account_data,
                earliest,
                latest,
                tiktok,
            )
        return await self._batch_process_detail(
            account_data,
            user_id=sec_user_id,
            mark=mark,
            api=api,
            earliest=earliest,
            latest=latest,
            tiktok=tiktok,
            mode=tab,
            info=info,
        )

    async def _get_account_data(
        self,
        cookie: str = None,
        proxy: str = None,
        sec_user_id: Union[str] = ...,
        tab: str = "post",
        earliest: str = "",
        latest: str = "",
        pages: int = None,
        *args,
        **kwargs,
    ):
        return await Account(
            self.parameter,
            cookie,
            proxy,
            sec_user_id,
            tab,
            earliest,
            latest,
            pages,
        ).run()

    async def _get_account_data_tiktok(
        self,
        cookie: str = None,
        proxy: str = None,
        sec_user_id: Union[str] = ...,
        tab: str = "post",
        earliest: str = "",
        latest: str = "",
        pages: int = None,
        *args,
        **kwargs,
    ):
        return await AccountTikTok(
            self.parameter,
            cookie,
            proxy,
            sec_user_id,
            tab,
            earliest,
            latest,
            pages,
        ).run()

    async def get_user_info_data(
        self,
        tiktok=False,
        cookie: str = None,
        proxy: str = None,
        unique_id: Union[str] = "",
        sec_user_id: Union[str] = "",
    ):
        return (
            await self._get_info_data_tiktok(
                cookie,
                proxy,
                unique_id,
                sec_user_id,
            )
            if tiktok
            else await self._get_info_data(
                cookie,
                proxy,
                sec_user_id,
            )
        )

    async def _get_info_data(
        self,
        cookie: str = None,
        proxy: str = None,
        sec_user_id: Union[str, list[str]] = ...,
    ):
        return await Info(
            self.parameter,
            cookie,
            proxy,
            sec_user_id,
        ).run()

    async def _get_info_data_tiktok(
        self,
        cookie: str = None,
        proxy: str = None,
        unique_id: Union[str] = "",
        sec_user_id: Union[str] = "",
    ):
        return await InfoTikTok(
            self.parameter,
            cookie,
            proxy,
            unique_id,
            sec_user_id,
        ).run()

    async def _batch_process_detail(
        self,
        data: list[dict],
        api: bool = False,
        earliest: date = None,
        latest: date = None,
        tiktok: bool = False,
        info: dict = None,
        mode: str = "",
        mark: str = "",
        user_id: str = "",
        mix_id: str = "",
        mix_title: str = "",
        collect_id: str = "",
        collect_name: str = "",
    ):
        self.logger.info(_("开始提取作品数据"))
        id_, name, mark = self.extractor.preprocessing_data(
            info or data,
            tiktok,
            mode,
            mark,
            user_id,
        )
        if not api and not all((id_, name, mark)):
            self.logger.error(_("提取账号或合集信息发生错误！"))
            return False
        self.__display_extracted_information(id_, name, mark)
        prefix = "UID"
        suffix = _("发布作品")
        old_mark = (
            f"{m['MARK']}_{suffix}" if (m := await self.cache.has_cache(id_)) else None
        )
        root, params, logger = self.record.run(self.parameter, blank=api)
        async with logger(
            root,
            name=f"{prefix}{id_}_{mark}_{suffix}",
            old=old_mark,
            console=self.console,
            **params,
        ) as recorder:
            data = await self.extractor.run(
                data,
                recorder,
                type_="batch",
                tiktok=tiktok,
                name=name,
                mark=mark,
                earliest=earliest or date(2016, 9, 20),
                latest=latest or date.today(),
                same=True,
            )
        if api:
            return data
        await self.cache.update_cache(
            self.parameter.folder_mode,
            prefix,
            suffix,
            id_,
            name,
            mark,
        )
        await self.download_detail_batch(
            data,
            tiktok=tiktok,
            mode=mode,
            mark=mark,
            user_id=id_,
            user_name=name,
        )
        return True

    def __display_extracted_information(
        self,
        id_: str,
        name: str,
        mark: str,
    ) -> None:
        self.logger.info(
            _("昵称/标题：{name}；标识：{mark}；ID：{id}").format(
                name=name,
                mark=mark,
                id=id_,
            ),
        )

    async def download_detail_batch(
        self,
        data: list[dict],
        type_: str = "batch",
        tiktok: bool = False,
        mode: str = "",
        mark: str = "",
        user_id: str = "",
        user_name: str = "",
        mix_id: str = "",
        mix_title: str = "",
        collect_id: str = "",
        collect_name: str = "",
    ):
        await self.downloader.run(
            data,
            type_,
            tiktok,
            mode=mode,
            mark=mark,
            user_id=user_id,
            user_name=user_name,
            mix_id=mix_id,
            mix_title=mix_title,
            collect_id=collect_id,
            collect_name=collect_name,
        )

    def txt_inquire(self) -> str:
        if path := self.console.input(_("请输入文本文档路径：")):
            if (t := Path(path.replace('"', ""))).is_file():
                try:
                    with t.open("r", encoding=self.ENCODE) as f:
                        return f.read()
                except UnicodeEncodeError as e:
                    self.logger.warning(
                        _("{path} 文件读取异常: {error}").format(path=path, error=e)
                    )
            else:
                self.console.print(_("{path} 文件不存在！").format(path=path))
        return ""

    async def run(self, run_command: list):
        self.run_command = run_command
        while self.running:
            if not (select := (self.run_command.pop() if self.run_command else None)):
                select = choose(
                    _("请选择采集功能"),
                    [i for i, __ in self.__function],
                    self.console,
                )
            if select in {"Q", "q"}:
                self.running = False
            try:
                n = int(select) - 1
            except ValueError:
                break
            if n in range(len(self.__function)):
                await self.__function[n][1](self.run_command.pop() if self.run_command else None)
