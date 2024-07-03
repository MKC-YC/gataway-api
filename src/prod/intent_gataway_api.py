from urllib.parse import urlencode
from fastapi import FastAPI, HTTPException, Body
from httpx import stream
from pydantic import BaseModel
from client import CustomOpenaiClient
import requests, json
import aiohttp
import asyncio
import re
from sse_starlette.sse import EventSourceResponse

# 创建FastApi实例
app = FastAPI()
# 常量定义如下：
ATTENDANCE_BASE_URL = "http://192.168.204.198:60001/execute_sql_stream?"  # 考勤
KNOWLEDGE_BASE_URL = "http://192.168.102.95:7861/chat/knowledge_base_chat"  # 知识库
ILLEGAL_AUTH_REFUSE = "很抱歉，根据您提供的查询条件，你不具有查询考勤的权限。建议您申请权限后再尝试查询。"
# 权限校验，根据用户角色和查询类型校验用户是否有权限进行访问
auth_role_allown_map = {"attendance": ["Boss", "Assistant", "HR"],
                        "chat": ["Boss", "Assistant", "HR", "Manager", "Employee"]}


# 创建请求体模型
class RequestBody(BaseModel):
    question: str
    user_id: str
    user_role: str
    topic_id: str


@app.post("/getaway_api")
async def user_intent_recognize(request_body: RequestBody = Body(...)):
    question = request_body.question
    user_id = request_body.user_id
    user_role = request_body.user_role
    topic_id = request_body.topic_id
    stream = False
    generate_config = {'temperature': 1e-7, 'max_tokens': 512, 'stream': stream}
    client = CustomOpenaiClient(base_url='http://192.168.204.202:8082/v1', api_key='EMPTY_KEY', default_model='Qwen1.5')
    if not check_auth_role("attendance", user_role):
        raise HTTPException(status_code=403, detail=ILLEGAL_AUTH_REFUSE)
    sys_prompt = '''\
        你是一个负责人判断的助手，用户将输入一个问题，请根据该问题判断对应的负责人，请直接输出对应的负责人。
        负责人有以下两种：
        1. 前台助理：负责开放领域的沟通。 
        2. 知识库助理：负责文档、制度、考勤制度、考勤规则、考勤规范、政策、流程、技术指南、历史记录等信息的查询。
        3. 考勤数据查询助理：负责查询员工的考勤数据，如旷工（缺勤）、迟到、早退、工时(工作时长)、上下班、打卡\刷卡、请假\休假、加班\调休等。
        用户将会举一些例子，请根据例子要求进行回答，不要添加负责人外的内容。
        '''
    prompt_prefix = '''\
        问：昨天有多少人迟到
        答：考勤数据查询助理
        问：今天天气怎么样
        答：前台助理
        问：考勤制度
        答：知识库助理
        问：一天要打几次卡
        答：知识库助理
        问：昨天有谁请假了
        答：考勤数据查询助理
        问：如何请假
        答：知识库助理
        问：{}
        答：'''
    prompt = prompt_prefix.format(question)
    print("question: " + question)
    # 根据问题和回答模版去校验 res 属于哪种类型（考勤/知识库/开放领域）
    res = client.chat(prompt=prompt, sys_prompt=sys_prompt, generate_config=generate_config)
    print("res: " + str(res))
    if '考勤数据查询助理' in res:
        return EventSourceResponse(call_third_party_attendance_api(question, user_id, user_role, topic_id),
                                   media_type="text/event-stream")
    if '知识库助理' in res:
        return EventSourceResponse(call_third_party_knowledge_api(question, user_id, user_role, topic_id),
                                   media_type="text/event-stream")
    else:
        def chat_stream_generator():
            for chunk in client.chat(prompt=question, generate_config=generate_config):
                yield f"{{\"data\": {chunk},\"type\": 3}}"
            yield f"{{\"data\": \"[DONE]\",\"type\": 3}}"

        return EventSourceResponse(chat_stream_generator(), media_type="text/event-stream")


def check_auth_role(agency_type, user_role):
    allown_role_list = auth_role_allown_map.get(agency_type)
    return allown_role_list is None or user_role in allown_role_list


async def call_third_party_attendance_api(question, user_id, user_role, topic_id):
    if not check_auth_role("attendance", user_role):
        raise HTTPException(status_code=403, detail=ILLEGAL_AUTH_REFUSE)
    params = {
        "question": question,
        "userId": user_id,
        "userRole": user_role,
        "topicId": topic_id,
    }
    try:
        query_params = urlencode(params)
        final_url = f"{ATTENDANCE_BASE_URL}{query_params}"
        async with aiohttp.ClientSession() as session:
            async with session.get(final_url) as response:
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    # 检查SSE事件结束或关闭事件
                    if line == '[DONE]' or line.startswith('event: close'):
                        yield "event: [DONE]\ndata: {\"type\": 1, \"data\": \"[DONE]\"}"
                        break
                    # 确保yield的数据格式正确
                    try:
                        data = json.loads(line)
                        data_with_type = {"data": data, "type": 1}
                        yield f"data: {json.dumps(data_with_type)}"
                    except json.JSONDecodeError:
                        yield f"data: {{\"error\": \"Invalid JSON format in response\"}}"
                print("考勤API调用成功，响应数据:", line)
    except aiohttp.ClientError as e:
        yield f"data: {{\"error\": \"{str(e)}\"}}"


# 知识库 2024年7月1日14:56:29
async def call_third_party_knowledge_api(question, user_id, user_role, topic_id):
    params = {
        "query": question,
        "userId": user_id,
        "topicId": topic_id,
        "userRole": user_role,
    }
    headers = {'Content-Type': 'application/json'}
    async with aiohttp.ClientSession() as session:
        async with session.post(KNOWLEDGE_BASE_URL, json=params, headers=headers) as response:
            print(f"response: {response}")
            try:
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if "data:[DONE]" in line:
                        yield "event: [DONE]: {\"data\": \"[DONE]\", \"type\": 2}"
                        break
                    if line:
                        try:
                            # 假设每行都是有效的JSON数据前缀以"data: "
                            data_str = re.sub(r'^data: ', '', line)
                            data = json.loads(data_str)
                            answer = ""
                            if stream:
                                # 直接yield包含"docs"的完整数据字典
                                if "docs" in data:
                                    yield json.dumps(data)
                                # 继续处理"data:[summary]"等其他情况
                                elif "data:[summary]" in data:
                                    summary_content = data.get("data:[summary]")
                                    # 构造一个新的字典，包含"type"字段
                                    yield json.dumps({"data": summary_content, "type": 2})
                            else:
                                async for token in data:
                                    answer += token
                                yield json.dumps({"data:[summary]": answer,
                                                  "docs": data})
                        except json.JSONDecodeError:
                            print(f"Invalid JSON: {line}")
            except asyncio.CancelledError:
                print(f"Error")


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app=app, host='0.0.0.0', port=8088)
