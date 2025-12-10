import sys
import os

# 加载.env文件中的环境变量 - 必须在任何其他导入之前完成
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("环境变量加载成功")
    # 验证关键环境变量
    if os.environ.get("DEEPSEEK_API_KEY"):
        print(f"DeepSeek API密钥已配置 (长度: {len(os.environ.get('DEEPSEEK_API_KEY', ''))})")
    else:
        print("警告: DeepSeek API密钥未配置")
except ImportError:
    print("警告: python-dotenv 未安装，.env 文件将不会被加载。请运行 'pip install python-dotenv'")
except Exception as e:
    print(f"加载环境变量时出错: {e}")

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.my_app.app import app

if __name__ == '__main__':
    # 避免与app.py中的app.run冲突，确保从main.py启动应用
    # 为了避免重复定义，我们从app.py导入后在此处启动
    app.run(debug=True, host='0.0.0.0', port=5000)