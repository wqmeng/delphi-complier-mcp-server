#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 code_hosting git 功能"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"

# 重定向 stdout 为 utf-8
sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)

from src.tools.code_hosting import code_hosting, _DISPATCH

ok = 0
fail = 0

def check(name, result, expected_status="success"):
    global ok, fail
    if isinstance(result, dict) and result.get("status") == expected_status:
        print(f"  [OK] {name}")
        ok += 1
    else:
        print(f"  [FAIL] {name}: {result}")
        fail += 1

print("=" * 50)
print("测试 code_hosting Git 功能")
print(f"Git 工作目录: {os.getcwd()}")
print("=" * 50)

# 1. git_status
print("\n--- git_status ---")
r = code_hosting(action="git_status", dir=".")
print(f"  Result: status={r.get('status','?')}, message={str(r.get('message',''))[:200]}")
check("git_status", r)
if r.get("status") == "success":
    ok += 1  # 额外加分
    print(f"  分支: {r.get('branch', 'N/A')}")
    print(f"  变更: {r.get('changes', 'N/A')}")

# 2. git_add
print("\n--- git_add ---")
r = code_hosting(action="git_add", dir=".", files=["tests/test_git_status.py"])
print(f"  Result: status={r.get('status','?')}, message={str(r.get('message',''))[:200]}")
check("git_add", r)

# 3. git_commit
print("\n--- git_commit ---")
r = code_hosting(action="git_commit", dir=".", message="test: verify git status")
print(f"  Result: status={r.get('status','?')}, message={str(r.get('message',''))[:200]}")
check("git_commit", r)

# 4. 测试各种 action 都注册
print("\n--- 所有 action 注册检查 ---")
actions_required = ["git_status", "git_add", "git_commit", "git_clone", "git_push", "git_push_retry"]
for a in actions_required:
    if a in _DISPATCH:
        print(f"  [OK] {a} 已注册")
        ok += 1
    else:
        print(f"  [FAIL] {a} 未注册")
        fail += 1

print("\n" + "=" * 50)
print(f"通过: {ok} / 失败: {fail}")
print("=" * 50)
sys.exit(0 if fail == 0 else 1)
