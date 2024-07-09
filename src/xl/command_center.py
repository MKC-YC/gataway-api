from pydantic import BaseModel
import uvicorn
from fastapi import FastAPI
from random import sample
from typing import List, Dict

# 创建FastAPI实例
app = FastAPI()


# 将CommandInfo转换为BaseModel子类
class CommandInfo(BaseModel):
    subtitle: str | None = None
    icon: str = "-------------------"
    sub_content: str | None = None


# 将AiCommandCenterVO转换为BaseModel子类
class AiCommandCenterVO(BaseModel):
    title: str | None = None
    command_list: list[CommandInfo] = []


# 响应模型
class ResponseModel(BaseModel):
    code: int
    data: list[AiCommandCenterVO]
    message: str

    @classmethod
    def success(cls, data: list[AiCommandCenterVO]):
        return cls(code=200, data=data, message="Success")


@app.get('/commandCenter')
def command_center() -> ResponseModel:
    data = []

    # 创建考勤和知识问答的命令中心数据
    clocking_in_commands = ai_command_center_clocking_in()
    knowledge_questions_commands = ai_command_center_knowledge_questions()

    # 创建包含全部的命令中心数据
    all_commands = AiCommandCenterVO(title="全部",
                                     command_list=clocking_in_commands.command_list + knowledge_questions_commands.command_list)

    # 添加所有数据到data列表
    data.append(all_commands)
    data.append(clocking_in_commands)
    data.append(knowledge_questions_commands)

    # 从ai_command_center_clocking_in和ai_command_center_knowledge_questions获取数据
    clocking_in_commands = ai_command_center_clocking_in().command_list
    knowledge_questions_commands = ai_command_center_knowledge_questions().command_list

    # 将CommandInfo对象转换为字典列表
    clocking_in_commands_dicts = [ci.dict() for ci in clocking_in_commands]
    knowledge_questions_dicts = [kq.dict() for kq in knowledge_questions_commands]

    # 现在你可以调用random_recommend_commands函数
    recommended_commands = random_recommend_commands(
        clocking_in_commands_dicts + knowledge_questions_dicts, "推荐"
    )
    data.append(AiCommandCenterVO(title="推荐",
                                  command_list=[CommandInfo(sub_content=rc['content']) for rc in recommended_commands]))

    return ResponseModel.success(data)


# 随机推荐命令函数
def random_recommend_commands(command_infos: List[Dict], title: str) -> List[Dict]:
    if len(command_infos) < 2:
        return [{"title": title, "content": command_infos[0]['sub_content']}]

    selected_indices = sample(range(len(command_infos)), 2)
    return [{"title": title, "content": command_infos[i]['sub_content']} for i in selected_indices]


def ai_command_center_clocking_in() -> AiCommandCenterVO:
    command_infos = clocking_in_command_infos()
    return AiCommandCenterVO(title="考勤", command_list=command_infos)


def ai_command_center_knowledge_questions() -> AiCommandCenterVO:
    command_infos = knowledge_questions_in_command_infos()
    return AiCommandCenterVO(title="知识问答", command_list=command_infos)


def clocking_in_command_infos() -> list[CommandInfo]:
    command_infos = [
        CommandInfo(subtitle="个人工时查询", sub_content="查询员工每天工作时长，以列表形式展示，时间为这个月，姓名为："),
        CommandInfo(subtitle="部门平均工时统计", sub_content="统计一下快鹭产品研发中心上周每个人平均工时"),
        CommandInfo(subtitle="最长工时查询", sub_content="上个月快鹭开发人员中谁的工时最长"),
        CommandInfo(subtitle="请假统计", sub_content="上周几个人请假了，分别请了多少天"),
        CommandInfo(subtitle="部门工时对比", sub_content="上周几个人请假了，对比一下采购和销售部门的工时")
    ]
    return command_infos


def knowledge_questions_in_command_infos() -> list[CommandInfo]:
    list_process = [
        CommandInfo(subtitle="收款签章表格", sub_content="加油站收银员在手工收款时需要在哪个表格上签章"),
        CommandInfo(subtitle="发票开具", sub_content="如果加油站顾客需要开具发票，收银员应该怎么做"),
        CommandInfo(subtitle="源代码的组成部分", sub_content="源代码包括哪些内容"),
        CommandInfo(subtitle="源代码完整性保障方法", sub_content="如何保障源代码的完整性"),
        CommandInfo(subtitle="源代码备份策略", sub_content="源代码备份有哪些方式"),
        CommandInfo(subtitle="职责范围", sub_content="测试部的部门经理都负责哪些工作"),
        CommandInfo(subtitle="工作内容", sub_content="测试部的功能测试组主要负责什么"),
        CommandInfo(subtitle="测试流程", sub_content="测试部的测试流程包括哪些阶段"),
        CommandInfo(subtitle="责任归属", sub_content="行政办公管理制度的责任部门是哪个"),
        CommandInfo(subtitle="工作时间", sub_content="工作时间规定中标准工时制的上班时间是几点到几点")
    ]
    return list_process


if __name__ == '__main__':
    uvicorn.run(app=app, host='0.0.0.0', port=8012)
