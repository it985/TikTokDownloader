from datetime import datetime
from json import dumps
from time import localtime, strftime
from types import SimpleNamespace
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from ..custom import (
    BITRATE_INFO_TIKTOK_INDEX,
    IMAGE_TIKTOK_INDEX,
    VIDEO_TIKTOK_INDEX,
    condition_filter,
)
from ..tools import DownloaderError
from ..translation import _

if TYPE_CHECKING:
    from datetime import date

    from ..config import Parameter

__all__ = ["Extractor"]


class Extractor:
    statistics_keys = (
        "digg_count",
        "comment_count",
        "collect_count",
        "share_count",
        "play_count",
    )
    statistics_keys_tiktok = (
        "diggCount",
        "commentCount",
        "collectCount",
        "shareCount",
        "playCount",
    )
    detail_necessary_keys = "id"
    comment_necessary_keys = "cid"
    user_necessary_keys = "sec_uid"
    extract_params_tiktok = {
        "sec_uid": "author.secUid",
        "mix_id": "playlistId",
        "uid": "author.id",
        "nickname": "author.nickname",
        "mix_title": "playlistId",  # TikTok 不返回合辑标题
    }
    extract_params = {
        "sec_uid": "author.sec_uid",
        "mix_id": "mix_info.mix_id",
        "uid": "author.uid",
        "nickname": "author.nickname",
        "mix_title": "mix_info.mix_name",
    }

    def __init__(self, params: "Parameter"):
        self.log = params.logger
        self.date_format = params.date_format
        self.cleaner = params.CLEANER
        self.type = {
            "batch": self.__batch,
            "detail": self.__detail,
        }

    def get_user_info(self, data: dict) -> dict:
        try:
            return {
                "nickname": data["nickname"],
                "sec_uid": data["sec_uid"],
                "uid": data["uid"],
            }
        except (KeyError, TypeError):
            self.log.error(_("提取账号信息失败: {data}").format(data=data))
            return {}

    def get_user_info_tiktok(self, data: dict) -> dict:
        try:
            return {
                "nickname": data["user"]["nickname"],
                "sec_uid": data["user"]["secUid"],
                "uid": data["user"]["id"],
            }
        except (KeyError, TypeError):
            self.log.error(_("提取账号信息失败: {data}").format(data=data))
            return {}

    @staticmethod
    def generate_data_object(
        data: dict | list,
    ) -> SimpleNamespace | list[SimpleNamespace]:
        def depth_conversion(element):
            if isinstance(element, dict):
                return SimpleNamespace(
                    **{k: depth_conversion(v) for k, v in element.items()}
                )
            elif isinstance(element, list):
                return [depth_conversion(item) for item in element]
            else:
                return element

        return depth_conversion(data)

    @staticmethod
    def safe_extract(
        data: SimpleNamespace | list[SimpleNamespace],
        attribute_chain: str,
        default: str | int | list | dict | SimpleNamespace = "",
    ):
        attributes = attribute_chain.split(".")
        for attribute in attributes:
            if "[" in attribute:
                parts = attribute.split("[", 1)
                attribute = parts[0]
                index = parts[1].split("]", 1)[0]
                try:
                    index = int(index)
                    data = getattr(data, attribute, None)[index]
                except (IndexError, TypeError, ValueError):
                    return default
            else:
                data = getattr(data, attribute, None)
                if not data:
                    return default
        return data or default

    async def run(
        self,
        data: list[dict],
        recorder,
        type_="detail",
        tiktok=False,
        **kwargs,
    ) -> list[dict]:
        if type_ not in self.type.keys():
            raise DownloaderError
        return await self.type[type_](data, recorder, tiktok, **kwargs)

    async def __batch(
        self,
        data: list[dict],
        recorder,
        tiktok: bool,
        name: str,
        mark: str,
        earliest,
        latest,
        same=True,
    ) -> list[dict]:
        """批量下载作品"""
        container = SimpleNamespace(
            all_data=[],
            template={
                "collection_time": datetime.now().strftime(self.date_format),
            },
            cache=None,
            name=name,
            mark=mark,
            same=same,  # 是否相同作者
            earliest=earliest,
            latest=latest,
        )
        self.__platform_classify_detail(
            data,
            container,
            tiktok,
        )
        container.all_data = self.__clean_extract_data(
            container.all_data,
            self.detail_necessary_keys,
        )
        self.__extract_item_records(container.all_data)
        self.__date_filter(container)
        self.__condition_filter(container)
        await self.__record_data(recorder, container.all_data)
        self.__summary_detail(container.all_data)
        return container.all_data

    @staticmethod
    def __condition_filter(
        container: SimpleNamespace,
    ):
        """自定义筛选作品"""
        result = [i for i in container.all_data if condition_filter(i)]
        container.all_data = result

    def __summary_detail(
        self,
        data: list[dict],
    ):
        """汇总作品数量"""
        self.log.info(_("筛选处理后作品数量: {count}").format(count=len(data)))

    def __extract_batch(
        self,
        container: SimpleNamespace,
        data: SimpleNamespace,
    ) -> None:
        """批量提取作品信息"""
        container.cache = container.template.copy()
        self.__extract_detail_info(container.cache, data)
        self.__extract_account_info(container, data)
        self.__extract_music(container.cache, data)
        self.__extract_statistics(container.cache, data)
        self.__extract_tags(container.cache, data)
        self.__extract_extra_info(container.cache, data)
        self.__extract_additional_info(container.cache, data)
        container.all_data.append(container.cache)

    def __extract_batch_tiktok(
        self,
        container: SimpleNamespace,
        data: SimpleNamespace,
    ) -> None:
        """批量提取作品信息"""

        container.cache = container.template.copy()
        self.__extract_detail_info_tiktok(container.cache, data)
        self.__extract_account_info_tiktok(container, data)
        self.__extract_music(container.cache, data, True)
        self.__extract_statistics_tiktok(container.cache, data)
        self.__extract_tags_tiktok(container.cache, data)
        self.__extract_extra_info_tiktok(container.cache, data)
        self.__extract_additional_info(container.cache, data, True)
        container.all_data.append(container.cache)

    def __extract_extra_info(
        self,
        item: dict,
        data: SimpleNamespace,
    ):
        if e := self.safe_extract(data, "anchor_info"):
            extra = dumps(e, ensure_ascii=False, indent=2, default=lambda x: vars(x))
        else:
            extra = ""
        item["extra"] = extra

    def __extract_extra_info_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
    ):
        # TODO: 尚未适配 TikTok 额外信息
        item["extra"] = ""

    def __extract_commodity_data(
        self,
        item: dict,
        data: SimpleNamespace,
    ):
        pass

    def __extract_game_data(
        self,
        item: dict,
        data: SimpleNamespace,
    ):
        pass

    def __extract_description(self, data: SimpleNamespace) -> str:
        # 2023/11/11: 抖音不再折叠过长的作品描述
        return self.safe_extract(data, "desc")
        # if len(desc := self.safe_extract(data, "desc")) < 107:
        #     return desc
        # long_desc = self.safe_extract(data, "share_info.share_link_desc")
        # return long_desc.split(
        #     "  ", 1)[-1].split("  %s", 1)[0].replace("# ", "#")

    def __clean_description(self, desc: str) -> str:
        return self.cleaner.clear_spaces(self.cleaner.filter(desc))

    def __format_date(
        self,
        data: int,
    ) -> str:
        return strftime(
            self.date_format,
            localtime(data or None),
        )

    def __extract_detail_info(
        self,
        item: dict,
        data: SimpleNamespace,
    ) -> None:
        item["id"] = self.safe_extract(data, "aweme_id")
        item["desc"] = (
            self.__clean_description(
                self.__extract_description(data),
            )
            or item["id"]
        )
        item["create_timestamp"] = self.safe_extract(data, "create_time")
        item["create_time"] = self.__format_date(item["create_timestamp"])
        self.__extract_text_extra(item, data)
        self.__classifying_detail(item, data)

    def __extract_detail_info_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
    ) -> None:
        item["id"] = self.safe_extract(data, "id")
        item["desc"] = (
            self.__clean_description(self.__extract_description(data)) or item["id"]
        )
        item["create_timestamp"] = self.safe_extract(
            data,
            "createTime",
        )
        item["create_time"] = self.__format_date(item["create_timestamp"])
        self.__extract_text_extra_tiktok(item, data)
        self.__classifying_detail_tiktok(item, data)

    def __classifying_detail(
        self,
        item: dict,
        data: SimpleNamespace,
    ) -> None:
        # 作品分类
        if images := self.safe_extract(data, "images"):
            self.__extract_image_info(item, data, images)
        else:
            self.__extract_video_info(
                item,
                data,
                _("视频"),
            )

    def __classifying_detail_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
    ) -> None:
        if images := self.safe_extract(data, "imagePost.images"):
            self.__extract_image_info_tiktok(item, data, images)
        else:
            self.__extract_video_info_tiktok(
                item,
                data,
                _("视频"),
            )

    def __extract_additional_info(
        self,
        item: dict,
        data: SimpleNamespace,
        tiktok=False,
    ):
        item["ratio"] = self.safe_extract(data, "video.ratio")
        item["share_url"] = self.__generate_link(
            item["type"],
            item["id"],
            item["unique_id"] if tiktok else None,
        )

    @staticmethod
    def __generate_link(
        type_: str,
        id_: str,
        unique_id: str = None,
    ) -> str:
        match bool(unique_id), type_:
            case True, "视频":
                return f"https://www.tiktok.com/@{unique_id}/video/{id_}"
            case True, "图集":
                return f"https://www.tiktok.com/@{unique_id}/photo/{id_}"
            case False, "视频":
                return f"https://www.douyin.com/video/{id_}"
            case False, "图集" | "实况":
                return f"https://www.douyin.com/note/{id_}"
            case _:
                return ""

    @staticmethod
    def __clean_share_url(url: str) -> str:
        if not url:
            return url
        parsed_url = urlparse(url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"

    def __extract_image_info(
        self,
        item: dict,
        data: SimpleNamespace,
        images: list[SimpleNamespace],
    ) -> None:
        if any(
            self.safe_extract(
                i,
                "video",
            )
            for i in images
        ):
            self.__set_blank_data(
                item,
                data,
                _("实况"),
            )
            item["downloads"] = [
                self.__classify_slides_item(
                    i,
                )
                for i in images
            ]
        else:
            self.__set_blank_data(
                item,
                data,
                _("图集"),
            )
            item["downloads"] = [
                self.safe_extract(
                    i,
                    "url_list[-1]",
                )
                for i in images
            ]

    def __extract_image_info_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
        images: list,
    ) -> None:
        self.__set_blank_data(
            item,
            data,
            _("图集"),
        )
        item["downloads"] = [
            self.safe_extract(
                i,
                f"imageURL.urlList[{IMAGE_TIKTOK_INDEX}]",
            )
            for i in images
        ]

    def __set_blank_data(
        self,
        item: dict,
        data: SimpleNamespace,
        type_=_("图集"),
    ):
        item["type"] = type_
        item["duration"] = "00:00:00"
        item["uri"] = ""
        item["height"] = -1
        item["width"] = -1
        self.__extract_cover(item, data)

    def __extract_video_info(
        self,
        item: dict,
        data: SimpleNamespace,
        type_=_("视频"),
    ) -> None:
        item["type"] = type_
        item["height"], item["width"], item["downloads"] = (
            self.__extract_video_download(
                data,
            )
        )
        item["duration"] = self.time_conversion(
            self.safe_extract(data, "video.duration", 0)
        )
        item["uri"] = self.safe_extract(data, "video.play_addr.uri")
        self.__extract_cover(item, data, True)

    def __classify_slides_item(
        self,
        item: SimpleNamespace,
    ) -> str:
        if self.safe_extract(item, "video"):
            return self.__extract_video_download(
                item,
            )[-1]
        return self.safe_extract(item, "url_list[-1]")

    def __extract_video_download(
        self,
        data: SimpleNamespace,
    ) -> tuple[int, int, str]:
        bit_rate: list[SimpleNamespace] = self.safe_extract(
            data,
            "video.bit_rate",
            [],
        )
        try:
            bit_rate: list[tuple[int, int, int, int, int, list[str]]] = [
                (
                    i.FPS,
                    i.bit_rate,
                    i.play_addr.data_size,
                    i.play_addr.height,
                    i.play_addr.width,
                    i.play_addr.url_list,
                )
                for i in bit_rate
            ]
            bit_rate.sort(
                key=lambda x: (
                    max(
                        x[3],
                        x[4],
                    ),
                    x[0],
                    x[1],
                    x[2],
                ),
            )
            return (
                (
                    bit_rate[-1][-3],
                    bit_rate[-1][-2],
                    bit_rate[-1][-1][-1],
                )
                if bit_rate
                else (-1, -1, "")
            )
        except AttributeError:
            self.log.error(
                f"视频下载地址解析失败: {data}",
                False,
            )
            height = self.safe_extract(
                bit_rate[0],
                "play_addr.height",
                -1,
            )
            width = self.safe_extract(
                bit_rate[0],
                "play_addr.width",
                -1,
            )
            url = self.safe_extract(
                bit_rate[0],
                "play_addr.url_list[-1]",
            )
            return height, width, url

    def __extract_video_info_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
        type_=_("视频"),
    ) -> None:
        item["type"] = type_
        # item["downloads"] = self.safe_extract(
        #     data,
        #     "video.playAddr",
        # )  # 视频文件大小优先
        item["height"], item["width"], item["downloads"] = (
            self.__extract_video_download_tiktok(
                data,
            )
        )  # 视频分辨率优先
        item["duration"] = self.time_conversion_tiktok(
            self.safe_extract(
                data,
                "video.duration",
                0,
            )
        )
        item["uri"] = self.safe_extract(
            data,
            f"video.bitrateInfo[{BITRATE_INFO_TIKTOK_INDEX}].PlayAddr.Uri",
        )
        self.__extract_cover_tiktok(item, data, True)

    def __extract_video_download_tiktok(
        self,
        data: SimpleNamespace,
    ) -> tuple[int, int, str]:
        bitrate_info: list[SimpleNamespace] = self.safe_extract(
            data,
            "video.bitrateInfo",
            [],
        )
        try:
            bitrate_info: list[tuple[int, str, int, int, list[str]]] = [
                (
                    i.Bitrate,
                    i.PlayAddr.DataSize,
                    i.PlayAddr.Height,
                    i.PlayAddr.Width,
                    i.PlayAddr.UrlList,
                )
                for i in bitrate_info
            ]
            bitrate_info.sort(
                key=lambda x: (
                    max(
                        x[2],
                        x[3],
                    ),
                    x[0],
                    x[1],
                ),
            )
            return (
                (
                    bitrate_info[-1][-3],
                    bitrate_info[-1][-2],
                    bitrate_info[-1][-1][VIDEO_TIKTOK_INDEX],
                )
                if bitrate_info
                else (-1, -1, "")
            )
        except AttributeError:
            self.log.error(
                f"视频下载地址解析失败: {data}",
                False,
            )
            height = self.safe_extract(
                bitrate_info[0],
                "PlayAddr.Height",
                -1,
            )
            width = self.safe_extract(
                bitrate_info[0],
                "PlayAddr.Width",
                -1,
            )
            url = self.safe_extract(
                bitrate_info[0],
                f"PlayAddr.UrlList[{VIDEO_TIKTOK_INDEX}]",
            )
            return height, width, url

    @staticmethod
    def time_conversion(time_: int) -> str:
        second = time_ // 1000
        return f"{second // 3600:0>2d}:{second % 3600 // 60:0>2d}:{second % 3600 % 60:0>2d}"

    @staticmethod
    def time_conversion_tiktok(seconds: int) -> str:
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return "{:02d}:{:02d}:{:02d}".format(int(hours), int(minutes), int(seconds))

    def __extract_text_extra(
        self,
        item: dict,
        data: SimpleNamespace,
    ):
        """作品标签"""
        text = [
            self.safe_extract(i, "hashtag_name")
            for i in self.safe_extract(data, "text_extra", [])
        ]
        item["text_extra"] = [i for i in text if i]

    def __extract_text_extra_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
    ):
        """作品标签"""
        text = [
            self.safe_extract(i, "hashtagName")
            for i in self.safe_extract(data, "textExtra", [])
        ]
        item["text_extra"] = [i for i in text if i]

    def __extract_cover(
        self,
        item: dict,
        data: SimpleNamespace,
        has=False,
    ) -> None:
        if has:
            # 动态封面图链接
            item["dynamic_cover"] = self.safe_extract(
                data, "video.dynamic_cover.url_list[-1]"
            )
            # 静态封面图链接 - 使用第一个链接(高质量)
            item["static_cover"] = self.safe_extract(
                data, "video.cover.url_list[0]"
            )
        else:
            item["dynamic_cover"], item["static_cover"] = "", ""

    def __extract_cover_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
        has=False,
    ) -> None:
        if has:
            # 动态封面图链接
            item["dynamic_cover"] = self.safe_extract(data, "video.dynamicCover")
            # 静态封面图链接 - 使用高质量封面
            item["static_cover"] = self.safe_extract(data, "video.cover")
        else:
            item["dynamic_cover"], item["static_cover"] = "", ""

    def __extract_music(
        self,
        item: dict,
        data: SimpleNamespace,
        tiktok=False,
    ) -> None:
        if music_data := self.safe_extract(data, "music"):
            if tiktok:
                author = self.safe_extract(music_data, "authorName")
                title = self.safe_extract(music_data, "title")
                url = self.safe_extract(music_data, "playUrl")
            else:
                author = self.safe_extract(music_data, "author")
                title = self.safe_extract(music_data, "title")
                url = self.safe_extract(
                    music_data,
                    "play_url.url_list[-1]",
                )  # 部分作品的音乐无法下载

        else:
            author, title, url = "", "", ""
        item["music_author"] = author
        item["music_title"] = title
        item["music_url"] = url

    def __extract_statistics(self, item: dict, data: SimpleNamespace) -> None:
        data = self.safe_extract(data, "statistics")
        for i in self.statistics_keys:
            item[i] = self.safe_extract(
                data,
                i,
                -1,
            )

    def __extract_statistics_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
    ) -> None:
        data = self.safe_extract(data, "stats")
        for i, j in enumerate(self.statistics_keys_tiktok):
            item[self.statistics_keys[i]] = self.safe_extract(
                data,
                j,
                -1,
            )

    def __extract_tags(
        self,
        item: dict,
        data: SimpleNamespace,
    ) -> None:
        if not (t := self.safe_extract(data, "video_tag")):
            item["tag"] = []
        else:
            item["tag"] = [self.safe_extract(i, "tag_name") for i in t]

    def __extract_tags_tiktok(
        self,
        item: dict,
        data: SimpleNamespace,
    ) -> None:
        if not (t := self.safe_extract(data, "textExtra")):
            item["tag"] = []
        else:
            item["tag"] = [self.safe_extract(i, "hashtagName") for i in t]

    def __extract_account_info(
        self,
        container: SimpleNamespace,
        data: SimpleNamespace,
        key="author",
    ) -> None:
        data = self.safe_extract(data, key)
        container.cache["uid"] = self.safe_extract(data, "uid")
        container.cache["sec_uid"] = self.safe_extract(data, "sec_uid")
        # container.cache["short_id"] = self.safe_extract(data, "short_id")
        container.cache["unique_id"] = self.safe_extract(
            data,
            "unique_id",
        )
        container.cache["signature"] = self.safe_extract(data, "signature")
        container.cache["user_age"] = self.safe_extract(data, "user_age", -1)
        self.__extract_nickname_info(container, data)

    def __extract_account_info_tiktok(
        self,
        container: SimpleNamespace,
        data: SimpleNamespace,
        key="author",
    ) -> None:
        data = self.safe_extract(data, key)
        container.cache["uid"] = self.safe_extract(data, "id")
        container.cache["sec_uid"] = self.safe_extract(data, "secUid")
        container.cache["unique_id"] = self.safe_extract(data, "uniqueId")
        container.cache["signature"] = self.safe_extract(data, "signature")
        container.cache["user_age"] = -1
        self.__extract_nickname_info(container, data)

    def __extract_nickname_info(
        self,
        container: SimpleNamespace,
        data: SimpleNamespace,
    ) -> None:
        if container.same:
            container.cache["nickname"] = container.name
            container.cache["mark"] = container.mark or container.name
        else:
            name = self.cleaner.filter_name(
                self.safe_extract(data, "nickname", _("已注销账号")),
                default=_("无效账号昵称"),
            )
            container.cache["nickname"] = name
            container.cache["mark"] = name

    def preprocessing_data(
        self,
        data: list[dict] | dict,
        tiktok: bool = False,
        mode: str = ...,
        mark: str = "",
        user_id: str = "",
    ) -> tuple[
        str,
        str,
        str,
    ]:
        if isinstance(data, dict):
            info = (
                self.get_user_info_tiktok(data) if tiktok else self.get_user_info(data)
            )
            if user_id != (s := info.get("sec_uid")):
                self.log.error(
                    _("sec_user_id {user_id} 与 {s} 不一致").format(
                        user_id=user_id, s=s
                    ),
                )
                return "", "", ""
            name = self.cleaner.filter_name(
                info["nickname"],
                info["uid"],
            )
            mark = self.cleaner.filter_name(
                mark,
                name,
            )
            return (
                info["uid"],
                name,
                mark,
            )
        elif isinstance(data, list):
            match mode:
                case "post":
                    item = self.__select_item(
                        data,
                        user_id,
                        (self.extract_params_tiktok if tiktok else self.extract_params)[
                            "sec_uid"
                        ],
                    )
                    id_, name, mark = self.__extract_pretreatment_data(
                        item,
                        (self.extract_params_tiktok if tiktok else self.extract_params)[
                            "uid"
                        ],
                        (self.extract_params_tiktok if tiktok else self.extract_params)[
                            "nickname"
                        ],
                        mark,
                    )
                    return id_, name, mark

                case _:
                    raise DownloaderError
        else:
            raise DownloaderError

    def __select_item(
        self,
        data: list[dict],
        id_: str,
        key: str,
    ):
        """从多个数据返回对象"""
        for item in data:
            item = self.generate_data_object(item)
            if id_ == self.safe_extract(item, key):
                return item
        raise DownloaderError(_("提取账号信息或合集信息失败，请向作者反馈！"))

    def __extract_pretreatment_data(
        self,
        item: SimpleNamespace,
        id_: str,
        name: str,
        mark: str,
        title: str = None,  # TikTok 合辑需要直接传入标题
    ):
        id_ = self.safe_extract(item, id_)
        name = self.cleaner.filter_name(
            title
            or self.safe_extract(
                item,
                name,
                id_,
            ),
        )
        mark = self.cleaner.filter_name(
            mark,
            name,
        )
        return id_, name.strip(), mark.strip()

    def __platform_classify_detail(
        self,
        data: list[dict],
        container: SimpleNamespace,
        tiktok: bool,
    ) -> None:
        if tiktok:
            [
                self.__extract_batch_tiktok(
                    container,
                    self.generate_data_object(item),
                )
                for item in data
            ]
        else:
            [
                self.__extract_batch(
                    container,
                    self.generate_data_object(item),
                )
                for item in data
            ]

    async def __detail(
        self,
        data: list[dict],
        recorder,
        tiktok: bool,
    ) -> list[dict]:
        container = SimpleNamespace(
            all_data=[],
            template={
                "collection_time": datetime.now().strftime(self.date_format),
            },
            cache=None,
            same=False,
        )
        self.__platform_classify_detail(
            data,
            container,
            tiktok,
        )
        container.all_data = self.__clean_extract_data(
            container.all_data, self.detail_necessary_keys
        )
        self.__extract_item_records(container.all_data)
        await self.__record_data(recorder, container.all_data)
        self.__condition_filter(container)
        return container.all_data











    async def __record_data(self, record, data: list[dict]):
        # 记录数据
        for i in data:
            await record.save(self.__extract_values(record, i))

    @staticmethod
    def __extract_values(record, data: dict) -> list:
        return [data[key] for key in record.field_keys]

    @staticmethod
    def __date_filter(container: SimpleNamespace):
        # print("前", len(container.all_data))  # 调试代码
        result = []
        for item in container.all_data:
            create_time = datetime.fromtimestamp(item["create_timestamp"]).date()
            if container.earliest <= create_time <= container.latest:
                result.append(item)
            # else:
            #     print("丢弃", item)  # 调试代码
        # print("后", len(result))  # 调试代码
        container.all_data = result

    def source_date_filter(
        self,
        data: list[dict],
        earliest: "date",
        latest: "date",
        tiktok=False,
    ) -> list[dict]:
        if tiktok:
            return self.__source_date_filter(
                data,
                "createTime",
                earliest=earliest,
                latest=latest,
            )
        return self.__source_date_filter(
            data,
            earliest=earliest,
            latest=latest,
        )

    def __source_date_filter(
        self,
        data: list[dict],
        key: str = "create_time",
        earliest: "date" = ...,
        latest: "date" = ...,
    ) -> list[dict]:
        result = []
        for item in data:
            if not (create_time := item.get(key, 0)):
                result.append(item)
                continue
            create_time = datetime.fromtimestamp(create_time).date()
            if earliest <= create_time <= latest:
                result.append(item)
        self.__summary_detail(result)
        return result

    @classmethod
    def extract_mix_id(cls, data: dict) -> str:
        data = cls.generate_data_object(data)
        return cls.safe_extract(data, "mix_info.mix_id")

    def __extract_item_records(self, data: list[dict]):
        # 记录提取成功的条目
        for i in data:
            self.log.info(f"{i['type']} {i['id']} 数据提取成功", False)

    @staticmethod
    def __clean_extract_data(data: list[dict], key: str) -> list[dict]:
        # 去除无效数据
        return [i for i in data if i.get(key)]