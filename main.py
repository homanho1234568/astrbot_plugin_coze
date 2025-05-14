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
            # 使用 session_id 作为 user_id，假设其为 QQ 号或类似标识
            user_id = event.session_id if event.session_id else "123"
            payload = {
                "bot_id": self.config['bot_id'],
                "user_id": user_id,
                "stream": True,  # 默认启用流式传输
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
                async with client.stream(
                    "POST",
                    self.config['api_url'],
                    headers=headers,
                    json=payload,
                    timeout=60.0
                ) as response:
                    logger.info(f"扣子 API 流式响应状态: {response.status_code}")
                    if response.status_code != 200:
                        error_message = await response.aread()
                        logger.error(f"扣子 API 请求失败: {response.status_code} - {error_message.decode()}")
                        yield event.plain_result(f"调用智能体失败：HTTP {response.status_code} - {error_message.decode()}")
                        return

                    full_content = ""
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            try:
                                event_data = json.loads(line[5:].strip())
                                logger.debug(f"流式事件: {json.dumps(event_data, ensure_ascii=False)}")
                                event_type = event_data.get("event")
                                event_content = event_data.get("data", {})

                                if event_type == "conversation.message.delta":
                                    content = event_content.get("content", "")
                                    if content:
                                        full_content += content
                                        yield event.plain_result(content)  # 实时输出增量内容

                                elif event_type == "conversation.message.completed":
                                    if event_content.get("role") == "assistant" and event_content.get("content"):
                                        if full_content:
                                            yield event.plain_result("")  # 确保增量内容已完整输出
                                        else:
                                            yield event.plain_result(event_content["content"])  # 兜底输出完整内容

                                elif event_type == "conversation.chat.completed":
                                    logger.info(f"对话完成，Token 使用量: {event_content.get('usage', {}).get('token_count', 0)}")
                                    break

                                elif event_type == "error":
                                    logger.error(f"流式响应错误: {event_data.get('code')} - {event_data.get('msg')}")
                                    yield event.plain_result(f"智能体返回错误: {event_data.get('msg', '未知错误')}")
                                    return

                            except json.JSONDecodeError as e:
                                logger.error(f"解析流式事件失败: {line} - {str(e)}")
                                continue

                    if not full_content:
                        logger.error("流式响应未返回有效消息内容")
                        yield event.plain_result("未能获取智能体回复，可能无有效响应内容")

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
