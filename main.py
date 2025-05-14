import asyncio
import logging
import json
import httpx

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def fetch_streaming_data(url, headers, payload):
    """
    从API获取流式数据并存入缓冲区。
    """
    buffer = []  # 缓冲区，用于存储流式数据
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    error_message = await response.aread()
                    logger.error(f"API请求失败: {response.status_code} - {error_message.decode()}")
                    return None

                # 逐行读取流式数据
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        try:
                            event_data = json.loads(line[5:].strip())
                            if isinstance(event_data, dict):
                                buffer.append(event_data)
                            else:
                                logger.warning(f"数据格式错误，跳过: {event_data}")
                        except json.JSONDecodeError as e:
                            logger.error(f"解析错误: {line} - {str(e)}")
                            continue

                # 等待流关闭
                await response.aclose()

    except httpx.HTTPError as e:
        logger.error(f"网络错误: {e}")
        return None
    except Exception as e:
        logger.error(f"未知错误: {e}")
        return None

    return buffer

def process_complete_data(buffer):
    """
    处理缓冲区中的完整数据，生成最终输出。
    """
    full_content = ""
    for event in buffer:
        event_type = event.get("event")
        event_content = event.get("data", {})
        # 累加消息增量内容
        if event_type == "conversation.message.delta":
            content = event_content.get("content", "")
            if content:
                full_content += content
        # 检查是否为最终完整消息
        elif event_type == "conversation.message.completed":
            if event_content.get("role") == "assistant" and event_content.get("content"):
                return event_content["content"]
    # 如果没有完整消息，返回累加的内容
    return full_content if full_content else "未能获取完整回复"

async def main():
    # 示例请求参数
    url = "https://api.coze.cn/v3/chat"  # 替换为实际API地址
    headers = {
        "Authorization": "Bearer your_access_token",  # 替换为您的token
        "Content-Type": "application/json"
    }
    payload = {
        "bot_id": "your_bot_id",  # 替换为您的bot_id
        "user_id": "your_user_id",  # 替换为您的user_id
        "stream": True,
        "auto_save_history": True,
        "additional_messages": [
            {
                "type": "question",
                "role": "user",
                "content_type": "text",
                "content": "你好",
                "meta_data": {"key_1": "User"}
            }
        ]
    }

    # 获取流式数据
    buffer = await fetch_streaming_data(url, headers, payload)
    if buffer:
        # 处理并输出完整结果
        final_output = process_complete_data(buffer)
        print(final_output)  # 一次性输出给AstrBot
    else:
        print("未能获取完整回复")

# 运行异步主函数
#asyncio.run(main())
