import json
import os
from typing import Optional, Any
from astrbot.api.star import Star, Context, register
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger, AstrBotConfig
import httpx

@register("YuanQiPlugin", "Homanho", "一個用於與騰訊元器 API 交互的插件", "v1.0")
class YuanQiPlugin(Star):
    def __init__(self, context: Context, config: Optional[AstrBotConfig] = None, db: Any = None, *args, **kwargs):
        super().__init__(context)
        self.config = config or getattr(context, 'config', {}) if hasattr(context, 'config') else {}
        self.db = db or getattr(context, 'db', None) if hasattr(context, 'db') else None
        logger.info(f"YuanQiPlugin initialized with config: {self.config}, db: {self.db}, args: {args}, kwargs: {kwargs}")

    def validate_config(self):
        """驗證配置參數"""
        required_fields = ["agent_id", "token", "api_url"]
        for field in required_fields:
            if not self.config.get(field):
                return False, f"配置錯誤：'{field}' 缺失或為空。"
        return True, None

    @filter.command("yuanqi")
    async def handle_yuanqi_command(self, event: AstrMessageEvent, context: Context, *args, **kwargs):
        """處理 /yuanqi 命令，與騰訊元器 API 交互"""
        try:
            # 記錄額外參數以便調試
            logger.info(f"接收到的參數: args={args}, kwargs={kwargs}")

            # 驗證配置
            is_valid, error_msg = self.validate_config()
            if not is_valid:
                yield event.plain_result(error_msg + " 請在管理面板中配置插件。")
                return

            # 提取用戶輸入（去除命令前綴）
            full_message = event.message_str.strip()
            parts = full_message.split(" ", 1)
            user_input = parts[1].strip() if len(parts) > 1 else ""

            if not user_input:
                yield event.plain_result("請輸入要發送給元器智能體的消息，例如：/yuanqi 你好")
                return

            # 準備 API 請求
            headers = {
                "Authorization": f"Bearer {self.config['token']}",
                "Content-Type": "application/json"
            }
            payload = {
                "agent_id": self.config['agent_id'],
                "message": user_input  # 使用 message 字段
            }
            logger.info(f"發送元器 API 請求: {json.dumps(payload, ensure_ascii=False)}")

            # 發送 POST 請求到元器 API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config['api_url'],
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )

            # 記錄完整響應以便調試
            logger.info(f"元器 API 響應: {response.status_code} - {response.text}")

            # 處理響應
            if response.status_code == 200:
                result = response.json()
                reply = result.get("response", "元器智能體未返回有效回復")
                yield event.plain_result(reply)
            else:
                logger.error(f"元器 API 請求失敗: {response.status_code} - {response.text}")
                yield event.plain_result(f"調用元器智能體失敗：HTTP {response.status_code} - {response.json().get('error', {}).get('message', '未知錯誤')}")
        except httpx.HTTPError as e:
            logger.error(f"調用元器 API 時發生網絡錯誤: {e}")
            yield event.plain_result("調用元器智能體時發生網絡錯誤，請稍後重試")
        except Exception as e:
            logger.error(f"YuanQiPlugin 內部錯誤: {e}")
            yield event.plain_result("插件內部錯誤，請聯繫管理員")

    async def on_load(self):
        """插件載入時調用"""
        logger.info(f"YuanQiPlugin 已載入")

    async def on_unload(self):
        """插件卸載時調用"""
        logger.info(f"YuanQiPlugin 已卸載")
