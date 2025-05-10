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
        self.config = config or {}
        self.validate_config()

    def validate_config(self):
        """Validate configuration parameters."""
        required_fields = ["agent_id", "token", "api_url"]
        for field in required_fields:
            if not self.config.get(field):
                logger.error(f"Configuration error: '{field}' is missing or empty.")
                raise ValueError(f"Configuration error: '{field}' is missing or empty.")

    @filter.command("yuanqi")
    async def handle_yuanqi_command(self, event: AstrMessageEvent):
        """Handle /yuanqi command to interact with Tencent YuanQi API."""
        try:
            # Extract user input (remove command prefix)
            user_input = event.message_str.strip()
            if not user_input:
                yield event.plain_result("請輸入要發送給元器智能體的消息，例如：/yuanqi 你好")
                return

            # Prepare API request
            headers = {
                "Authorization": f"Bearer {self.config['token']}",
                "Content-Type": "application/json"
            }
            payload = {
                "agent_id": self.config['agent_id'],
                "query": user_input
            }

            # Send POST request to YuanQi API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config['api_url'],
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

            # Handle response
            if response.status_code == 200:
                result = response.json()
                reply = result.get("response", "元器智能體未返回有效回復")
                yield event.plain_result(reply)
            else:
                logger.error(f"YuanQi API request failed: {response.status_code} - {response.text}")
                yield event.plain_result(f"調用元器智能體失敗：HTTP {response.status_code}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error while calling YuanQi API: {e}")
            yield event.plain_result("調用元器智能體時發生網絡錯誤，請稍後重試")
        except Exception as e:
            logger.error(f"Unexpected error in YuanQiPlugin: {e}")
            yield event.plain_result("插件內部錯誤，請聯繫管理員")

    async def on_load(self):
        """Called when the plugin is loaded."""
        logger.info(f"YuanQiPlugin loaded.")

    async def on_unload(self):
        """Called when the plugin is unloaded."""
        logger.info(f"YuanQiPlugin unloaded.")
