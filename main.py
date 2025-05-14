from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import httpx
import json
from typing import Optional

@register(
    name="coze_api",
    author="YourName",
    description="一个调用Coze API的AstrBot插件",
    version="1.0.0",
    repo_url="https://github.com/yourname/astrbot_plugin_coze"
)
class CozePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.access_token: Optional[str] = None
        self.bot_id: Optional[str] = None
        self.api_url: str = "https://api.coze.cn/v3/chat"
        self.load_config()

    def load_config(self):
        """加载Coze API配置"""
        try:
            config = self.context.get_config()
            self.access_token = config.get("access_token")
            self.bot_id = config.get("bot_id")
            self.api_url = config.get("api_url", "https://api.coze.cn/v3/chat")
            if not self.access_token or not self.bot_id:
                logger.error("Coze API配置缺失，请在AstrBot配置文件中设置access_token和bot_id")
        except Exception as e:
            logger.error(f"加载Coze配置失败: {str(e)}")

    async def call_coze_api(self, message: str, conversation_id: str = None) -> dict:
        """调用Coze API"""
        if not self.access_token or not self.bot_id:
            return {"error": "Coze API配置缺失"}

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }
        payload = {
            "bot_id": self.bot_id,
            "user_id": "astrbot_user",
            "messages": [
                {
                    "role": "user",
                    "content": message,
                    "content_type": "text"
                }
            ],
            "stream": False
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, headers=headers, json=payload, timeout=30)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Coze API请求失败: {e.response.status_code} {e.response.text}")
            return {"error": f"API请求失败: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Coze API调用异常: {str(e)}")
            return {"error": str(e)}

    @filter.command("coze")
    async def coze_command(self, event: AstrMessageEvent, message: str = ""):
        """调用Coze API的指令
        用法: /coze <消息内容>
        示例: /coze 你好，Coze！
        """
        if not message:
            yield event.plain_result("请提供消息内容，例如：/coze 你好")
            return

        try:
            logger.info(f"用户 {event.get_sender_name()} 调用Coze API: {message}")
            response = await self.call_coze_api(message)
            
            if "error" in response:
                yield event.plain_result(f"错误: {response['error']}")
                return

            # 解析Coze API响应
            if response.get("code") == 0:
                messages = response.get("data", {}).get("messages", [])
                for msg in messages:
                    if msg.get("role") == "assistant" and msg.get("content"):
                        content = msg.get("content", "")
                        yield event.plain_result(content)
                        return
                yield event.plain_result("未收到有效回复")
            else:
                yield event.plain_result(f"Coze API错误: {response.get('msg', '未知错误')}")
        except Exception as e:
            logger.error(f"处理Coze指令时出错: {str(e)}")
            yield event.plain_result(f"发生错误: {str(e)}")

    async def terminate(self):
        """插件卸载时调用"""
        logger.info("Coze插件已卸载")
