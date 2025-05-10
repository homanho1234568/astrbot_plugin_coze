import json
import os
from typing import Optional
from astrbot.core.plugin import BaseStarPlugin, PluginMetadata
from astrbot.core.message.event import AstrMessageEvent
from astrbot.core.logger import logger
import httpx
from astrbot.core.filter import filter

class YuanQiPlugin(BaseStarPlugin):
    def __init__(self):
        super().__init__()
        self.metadata = PluginMetadata(
            plugin_name="YuanQiPlugin",
            description="A plugin to interact with Tencent YuanQi API",
            version="1.0.0",
            author="Grok"
        )
        self.config = self.load_config()
        self.validate_config()

    def load_config(self) -> dict:
        """Load configuration from config.json in data directory."""
        config_path = os.path.join("data", "yuanqi_plugin", "config.json")
        default_config = {
            "agent_id": "",
            "token": "",
            "api_url": "https://api.hunyuan.tencent.com/v1/agents"
        }

        try:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            if not os.path.exists(config_path):
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, ensure_ascii=False, indent=4)
                logger.info("Created default config file for YuanQiPlugin.")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return default_config

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
        logger.info(f"{self.metadata.plugin_name} v{self.metadata.version} loaded.")

    async def on_unload(self):
        """Called when the plugin is unloaded."""
        logger.info(f"{self.metadata.plugin_name} unloaded.")
