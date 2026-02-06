from src.storage import get_db
import logging

# 配置 logging 以便看到 info 输出
logging.basicConfig(level=logging.INFO)

db = get_db()
print("开始清空数据库...")
if db.clear_database():
    print("数据库清空成功！")
else:
    print("数据库清空失败，请检查日志。")
