from typing import Any, Generator
from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk


class CustomOpenaiClient:
    def __init__(self, default_model: str, base_url: str, api_key: str = 'EMPTY_KEY', ) -> None:
        '''
        无api key 填空字符串
        '''
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.default_model = default_model
        self.create_chat_completions = self.client.chat.completions.create

    # 调用OpenAI API
    def chat_completions(self, messages: list[dict[str, str]], model_or_lora_name: str = None,
                         generate_config: dict[str, Any] = {}) \
            -> ChatCompletion | Generator[None, ChatCompletionChunk, None]:
        '''
        args example:
            messages:
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Tell me something about large language models."}
                ]
        '''
        model = model_or_lora_name if model_or_lora_name is not None else self.default_model
        # copy for not modify source dict
        generate_config = generate_config.copy()

        # 调用OpenAI的chat Completion API进行意图识别
        chat_response = self.create_chat_completions(
            model=model,
            messages=messages,
            stream=generate_config.pop('stream', False),  # 返回聊天完成对象， true，返回一个生成器
            extra_body=generate_config  # 生成的参数放在 extra_body 发送
        )
        return chat_response

    # 构建消息列表并调用 chat_completions
    def chat(self, prompt: str, sys_prompt: str = '你是一个擅长回答各种问题的助手。', model_or_lora_name: str = None,
             generate_config: dict[str, Any] = {}) \
            -> str | Generator[None, ChatCompletionChunk, None]:
        '''
        '''
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": prompt}
        ]
        stream = generate_config.get('stream', False)  # 返回第一条消息，true，返回生成器

        chat_response = self.chat_completions(messages, model_or_lora_name=model_or_lora_name,
                                              generate_config=generate_config)
        # 流式的话，返回generator
        if stream:
            return chat_response
        return chat_response.choices[0].message.content # 获取OpenAI生成的回复文本

    # 辅助方法，从字典解包并调用chat方法
    def _batch_chat(self, args: dict[str, Any]) -> str:
        '''
        将线程池的参数解包，调用chat获取模型输出
        '''
        return self.chat(**args)


if __name__ == '__main__':
    # openai client:
    stream = False
    generate_config = {'temperature': 1e-7, 'max_tokens': 512, 'stream': stream}
    client = CustomOpenaiClient(base_url='http://192.168.204.202:8082/v1', api_key='EMPTY_KEY', default_model='Qwen1.5')
    sys_prompt = '''\
        你是一个负责人判断的助手，用户将输入一个问题，请根据该问题判断哪个负责人对问题负责，请直接输出对应的负责人
        负责人有以下两种：
        前台助理：负责开放领域的沟通。
        人力考勤专员：了解公司-部门-团队的组织架构和其员工考勤数据:旷工（缺勤）、迟到、早退、()工时(工作时长)、上下班、打卡\刷卡、请假\休假、加班\调休等。
        请直接输出对应的负责人。
    '''
    prompt_prefix = '''\
        以下为问题：
        {}
    '''
    # question = '昨天谁来得最早'
    question = '知识库问答'
    prompt = prompt_prefix.format(question)
    res = client.chat(prompt=prompt, sys_prompt=sys_prompt, generate_config=generate_config)
    if stream:
        for ret in res:
            content = ret.choices[0].delta.content
            if content:
                print(content, end='')
    else:
        print(res)
