import httpx
from typing import List
from pydantic import BaseModel, Field

from nekro_agent.services.plugin.base import NekroPlugin, ConfigBase, SandboxMethodType
from nekro_agent.api.schemas import AgentCtx
from nekro_agent.core import logger

# 插件实例
plugin = NekroPlugin(
    name="ACG图片搜索插件",
    module_name="acg_image_search",
    description="提供二次元图片搜索功能",
    version="1.0.0",
    author="XGGM",
    url="https://github.com/XG2020/acg_image_search",
)

@plugin.mount_config()
class AcgImageConfig(ConfigBase):
    """ACG图片搜索配置"""
    API_URL: str = Field(
        default="https://api.lolicon.app/setu/v2",
        title="API地址",
        description="lolicon API的基础URL",
    )
    R18_ENABLED: bool = Field(
        default=False,
        title="R18内容开关",
        description="是否允许R18内容",
    )
    TIMEOUT: float = Field(
        default=10.0,
        title="请求超时时间",
        description="API请求的超时时间(秒)",
    )
    MAX_TAGS: int = Field(
        default=3,
        title="最大标签数",
        description="允许的最大搜索标签数量",
    )

# 获取配置
config = plugin.get_config(AcgImageConfig)

async def fetch_image_data(tags: List[str]) -> str:
    """获取图片URL数据
    
    Args:
        tags: 搜索标签列表
        
    Returns:
        str: 图片URL或错误消息
        
    Raises:
        httpx.RequestError: 请求失败时抛出
        httpx.HTTPStatusError: HTTP状态错误时抛出
        KeyError: 数据解析错误时抛出
    """
    params = {
        "r18": 2 if config.R18_ENABLED else 0,
        "num": 1,
        "tag": tags,
        "size": "original"
    }
    
    async with httpx.AsyncClient(timeout=config.TIMEOUT) as client:
        response = await client.post(config.API_URL, json=params)
        response.raise_for_status()
        data = response.json()
        return data["data"][0]["urls"]["original"]

async def download_image(url: str) -> bytes:
    """下载图片数据
    
    Args:
        url: 图片URL
        
    Returns:
        bytes: 图片字节流
        
    Raises:
        httpx.RequestError: 请求失败时抛出
        httpx.HTTPStatusError: HTTP状态错误时抛出
    """
    async with httpx.AsyncClient(timeout=config.TIMEOUT) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content

@plugin.mount_sandbox_method(
    SandboxMethodType.TOOL,
    name="acg_image_search",
    description="二次元图片搜索，获取图片字节流",
)
async def acg_image_search(_ctx: AgentCtx, tags: List[str]) -> bytes:
    """二次元图片搜索
    
    根据提供的标签列表搜索并返回图片字节流，仅返回.jpg格式图片。
    最多支持3个标签同时搜索。
    
    Args:
        tags: 搜索标签列表，最多3个标签
        
    Returns:
        bytes: 图片字节流
        
    Raises:
        ValueError: 如果标签数量超过限制或为空
        
    Examples:
        acg_image_search(["初音未来"])
        acg_image_search(["明日方舟", "能天使"])
    """
    if not tags:
        raise ValueError("至少需要提供一个搜索标签")
    if len(tags) > config.MAX_TAGS:
        raise ValueError(f"最多支持{config.MAX_TAGS}个标签同时搜索")
        
    clean_tags = [t.strip() for t in tags if t.strip()]
    
    try:
        # 获取图片URL
        image_url = await fetch_image_data(clean_tags)
        
        # 下载图片
        if image_url.startswith("http"):
            return await download_image(image_url)
        return image_url.encode()
        
    except httpx.RequestError as e:
        logger.error(f"图片搜索请求失败: {e}")
        return f"图片搜索失败，无法连接到服务: {str(e)}".encode()
    except httpx.HTTPStatusError as e:
        logger.error(f"图片搜索HTTP错误: {e}")
        return f"图片搜索失败，服务返回错误: {e.response.status_code}".encode()
    except KeyError as e:
        logger.error(f"图片数据解析错误: {e}")
        return "图片搜索结果格式不正确".encode()
    except Exception as e:
        logger.error(f"图片搜索未知错误: {e}")
        return f"图片搜索发生未知错误: {str(e)}".encode()

@plugin.mount_cleanup_method()
async def clean_up():
    """清理插件资源"""
    logger.info("ACG图片搜索插件资源已清理")
