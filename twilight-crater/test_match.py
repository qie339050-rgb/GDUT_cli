import sys
sys.path.append('.')
from jw.auth import JWAuth
from jw.api import JWClient

c = JWClient(JWAuth().get_session(False))
data = c.get_student_info()

fields = ["学号", "xh", "姓名", "xm", "入学年份", "rxnf", "学院", "院系名称", "xy"]
print("----- 当前拿到的 Keys -----")
keys_list = list(data.keys())
for k in keys_list:
    print(repr(k))

print("\n----- 匹配测试 -----")
for f in fields:
    if f in data:
        print(f"匹配成功: {f} -> {data[f]}")
    else:
        print(f"匹配失败: {f}")
