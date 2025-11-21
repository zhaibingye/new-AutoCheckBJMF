# -*- coding: utf-8 -*-
import requests
import re
import sys
import time
from bs4 import BeautifulSoup
from datetime import datetime

# =========================================================
# >>> 用户配置区域 (请直接在此处修改参数) <<<
# =========================================================

class Config:
    # 1. 班级ID (必填) - 从抓包的 URL 中获取
    # 例如 /student/course/114514/punchs 中的 114514
    CLASS_ID = "114514"

    # 2. 腾讯地图坐标 (必填)
    # 拾取工具: https://lbs.qq.com/getPoint/
    # 建议保留小数点后6位
    LAT = "34.114873"  # 纬度
    LNG = "108.942932" # 经度
    ACC = "10"         # 精度

    # 3. 身份凭证 Cookie (必填)
    # 填写完整的 Cookie 字符串 (包含 remember_student_xxx)
    COOKIE = ""

    # 4. PushPlus 通知 Token (选填)
    # 需要微信通知请填写，否则留空 ""
    PUSHPLUS_TOKEN = "" 

# =========================================================
# >>> 核心逻辑区域 <<<
# =========================================================

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_headers(referer_url):
    """构造与抓包一致的请求头"""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/wxpic,image/webp,image/apng,*/*;q=0.8',
        'Referer': referer_url,
        'Cookie': Config.COOKIE,
        'Upgrade-Insecure-Requests': '1',
        'Host': 'k8n.cn'
    }

def push_notify(content):
    """发送 PushPlus 通知"""
    if not Config.PUSHPLUS_TOKEN:
        return
    print(f"[{get_timestamp()}] 正在发送通知...")
    url = 'http://www.pushplus.plus/send'
    data = {
        'token': Config.PUSHPLUS_TOKEN,
        'title': '班级魔法签到结果',
        'content': content
    }
    try:
        requests.post(url, json=data, timeout=5)
    except Exception as e:
        print(f"通知发送失败: {e}")

def check_status_on_page(html_content, punch_id):
    """
    解析页面 HTML，判断指定 ID 的任务是否包含 '已签' 标记
    根据用户提供的 HTML 结构：
    <div class="card-body" ... id="punchcard_4427853">
        ...
        <span class="layui-badge layui-bg-green">已签</span>
    </div>
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # 查找 ID 为 punchcard_XXXX 的 div
        target_div = soup.find('div', id=f"punchcard_{punch_id}")
        
        if target_div:
            # 在这个 div 内部查找是否存在 class 为 layui-bg-green 且文本为 "已签" 的 span
            badge = target_div.find('span', class_='layui-bg-green', string='已签')
            if badge:
                return True # 已签到
            
        return False # 未签到
    except Exception as e:
        print(f"解析页面状态出错: {e}")
        return False

def main():
    print(f"========== 班级魔法自动签到启动 ==========")
    print(f"时间: {get_timestamp()}")
    
    # 0. 基础检查
    if "这里填写" in Config.CLASS_ID or "这里填写" in Config.COOKIE:
        print("❌ 错误: 请先在代码顶部的 Config 区域填写 ClassID 和 Cookie！")
        sys.exit(1)

    base_url = f'http://k8n.cn/student/course/{Config.CLASS_ID}/punchs'
    referer_url = f'http://k8n.cn/student/course/{Config.CLASS_ID}'
    headers = get_headers(referer_url)

    try:
        # 1. 获取任务列表页面
        print(f"[{get_timestamp()}] 正在获取课程页面...")
        res_list = requests.get(base_url, headers=headers, timeout=10)
        
        if res_list.status_code != 200:
            print(f"❌ 页面请求失败，状态码: {res_list.status_code}")
            return

        # 2. 提取所有签到 ID (包括 GPS 和 二维码)
        # 页面 ID 格式通常为 punchcard_123456
        all_ids = re.findall(r'punchcard_(\d+)', res_list.text)
        # 有些旧代码可能还在用 punch_gps，也兼容一下
        gps_ids = re.findall(r'punch_gps\((\d+)\)', res_list.text)
        
        unique_ids = list(set(all_ids + gps_ids))

        if not unique_ids:
            print(f"[{get_timestamp()}] ✅ 当前没有检测到任何签到活动。")
            return

        print(f"[{get_timestamp()}] ⚠️ 检测到 {len(unique_ids)} 个签到卡片，ID: {unique_ids}")

        # 3. 遍历处理每个任务
        for pid in unique_ids:
            print(f"\n--- 处理任务 ID: {pid} ---")
            
            # 3.1 检查是否已经签到 (预检查)
            if check_status_on_page(res_list.text, pid):
                print(f"[{get_timestamp()}] 🟢 该任务显示 [已签]，跳过。")
                continue

            # 3.2 执行签到请求
            print(f"[{get_timestamp()}] 🔴 状态为未签，正在提交签到请求...")
            post_url = f"http://k8n.cn/student/punchs/course/{Config.CLASS_ID}/{pid}"
            payload = {
                'id': pid,
                'lat': Config.LAT,
                'lng': Config.LNG,
                'acc': Config.ACC,
                'res': '',
                'gps_addr': ''
            }
            
            try:
                # 发送 POST 请求
                requests.post(post_url, headers=headers, data=payload, timeout=10)
                
                # 3.3 验证阶段：再次刷新列表页，查看是否变更为“已签”
                # 注意：这里必须重新请求 GET 页面，因为 POST 返回的可能只是 JSON 或简单的 200 OK
                print(f"[{get_timestamp()}] 正在刷新页面验证结果...")
                time.sleep(1) # 稍等一下服务器处理
                
                res_verify = requests.get(base_url, headers=headers, timeout=10)
                
                if check_status_on_page(res_verify.text, pid):
                    success_msg = f"签到成功！ID: {pid} 状态已更新为 [已签]"
                    print(f"[{get_timestamp()}] ✅ {success_msg}")
                    push_notify(success_msg + f"\n时间: {get_timestamp()}")
                else:
                    fail_msg = f"签到可能失败，ID: {pid} 页面仍未显示 [已签]"
                    print(f"[{get_timestamp()}] ❌ {fail_msg}")
                    # 也可以选择推送失败消息
                    
            except Exception as e:
                print(f"[{get_timestamp()}] 请求异常: {e}")

    except Exception as e:
        print(f"[{get_timestamp()}] ❌ 运行出错: {e}")
    finally:
        print(f"\n========== 脚本运行结束 ==========")

if __name__ == "__main__":
    main()
