import json
import os
from typing import Optional
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig
import httpx

@register("YuanQiPlugin", "Homanho", "一個用於與騰訊元器 API 交互的插件", "v1.0")
class YuanQiPlugin(Star):
    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None):
        super().__init__(context)
        self.config = config or context.config if hasattr(context, 'config') else {}
        logger.info(f"YuanQiPlugin initialized with config: {self.config}")

    def validate_config(self):
        """验证配置参数"""
        required_fields = ["agent_id", "token", "api_url"]
        for field in required_fields:
            if not self.config.get(field):
                return False, f"配置错误：'{field}' 缺失或为空。"
        return True, None

    @filter.command("yuanqi")
    async def handle_yuanqi_command(self, event: AstrMessageEvent, context: Context, *args, **kwargs):
        """处理 /yuanqi 命令，与腾讯元器 API 交互"""
        try:
            # 记录额外参数以便调试
            logger.info(f"接收到的参数: args={args}, kwargs={kwargs}")

            # 验证配置
            is_valid, error_msg = self.validate_config()
            if not is_valid:
                yield event.plain_result(error_msg + " 请在管理面板中配置插件。")
                return

            # 提取用户输入（去除命令前缀）
            full_message = event.message_str.strip()
            parts = full_message.split(" ", 1)
            user_input = parts[1].strip() if len(parts) > 1 else ""

            if not user_input:
                yield event.plain_result("请输入要发送给元器智能体的消息，例如：/yuanqi 你好")
                return

            # 准备 API 请求
            headers = {
                "Authorization": f"Bearer {self.config['token']}",
                "Content-Type": "application/json"
            }
            payload = {
                "agent_id": self.config['agent_id'],
                "message": user_input  # 使用 message 字段
            }
            logger.info(f"发送元器 API 请求: {json.dumps(payload, ensure_ascii=False)}")

            # 发送 POST 请求到元器 API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config['api_url'],
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

            # 记录完整响应以便调试
            logger.info(f"元器 API 响应: {response.status_code} - {response.text}")

            # 处理响应
            if response.status_code == 200:
                result = response.json()
                reply = result.get("response", "元器智能体未返回有效回复")
                yield event.plain_result(reply)
            else:
                logger.error(f"元器 API 请求失败: {response.status_code} - {response.text}")
                yield event.plain_result(f"调用元器智能体失败：HTTP {response.status_code} - {response.json().get('error', {}).get('message', '未知错误')}")
        except httpx.HTTPError as e:
            logger.error(f"调用元器 API 时发生网络错误: {e}")
            yield event.plain_result("调用元器智能体时发生网络错误，请稍后重试")
        except Exception as e:
            logger.error(f"YuanQiPlugin 内部错误: {e}")
            yield event.plain_result("插件内部错误，请联系管理员")

    async def on_load(self):
        """插件加载时调用"""
        logger.info(f"YuanQiPlugin 已加载")

    async def on_unload(self):
        """插件卸载时调用"""
        logger.info(f"YuanQiPlugin 已卸载")
