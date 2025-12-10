"""
运行A2A服务的入口脚本
"""
import os
import sys
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run_a2a")


def main():
    """主函数，启动A2A服务"""
    try:
        # 导入A2A集成模块
        from src.my_app.a2a.integration import a2a_integration
        
        logger.info("准备启动A2A服务...")
        logger.info("此服务将连接所有智能体并提供A2A通信功能")
        
        # 从环境变量获取配置
        host = os.getenv("A2A_HOST", "0.0.0.0")
        port = int(os.getenv("A2A_PORT", "8000"))
        
        logger.info(f"配置信息: 主机={host}, 端口={port}")
        
        # 启动服务
        logger.info("正在初始化并启动A2A服务...")
        a2a_integration.run_server(host=host, port=port)
        
    except ImportError as e:
        logger.error(f"导入模块失败: {str(e)}")
        logger.error("请检查Python环境和依赖安装")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("服务已被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    print("===== 智能旅游助手A2A服务 =====")
    print("此服务将所有智能体连接到A2A框架，提供统一的API接口")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    
    main()