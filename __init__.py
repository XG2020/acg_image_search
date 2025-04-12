import httpx
from typing import List
from pydantic import BaseModel, Field
from nekro_agent.core import logger

from nekro_agent.services.plugin.base import NekroPlugin, ConfigBase, SandboxMethodType
from nekro_agent.api.schemas import AgentCtx

# 插件实例
plugin = NekroPlugin(
    name="ACG图片搜索插件",
    module_name="acg_image_search",
    description="提供二次元图片搜索功能",
    version="1.0.0",
    author="XG.GM, Zaxpris, wess09",
    url="https://github.com/XG2020/acg_image_search",
)

@plugin.mount_config()
class ACGImageConfig(ConfigBase):
    """ACG图片搜索配置"""
    API_URL: str = Field(
        default="https://api.lolicon.app/setu/v2",
        title="Lolicon API地址",
        description="二次元图片API的基础URL",
    )
    TIMEOUT: float = Field(
        default=10.0,
        title="请求超时时间",
        description="API请求的超时时间(秒)",
    )
    R18_ENABLED: bool = Field(
        default=False,
        title="R18内容开关",
        description="是否允许获取R18内容",
    )
    MAX_TAGS: int = Field(
        default=3,
        title="最大标签数量",
        description="每次搜索允许的最大标签数量",
    )

# 获取配置
config = plugin.get_config(ACGImageConfig)

@plugin.mount_sandbox_method(
    SandboxMethodType.MULTIMODAL_AGENT,
    name="二次元图片搜索",
    description="通过标签搜索二次元图片并返回图片字节流",
)
async def acg_image_search(_ctx: AgentCtx, tags: List[str]) -> bytes:
    """通过标签搜索二次元图片
    
    获取符合标签条件的二次元图片并返回JPEG格式的图片字节流
    每个搜索最多支持3个标签
    
    Args:
        tags: 搜索标签列表，如 ["初音未来", "天使", "蓝色"]
        
    Returns:
        bytes: JPEG格式的图片字节流
        
    Raises:
        会捕获所有异常并返回友好的错误消息
        
    Example:
        acg_image_search(["初音未来", "天使"])
    """
    try:
        # 清理和验证标签
        clean_tags = [t.strip() for t in tags if t.strip()]
        if len(clean_tags) > config.MAX_TAGS:
            raise ValueError(f"最多支持{config.MAX_TAGS}个标签")
            
        params = {
            "r18": 2 if config.R18_ENABLED else 0,
            "num": 1,
            "tag": clean_tags,
            "size": "original"
        }

        # 调用Lolicon API
        async with httpx.AsyncClient(timeout=config.TIMEOUT) as client:
            response = await client.post(config.API_URL, json=params)
            response.raise_for_status()
            data = response.json()
            
            # 检查返回数据
            if not data.get("data"):
                return "未找到匹配的图片".encode()
                
            # 获取图片URL
            first_item = data["data"][0]
            image_url = first_item["urls"].get("original")
            if not image_url:
                return "[Lolicon] 无效的图片规格".encode()
                
            # 下载图片
            image_response = await client.get(image_url, timeout=config.TIMEOUT)
            image_response.raise_for_status()
            return image_response.content
            
    except httpx.RequestError as e:
        logger.error(f"图片搜索请求失败: {e}")
        return f"请求API失败: {str(e)}".encode()
    except httpx.HTTPStatusError as e:
        logger.error(f"图片搜索API错误: {e}")
        return f"API返回错误: {e.response.status_code}".encode()
    except (KeyError, IndexError) as e:
        logger.error(f"图片数据解析错误: {e}")
        return f"解析图片数据失败: {str(e)}".encode()
    except ValueError as e:
        logger.error(f"参数验证错误: {e}")
        return str(e).encode()
    except Exception as e:
        logger.error(f"图片搜索未知错误: {e}")
        return f"发生未知错误: {str(e)}".encode()

@plugin.mount_cleanup_method()
async def clean_up():
    """清理插件资源"""
    logger.info("ACG图片搜索插件资源已清理")