from asyncio import sleep
from random import randint
from typing import TYPE_CHECKING
from src.translation import _

if TYPE_CHECKING:
    from src.tools import ColorfulConsole


async def wait() -> None:
    """
    设置网络请求间隔时间，仅对获取数据生效，不影响下载文件
    """
    # 随机延时
    await sleep(randint(5, 20) * 0.1)
    # 固定延时
    # await sleep(1)
    # 取消延时
    # pass


def failure_handling() -> bool:
    """批量下载账号作品模式 和 批量下载合集作品模式 获取数据失败时，是否继续执行"""
    # 询问用户
    # return bool(input(_("输入任意字符继续处理账号/合集，直接回车停止处理账号/合集: ")))
    # 继续执行
    return True
    # 结束执行
    # return False


# 全局过滤统计计数器
filter_stats = {"total": 0, "filtered": 0, "image": 0, "live": 0}

def condition_filter(data: dict) -> bool:
    """
    自定义作品筛选规则，例如：筛选作品点赞数、作品类型、视频分辨率等
    需要排除的作品返回 False，否则返回 True
    """
    filter_stats["total"] += 1
    
    # 允许下载所有类型作品（包括图集、实况、视频）
    # work_type = data.get("type")
    # if work_type in ["图集", "实况"]:
    #     filter_stats["filtered"] += 1
    #     if work_type == "图集":
    #         filter_stats["image"] += 1
    #     elif work_type == "实况":
    #         filter_stats["live"] += 1
    #     return False
        
    # if data["ratio"] in ("720p", "540p"):
    #     return False  # 过滤低分辨率的视频作品
    return True

def get_filter_stats():
    """获取过滤统计信息"""
    return filter_stats.copy()

def reset_filter_stats():
    """重置过滤统计信息"""
    filter_stats.update({"total": 0, "filtered": 0, "image": 0, "live": 0})


async def suspend(count: int, console: "ColorfulConsole") -> None:
    """
    批量采集暂停机制：处理指定数量后暂停一段时间
    batches: 每处理多少个账号/合集后暂停
    rest_time: 暂停时间（秒）
    """
    # 启用暂停机制
    batches = 5  # 每处理5个账号后暂停
    if not count % batches:
        rest_time = 60 * 2  # 暂停2分钟
        console.print(
            _(
                "程序连续处理了 {batches} 个数据，为了避免请求频率过高导致账号或 IP 被风控，"
                "程序已经暂停运行，将在 {rest_time} 秒后恢复运行！"
            ).format(batches=batches, rest_time=rest_time),
        )
        await sleep(rest_time)
    # 禁用暂停机制
    # pass


def is_valid_token(token: str) -> bool:
    """Web API 接口模式 和 Web UI 交互模式 token 参数验证"""
    return True
