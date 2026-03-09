#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
班级魔方自动签到脚本
基于 API 文档实现自动签到功能
"""

import re
import json
import requests
from typing import Optional, List, Dict

# =========================================================
# >>> 用户配置区域 (请根据实际情况修改以下参数) <<<
# =========================================================

# 【必需】完整 Cookie 字符串
# 获取方法：
#   1. 在微信中打开班级魔方小程序并登录
#   2. 使用抓包工具（如 Reqable、Charles）抓取请求
#   3. 复制请求头中完整的 Cookie 值
# 示例值格式：
#   wxid=xxx; remember_student_xxx=yyy; s=zzz
# 注意：直接粘贴完整 Cookie 即可，脚本会自动提取 remember_student 的值
RAW_COOKIE = """wxid=ollOC0dHSmdEVIEt4EoCaZ3a43is$1766584302$874051aab30d42cf08eaf65fb2c0e01d; remember_student_59ba36addc2b2f9401580f014c7f58ea4e30989d=3520620%7CtHOgosIQd4m5J4AI3BMmyTRdfr92HODsqd3L23pwr1I8STLIClPQVEhw1g2w%7C; s=6Jh5atntonNcPONYpTsg9aKhGgCjlAJyMveUEQqU"""

# 【必需】课程 ID
# 获取方法：
#   1. 在班级魔方中进入需要签到的课程
#   2. 查看页面 URL，格式为：/student/course/{课程ID}/punchs
#   3. 其中的数字就是课程 ID
# 示例：URL 为 /student/course/121411/punchs，则课程 ID 为 121411
COURSE_ID = 121411

# 【必需】GPS 签到位置
# 获取方法：
#   1. 打开腾讯地图拾取坐标工具：https://lbs.qq.com/getPoint/
#   2. 在地图上找到签到地点的位置
#   3. 点击该位置，复制显示的坐标
# 注意：建议使用签到地点的实际坐标，否则可能因距离过远导致签到失败
GPS_LAT = 34.11486   # 纬度（小数格式，保留5-6位小数）
GPS_LNG = 108.94291  # 经度（小数格式，保留5-6位小数）
GPS_ACC = 35.0       # GPS 精度，单位：米（一般填 10-50 即可）

# ============== 核心代码 ==============


def parse_remember_cookie(raw_cookie: str) -> tuple[str, str]:
    """
    从完整的 Cookie 字符串中提取 remember_student 的名称和值

    Args:
        raw_cookie: 完整的 Cookie 字符串

    Returns:
        (cookie_name, cookie_value) 元组

    Raises:
        ValueError: 如果找不到 remember_student cookie
    """
    # 使用正则匹配 remember_student_xxx=value
    pattern = r'(remember_student_[a-f0-9]+)=([^;]+)'
    match = re.search(pattern, raw_cookie)

    if not match:
        raise ValueError("Cookie 中未找到 remember_student，请检查 Cookie 是否正确")

    return match.group(1), match.group(2)


BASE_URL = "https://bj.k8n.cn"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


class BJMFClient:
    """班级魔方客户端"""

    def __init__(self, cookie_name: str, cookie_value: str, course_id: int):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.cookies.set(cookie_name, cookie_value)
        self.course_id = course_id
        self.user_id: Optional[int] = None

    def get_ongoing_punchs(self) -> List[Dict]:
        """获取正在进行的签到列表"""
        url = f"{BASE_URL}/student/course/{self.course_id}/punchs"
        params = {"op": "ing"}

        resp = self.session.get(url, params=params)
        resp.raise_for_status()

        # 解析用户信息
        self._parse_user_info(resp.text)

        # 解析签到列表
        return self._parse_punch_list(resp.text)

    def _parse_user_info(self, html: str) -> None:
        """从 HTML 中解析用户信息"""
        # 匹配 gconfig 变量
        pattern = r"var\s+gconfig\s*=\s*\{[^}]*uid\s*:\s*(\d+)"
        match = re.search(pattern, html)
        if match:
            self.user_id = int(match.group(1))
            print(f"[INFO] 用户 ID: {self.user_id}")

    def _parse_punch_list(self, html: str) -> List[Dict]:
        """从 HTML 中解析签到列表"""
        punchs = []

        # 匹配签到卡片（根据实际 HTML 结构调整）
        # 这里需要根据实际返回的 HTML 结构来解析
        # 示例：查找签到链接 /student/punchs/course/{course_id}/{punch_id}
        pattern = rf"/student/punchs/course/{self.course_id}/(\d+)"
        matches = re.findall(pattern, html)

        for punch_id in matches:
            punchs.append({"punch_id": int(punch_id)})

        return punchs

    def do_punch(self, punch_id: int, lat: float, lng: float, acc: float = 35.0) -> bool:
        """执行签到"""
        if not self.user_id:
            print("[ERROR] 未获取到用户 ID")
            return False

        url = f"{BASE_URL}/student/punchs/course/{self.course_id}/{punch_id}"
        params = {"sid": self.user_id}
        data = {
            "lat": lat,
            "lng": lng,
            "acc": acc,
            "res": ""
        }

        # 添加 Referer
        headers = {"Referer": url}

        resp = self.session.post(url, params=params, data=data, headers=headers)
        resp.raise_for_status()

        # 检查签到结果
        if "签到成功" in resp.text or "成功" in resp.text:
            print(f"[SUCCESS] 签到成功！签到 ID: {punch_id}")
            return True
        elif "已签到" in resp.text or "已经签到" in resp.text:
            print(f"[INFO] 已经签到过了，签到 ID: {punch_id}")
            return True
        else:
            print(f"[WARN] 签到结果未知，签到 ID: {punch_id}")
            # 保存响应用于调试
            with open("punch_response.html", "w", encoding="utf-8") as f:
                f.write(resp.text)
            return False


def main():
    """主函数"""
    print("=" * 50)
    print("班级魔方自动签到")
    print("=" * 50)

    # 解析 Cookie
    try:
        cookie_name, cookie_value = parse_remember_cookie(RAW_COOKIE)
        print(f"[INFO] 已解析 Cookie: {cookie_name}")
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    # 初始化客户端
    client = BJMFClient(cookie_name, cookie_value, COURSE_ID)

    # 获取正在进行的签到
    print("\n[STEP 1] 获取签到列表...")
    try:
        punchs = client.get_ongoing_punchs()
    except requests.RequestException as e:
        print(f"[ERROR] 网络请求失败: {e}")
        return

    if not punchs:
        print("[INFO] 当前没有正在进行的签到")
        return

    print(f"[INFO] 发现 {len(punchs)} 个正在进行的签到")

    # 执行签到
    print(f"\n[STEP 2] 开始签到...")
    print(f"[INFO] GPS 位置: ({GPS_LAT}, {GPS_LNG}), 精度: {GPS_ACC}m")

    for punch in punchs:
        punch_id = punch["punch_id"]
        print(f"\n[ACTION] 正在签到 ID: {punch_id}")

        try:
            success = client.do_punch(punch_id, GPS_LAT, GPS_LNG, GPS_ACC)
            if success:
                print(f"[DONE] 签到 ID {punch_id} 完成")
        except requests.RequestException as e:
            print(f"[ERROR] 签到失败: {e}")

    print("\n" + "=" * 50)
    print("签到任务完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
