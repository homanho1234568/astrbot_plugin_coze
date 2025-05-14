import json
import os
from typing import Optional, Any
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent, EventMessageType
from astrbot.api import logger
import httpx
import asyncio

@register("Astrbot-Coze-Plugin", "Homanho", "一个用于与扣子 AI 智能体 API 交互的插件", "v1.0.0", "https://github.com/homanho1234568/astrbot_plugin_coze")
class AstrbotCozePlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None, db: Optional[Any] = None):
        logger.info(f"Astrbot-Coze-Plugin 初始化接收到 context: {context}, config: {config}, db: {db}")
        super().__init__(context)
        self.config = config or {}
        self.db = db
        if not self.config and hasattr(context, 'config'):
            self.config = getattr(context, 'config', {})
        if not self.db and hasattr(context, 'db'):
            self.db = getattr(context, 'db', None)
        logger.info(f"Astrbot-Coze-Plugin 初始化完成，config: {self.config}, db: {self.db}")

    def validate_config(self) -> tuple[bool, Optional[str]]:
        required_fields = ["bot_id", "access_token", "api_url"]
        for field in required_fields:
            if not self.config.get(field):
                return False, f"配置错误：'{field}' 缺失或为空。"
        return True, None

    async def poll_chat_status(self, chat_id: str, headers: dict) -> dict:
        """轮询 Coze API 直到获取最终回复"""
        poll_url = f"https://api.coze.cn/v3/chat/{chat_id}"
        for _ in range(10):  # 最多尝试 10 次
            async with httpx.AsyncClient() as client:
                response = await client.get(poll_url, headers=headers, timeout=30.0)
                logger.info(f"轮询响应: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    result = response.json()
                    if result.get("data", {}).get("status") == "completed":
                        return result
                await asyncio.sleep(2)  # 等待 2 秒
        return {}

    @filter.command("coze")
    async def handle_coze_command(self, event: AstrMessageEvent):
        try:
            is_valid, error_msg = self.validate_config()
            if not is_valid:
                yield event.plain_result(error_msg + " 请在 WebUI 管理面板中配置插件。")
                return

            full_message = event.message_str.strip()
            parts = full_message.split(" ", 1)
            user_input = parts[1].strip() if len(parts) > 1 else ""

            if not user_input:
                yield event.plain_result("请输入要发送给智能体的消息，例如：/coze 你好")
                return

            headers = {
                "Authorization": f"Bearer {self.config['access_token']}",
                "Content-Type": "application/json"
            }
            payload = {
                "bot_id": self.config['bot_id'],
                "user_id": event.session_id or "123",
                "stream": False,
                "auto_save_history": True,
                "additional_messages": [
                    {
                        "type": "question",
                        "role": "user",
                        "content_type": "text",
                        "content": user_input,
                        "meta_data": {"key_1": "Homan"}
                    }
                ]
            }
            logger.info(f"发送扣子 API 请求: {json.dumps(payload, ensure_ascii=False)}")

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config['api_url'],
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

            logger.info(f"扣子 API 响应: {response.status_code} - {response.text}")
            if response.status_code == 200:
                result = response.json()
                chat_id = result.get("data", {}).get("id")
                if not chat_id:
                    yield event.plain_result("未获取到有效的聊天 ID")
                    return

                # 轮询获取最终回复
                final_result = await self.poll_chat_status(chat_id, headers)
                if final_result and final_result.get("data", {}).get("status") == "completed":
                    messages = final_result.get("data", {}).get("messages", [])
                    for msg in messages:
                        if msg.get("role") == "assistant" and msg.get("content"):
                            yield event.plain_result(msg["content"])
                            return
                    yield event.plain_result("智能体未返回有效回复")
                else:
                    yield event.plain_result("未能获取智能体回复，可能超时或处理失败")
            else:
                error_message = response.json().get("error", {}).get("message", "未知错误")
                logger.error(f"扣子 API 请求失败: {response.status_code} - {error_message}")
                yield event.plain_result(f"调用智能体失败：HTTP {response.status_code} - {error_message}")
        except httpx.HTTPError as e:
            logger.error(f"调用扣子 API 时发生网络错误: {e}")
            yield event.plain_result("调用智能体时发生网络错误，请稍后重试")
        except Exception as e:
            logger.error(f"Astrbot-Coze-Plugin 内部错误: {e}")
            yield event.plain_result(f"插件内部错误，请联系管理员: {str(e)}")

    async def on_load(self):
        logger.info("Astrbot-Coze-Plugin 已加载")

    async def terminate(self):
        logger.info("Astrbot-Coze-Plugin 已卸载")
