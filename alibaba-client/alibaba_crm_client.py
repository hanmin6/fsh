# -*- coding: utf-8 -*-
"""
广州福三和食品有限公司 - 阿里国际站 CRM 数据对接客户端
支持：
  1. 交易订单增量拉取与详情查询 (alibaba.seller.order.list / get)
  2. 在售商品库同步 (alibaba.icbu.product.list / get)
  3. RFQ商机采购需求检索 (alibaba.icbu.rfq.search)
  4. Token 自动持久化存储与过期刷新 (/auth/token/create / refresh)
"""

import os
import sys
import json
import time
import hmac
import hashlib
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(CURRENT_DIR, "token_storage.json")

# 广州福三和食品有限公司应用配置
REDIRECT_URI = os.getenv("ALIBABA_REDIRECT_URI", "https://api.fsh.digital/alibaba/oauth/callback")

TOP_GATEWAY_URL = "https://open-api.alibaba.com/sync"
GOP_GATEWAY_URL = "https://open-api.alibaba.com/rest"


class AlibabaCRMClient:
    def __init__(self, app_key: str | None = None, app_secret: str | None = None):
        app_key = os.getenv("ALIBABA_APP_KEY", "") if app_key is None else app_key
        app_secret = os.getenv("ALIBABA_APP_SECRET", "") if app_secret is None else app_secret
        if not app_key or not app_secret:
            raise ValueError(
                "ALIBABA_APP_KEY and ALIBABA_APP_SECRET must be configured"
            )
        self.app_key = app_key
        self.app_secret = app_secret
        self.token_info = self._load_token()

    # ==================== 1. 签名与底层 HTTP 通信 ====================
    def execute(self, api_name: str, params: dict = None, access_token: str = None, http_method: str = "POST", timeout: int = 30) -> dict:
        """
        核心请求方法，自动识别 TOP 协议 (sync网关) 与 GOP 协议 (rest网关)
        并完成 HMAC-SHA256 签名计算
        """
        if params is None:
            params = {}

        # 区分网关
        is_gop = api_name.startswith("/")
        gateway_url = GOP_GATEWAY_URL if is_gop else TOP_GATEWAY_URL

        # 组装系统级公共参数
        sys_params = {
            "app_key": self.app_key,
            "sign_method": "sha256",
            "timestamp": str(int(time.time() * 1000)),
            "simplify": "true",
            "format": "json"
        }

        if is_gop:
            sys_params["method"] = api_name
        else:
            sys_params["method"] = api_name

        token = access_token or self.token_info.get("access_token")
        if token:
            sys_params["access_token"] = token

        # 合并业务参数
        all_params = sys_params.copy()
        all_params.update({k: str(v) for k, v in params.items()})

        # 签名规则计算
        sort_dict = sorted(all_params.keys())
        if is_gop:
            # GOP 规则：API 路径在最前面
            sign_str = api_name + "".join(f"{k}{all_params[k]}" for k in sort_dict)
        else:
            # TOP 规则：ASCII 字典序排序拼接
            sign_str = "".join(f"{k}{all_params[k]}" for k in sort_dict)

        sign = hmac.new(self.app_secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha256).hexdigest().upper()
        all_params["sign"] = sign

        # 发起 HTTP 请求
        headers = {"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
        try:
            if http_method.upper() == "POST":
                r = requests.post(gateway_url, data=all_params, headers=headers, timeout=timeout)
            else:
                r = requests.get(gateway_url, params=all_params, headers=headers, timeout=timeout)
            
            res_json = r.json()
        except Exception as e:
            raise RuntimeError(f"HTTP 请求异常: {e}")

        # 异常诊断
        if "type" in res_json and res_json.get("type") in ["ISV", "ISP", "SYSTEM"]:
            code = res_json.get("code")
            msg = res_json.get("message")
            req_id = res_json.get("request_id")
            raise RuntimeError(f"阿里开放平台调用报错 [{res_json.get('type')}] code: {code}, message: {msg} (requestId: {req_id})")

        return res_json

    # ==================== 2. 授权与 Token 维护 ====================
    def get_auth_url(self) -> str:
        """生成商家登录授权 URL"""
        return (
            f"https://open-api.alibaba.com/oauth/authorize"
            f"?response_type=code"
            f"&force_auth=true"
            f"&redirect_uri={REDIRECT_URI}"
            f"&client_id={self.app_key}"
        )

    def exchange_code_for_token(self, code: str) -> dict:
        """通过授权 code 换取 access_token"""
        data = self.execute("/auth/token/create", {"code": code})
        self.token_info = data
        self._save_token(data)
        print(">>> 授权 Token 获取成功并已本地保存！")
        return data

    def refresh_access_token(self) -> dict:
        """刷新 access_token"""
        refresh_token = self.token_info.get("refresh_token")
        if not refresh_token:
            raise ValueError("本地未发现可用的 refresh_token")
        data = self.execute("/auth/token/refresh", {"refresh_token": refresh_token})
        self.token_info.update(data)
        self._save_token(self.token_info)
        print(">>> Access Token 刷新成功！")
        return data

    def _save_token(self, token_data: dict):
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_data, f, ensure_ascii=False, indent=2)

    def _load_token(self) -> dict:
        if os.path.exists(TOKEN_FILE):
            try:
                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    # ==================== 3. CRM 核心对接业务 ====================
    def get_order_list(self, page_size: int = 20, start_page: int = 0, modified_start: str = None, modified_end: str = None, status: str = None) -> dict:
        """
        【订单管理】拉取国际站交易订单列表
        :param page_size: 每页数量 (默认 20，最大 100)
        :param start_page: 起始页码 (从 0 开始)
        :param modified_start: 订单修改时间起点 (美西时间，格式：YYYY-MM-DD HH:mm:ss)
        :param modified_end: 订单修改时间终点
        :param status: 状态过滤 (unpay, paid, delivering, trade_success 等)
        """
        query = {
            "role": "seller",
            "page_size": page_size,
            "start_page": start_page
        }
        if modified_start:
            query["modified_date_start"] = modified_start
        if modified_end:
            query["modified_date_end"] = modified_end
        if status:
            query["status"] = status

        return self.execute("alibaba.seller.order.list", {
            "param_trade_ecology_order_list_query": json.dumps(query)
        })

    def get_order_detail(self, e_trade_id: str, data_select: str = "draft_role", language: str = "en_US") -> dict:
        """
        【订单详情】查询单个订单详细数据 (包含买家联系信息、收货地址、成交明细等)
        :param e_trade_id: 订单加密ID (由 order_list 中取得)
        """
        return self.execute("alibaba.seller.order.get", {
            "e_trade_id": e_trade_id,
            "data_select": data_select,
            "language": language
        })

    def get_product_list(self, page_size: int = 20, current_page: int = 1, language: str = "ENGLISH") -> dict:
        """
        【商品同步】拉取店铺所有在售商品列表 (供 CRM 产品库报价使用)
        """
        return self.execute("alibaba.icbu.product.list", {
            "page_size": page_size,
            "current_page": current_page,
            "language": language
        })

    def get_product_detail(self, product_id: str, language: str = "ENGLISH") -> dict:
        """
        【商品详情】获取指定商品详情
        """
        return self.execute("alibaba.icbu.product.get", {
            "product_id": product_id,
            "language": language
        })

    def search_rfq(self, keywords: str = "", page: int = 1, page_size: int = 20) -> dict:
        """
        【商机线索】查询/推荐 RFQ 采购需求商机 (沉淀 CRM 潜客线索)
        """
        return self.execute("alibaba.icbu.rfq.search", {
            "keywords": keywords,
            "page": page,
            "page_size": page_size
        })


# ==================== 测试运行 ====================
if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    client = AlibabaCRMClient()

    print("==================================================")
    print("广州福三和食品有限公司 - 阿里国际站 CRM 数据接口联调")
    print("==================================================")

    # 1. 验证商品列表拉取
    print("\n[1/2] 正在拉取在售商品列表 (Product Sync)...")
    try:
        products = client.get_product_list(page_size=3, current_page=1)
        total = products.get("total_item")
        items = products.get("products", [])
        print(f"[成功] 商品列表拉取成功！店铺在售总商品数: {total}")
        for idx, item in enumerate(items, 1):
            print(f"  ({idx}) 商品名称: {item.get('subject')}")
            print(f"      商品类目/分组: {item.get('group_name')}")
            print(f"      创建时间: {item.get('gmt_create')}")
    except Exception as e:
        print("[失败] 商品拉取失败:", e)

    # 2. 验证订单列表拉取
    print("\n[2/2] 正在拉取交易订单列表 (Order Sync)...")
    try:
        orders = client.get_order_list(page_size=5, start_page=0)
        print("[成功] 订单列表接口调用成功！返回结果:")
        print(json.dumps(orders, ensure_ascii=False, indent=2))
    except Exception as e:
        print("[失败] 订单拉取失败:", e)

