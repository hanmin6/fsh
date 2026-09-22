# -*- coding: utf-8 -*-

import iop

# The following are the custom parameters you need to fill in.
# gateway url(eg. BASE_URL = ("https://pre-openapi-api.alibaba.com/rest"))
BASE_URL = ("xxxxxxx")
# appkey
APP_KEY = "xxxxxxx"
# appSecret
APP_SECRET = "xxxxxxxx"
# API path(eg. API_NAME = "/alibaba/order/get")
API_NAME = "xxxxxxx"
# method(eg. HTTP_METHOD = "GET")
HTTP_METHOD = "xxxx"
# access_token
ACCESS_TOKEN = "xxxxxxxxx"

# params 1 : , params 2 : , params 3 :
client = iop.IopClient(BASE_URL, APP_KEY, APP_SECRET)

# create a api request set GET mehotd
# default http method is POST
request = iop.IopRequest(API_NAME, HTTP_METHOD)
request.set_simplify()
# simple type params ,Number ,String
request.add_api_param('e_trade_id', '275331339501025473')
request.add_api_param('data_select', 'draft_role')
request.add_api_param('language', 'en_US')

response = client.execute(request, ACCESS_TOKEN)

# response type nil,ISP,ISV,SYSTEM
# nil ：no error
# ISP : API Service Provider Error
# ISV : API Request Client Error
# SYSTEM : Iop platform Error
print(response.type)

# response code, 0 is no error
print(response.code)

# response error message
print(response.message)

# response unique id
print(response.request_id)

# full response
print(response.body)