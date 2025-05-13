import json
import os
from typing import Optional, Any
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent, EventMessageType
from astrbot.api import logger, AstrBotConfig
import httpx

@register("Astrbot-Coze-Plugin", "Homanho", "一个用于与扣子 AI 智能体 API 交互的插件", "v1.0")
class AstrbotCozePlugin(Star):
    def __init__(self, context: Context, config: Optional[dict] = None, db: Any = None):
        logger.info(f"Astrbot-Coze-Plugin init received context: {context}, config: {config}, db: {db}")
        super().__init__(context)
        self.config = config or getattr(context, 'config', {}) if hasattr(context, 'config') else {}
        self.db = db or getattr(context, 'db', None) if hasattr(context, 'db') else None
        logger.info(f"Astrbot-Coze-Plugin initialized with config: {self.config}, db: {self.db}")

    def validate_config(self):
        """验证配置参数"""
        required_fields = ["bot_id", "access_token", "api_url"]
        for field in required_fields:
            if not self.config.get(field):
                return False, f"配置错误：'{field}' 缺失或为空。"
        return True, None

    @filter.command("coze")
    async def handle_coze_command(self, event: AstrMessageEvent, context: Context):
        """处理 /coze 命令，与扣子 API 交互"""
        try:
            is_valid, error_msg = self.validate_config()
            if not is_valid:
                yield event.plain_result(error_msg + " 请在管理面板中配置插件。")
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
                "user_id": event.session_id or "123",  # 使用 session_id 或默认值
                "stream": False,
                "auto_save_history": True,
                "additional_messages": [
                    {
                        "role": "user",
                        "content": user_input,
                        "content_type": "text"
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
                reply = result.get('data', {}).get('messages', [{}])[-1].get('content', "智能体未返回有效回复")
                yield event.plain_result(reply)
            else:
                logger.error(f"扣子 API 请求失败: {response.status_code} - {response.text}")
                yield event.plain_result(f"调用智能体失败：HTTP {response.status_code} - {response.json().get('error', {}).get('message', '未知错误')}")
        except httpx.HTTPError as e:
            logger.error(f"调用扣子 API 时发生网络错误: {e}")
            yield event.plain_result("调用智能体时发生网络错误，请稍后重试")
        except Exception as e:
            logger.error(f"Astrbot-Coze-Plugin 内部错误: {e}")
            yield event.plain_result("插件内部错误，请联系管理员")

    async def on_load(self):
        logger.info(f"Astrbot-Coze-Plugin 已加载")

    async def on_unload(self):
        logger.info(f"Astrbot-Coze-Plugin 已卸载")
