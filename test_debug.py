import os
# 双重保险开关
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import logging
logging.basicConfig(level=logging.INFO)

from agent_core import LuminaAgentCore
import agent_tools

def run_test():
    print("===================================")
    print("🚀 开始本地脱机测试 (绕过 PyQt)")
    print("===================================")
    
    # 模拟前端传来的 Session
    test_session = "debug_session_001"
    agent_tools.CURRENT_SESSION_ID = test_session
    
    print("\n[1/3] 正在初始化 Agent 控制中心...")
    agent = LuminaAgentCore()
    
    print("\n[2/3] 准备向 Agent 提问...")
    test_question = "介绍一下这个文件的内容" # 用你之前卡住的问题
    
    print(f"\n[3/3] 正在请求大模型，问题：{test_question}")
    print("⏳ 等待回答中...\n")
    
    try:
        response = agent.chat(test_question, test_session)
        print("✅ 测试成功！收到回答：")
        print("-----------------------------------")
        print(response)
        print("-----------------------------------")
    except Exception as e:
        print(f"❌ 测试失败！爆出异常: {e}")

if __name__ == "__main__":
    run_test()