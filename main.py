import json
import os
from typing import Optional, Any
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
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

    async def fetch_streaming_data(self, url: str, headers: dict, payload: dict) -> list:
        """从 Coze API 获取流式数据并存入缓冲区"""
        buffer = []
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, headers=headers, json=payload, timeout=60.0) as response:
                    logger.info(f"扣子 API 流式响应状态: {response.status_code}")
                    if response.status_code != 200:
                        error_message = await response.aread()
                        logger.error(f"扣子 API 请求失败: {response.status_code} - {error_message.decode()}")
                        return []
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            try:
                                event_data = json.loads(line[5:].strip())
                                if isinstance(event_data, dict):
                                    buffer.append(event_data)
                                else:
                                    logger.warning(f"流式事件数据非字典: {event_data}")
                            except json.JSONDecodeError as e:
                                logger.error(f"解析流式事件失败: {line} - {str(e)}")
                                continue
        except httpx.HTTPError as e:
            logger.error(f"调用扣子 API 时发生网络错误: {e}")
            return []
        return buffer

    def process_complete_data(self, buffer: list) -> str:
        """处理缓冲区中的完整数据，生成最终输出"""
        full_content = ""
        for event in buffer:
            event_type = event.get("event")
            event_content = event.get("data", {})
            if event_type == "conversation.message.delta":
                content = event_content.get("content", "")
                if content:
                    full_content += content
            elif event_type == "conversation.message.completed":
                if event_content.get("role") == "assistant" and event_content.get("content"):
                    return event_content["content"]
            elif event_type == "error":
                logger.error(f"流式响应错误: {event.get('code')} - {event.get('msg')}")
                return f"智能体返回错误: {event.get('msg', '未知错误')}"
        return full_content if full_content else "未能获取智能体回复，可能无有效响应内容"

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
            user_id = event.session_id if event.session_id else "123"
            payload = {
                "bot_id": self.config['bot_id'],
                "user_id": user_id,
                "stream": True,
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

            # 获取流式数据
            buffer = await self.fetch_streaming_data(self.config['api_url'], headers, payload)
            # 处理并输出完整结果
            final_output = self.process_complete_data(buffer)
            yield event.plain_result(final_output)

        except Exception as e:
            logger.error(f"Astrbot-Coze-Plugin 内部错误: {e}")
            yield event.plain_result(f"插件内部错误，请联系管理员: {str(e)}")

    async def on_load(self):
        logger.info("Astrbot-Coze-Plugin 已加载")

    async def terminate(self):
        logger.info("Astrbot-Coze-Plugin 已卸载")
