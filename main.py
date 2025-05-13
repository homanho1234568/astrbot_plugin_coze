import json
import os
from typing import Optional, Any
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig
import httpx

@register("YuanQiPlugin", "Homanho", "一个用于与扣子 API 交互的插件", "v1.0")
class YuanQiPlugin(Star):
    def __init__(self, *args, **kwargs):
        logger.info(f"YuanQiPlugin init received args: {args}, kwargs: {kwargs}")
        context = args[0] if args else kwargs.get('context')
        if not context:
            logger.error("No context provided to YuanQiPlugin")
            raise ValueError("Context is required")
        logger.info(f"Context received: {context}")
        super().__init__(context)
        self.config = kwargs.get('config', getattr(context, 'config', {}))
        self.db = kwargs.get('db', getattr(context, 'db', None))
        logger.info(f"YuanQiPlugin initialized with config: {self.config}, db: {self.db}")

    def validate_config(self):
        """验证配置参数"""
        required_fields = ["bot_id", "access_token", "api_url"]
        for field in required_fields:
            if not self.config.get(field):
                return False, f"配置错误：'{field}' 缺失或为空。"
        return True, None

    @filter.command("yuanqi")
    async def handle_yuanqi_command(self, event: AstrMessageEvent, context: Context, *args, **kwargs):
        """处理 /yuanqi 命令，与扣子 API 交互"""
        try:
            logger.info(f"接收到的参数: args={args}, kwargs={kwargs}")
            is_valid, error_msg = self.validate_config()
            if not is_valid:
                yield event.plain_result(error_msg + " 请在管理面板中配置插件。")
                return

            full_message = event.message_str.strip()
            parts = full_message.split(" ", 1)
            user_input = parts[1].strip() if len(parts) > 1 else ""

            if not user_input:
                yield event.plain_result("请输入要发送给智能体的消息，例如：/yuanqi 你好")
                return

            headers = {
                "Authorization": f"Bearer {self.config['access_token']}",
                "Content-Type": "application/json"
            }
            payload = {
                "bot_id": self.config['bot_id'],
                "user_id": "123",  # 固定用户 ID，生产环境可动态生成
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
                # 假设返回的消息在 result['data']['messages'] 中
                reply = result.get('data', {}).get('messages', [{}])[-1].get('content', "智能体未返回有效回复")
                yield event.plain_result(reply)
            else:
                logger.error(f"扣子 API 请求失败: {response.status_code} - {response.text}")
                yield event.plain_result(f"调用智能体失败：HTTP {response.status_code} - {response.json().get('error', {}).get('message', '未知错误')}")
        except httpx.HTTPError as e:
            logger.error(f"调用扣子 API 时发生网络错误: {e}")
            yield event.plain_result("调用智能体时发生网络错误，请稍后重试")
        except Exception as e:
            logger.error(f"YuanQiPlugin 内部错误: {e}")
            yield event.plain_result("插件内部错误，请联系管理员")

    async def on_load(self):
        logger.info(f"YuanQiPlugin 已加载")

    async def on_unload(self):
        logger.info(f"YuanQiPlugin 已卸载")
