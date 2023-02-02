
import socket
import sys
import json
import requests
from datetime import datetime

from Tea.core import TeaCore

from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_alidns20150109 import models as alidns_20150109_models
from alibabacloud_alidns20150109.client import Client
from alibabacloud_tea_util.models import RuntimeOptions
from alibabacloud_tea_console.client import Client as ConsoleClient
from alibabacloud_tea_util.client import Client as UtilClient

HOST = "alidns.cn-hangzhou.aliyuncs.com"
domain_ip_dict = {}


def config_ini(access_key_id, access_key_secret, region_id, push_token):
    """
    :param access_key_id: 阿里云access
    :param access_key_secret: 阿里云access
    :param region_id: 阿里云region
    :param push_token: pushplush token
    :return:
    """
    global client
    global runtime_config
    global pushplus_token

    config = open_api_models.Config(
        access_key_id=access_key_id,
        access_key_secret=access_key_secret,
        region_id=region_id,
        endpoint=HOST,
        read_timeout=10000,  # 读超时时间 单位毫秒(ms)
        connect_timeout=5000  # 连接超时 单位毫秒(ms)
    )

    runtime_config = RuntimeOptions(
        autoretry=True,  # 是否开启重试 默认关闭
        max_attempts=3   # 重试次数 默认3次
    )
    client = Client(config)

    pushplus_token = push_token


def pushpush(p_content):
    """
    使用pushplus服务做微信消息推送
    http://www.pushplus.plus/
    :return:
    """
    token = pushplus_token
    title = "kie-server ipv6 发生变化"
    content = p_content
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": token,
        "title": title,
        "template": "txt",
        "content": content
    }
    body = json.dumps(data).encode(encoding='utf-8')
    headers = {'Content-Type': 'application/json'}

    requests.post(url=url, data=body, headers=headers)


def get_ipv6() -> str:
    """
    这个方法是目前见过最优雅获取本机服务器的IP方法了。没有任何的依赖，也没有去猜测机器上的网络设备信息。
    而且是利用 UDP 协议来实现的，生成一个UDP包，把自己的 IP 放如到 UDP 协议头中，然后从UDP包中获取本机的IP。
    这个方法并不会真实的向外部发包，所以用抓包工具是看不到的。但是会申请一个 UDP 的端口，所以如果经常调用也会比较耗时的，这里如果需要可以将查询到的IP给缓存起来，性能可以获得很大提升。
    :return: ip
    """
    global local_ip
    s = None
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.connect(('2001::80f2:f09b', 53))
        ipv6 = s.getsockname()[0]
        local_ip = ipv6
    finally:
        if s:
            s.close()
    return local_ip


def get_old_ipv6(old_ipv6_recode_file) -> str:
    with open(old_ipv6_recode_file, 'r') as f:
        for ip in f.readlines():
            if len(ip) > 10:
                return ip.strip()
    return ""


def update_domain_ip(client: Client, domain_ip_dict:dict, new_ip):
    if domain_ip_dict:
        push_content = ""
        for recode_id, ip_info in domain_ip_dict.items():
            if ip_info['ip'] != new_ip:
                request = alidns_20150109_models.UpdateDomainRecordRequest()
                request.record_id = recode_id
                request.value = new_ip
                request.rr = ip_info['rr']
                request.type = ip_info['recode_type']
                try:
                    resp = client.update_domain_record_with_options(request, runtime_config)
                    ConsoleClient.log(recode_id + ':-------------------修改解析记录--------------------')
                    ConsoleClient.log("recode_id:%s, ip:%s, rr:%s, recode_type:%s" % (request.record_id,
                                                                                      request.value,
                                                                                      request.rr,
                                                                                      request.type))
                    ConsoleClient.log(UtilClient.to_jsonstring(TeaCore.to_map(resp)))

                    push_content = push_content + " - recode_id:%s, rr:%s, old_ip:%s, new_ip:%s - \n" % (request.record_id,
                                                                                  request.rr,
                                                                                  request.value,
                                                                                  ip_info['ip'])
                    # 发送微信通知
                except Exception as error:
                    ConsoleClient.log(error)
        if len(push_content) > 0:
            pushpush(push_content)


def get_analyze_ip_record_id(client: Client, domain_name: str):
    global domain_ip_dict
    request = alidns_20150109_models.DescribeDomainRecordsRequest()
    request.domain_name = domain_name
    try:
        # 复制代码运行请自行打印 API 的返回值
        resp = client.describe_domain_records_with_options(request, runtime_config)
        ConsoleClient.log('-------------------获取主域名的所有解析记录列表--------------------')
        ConsoleClient.log(UtilClient.to_jsonstring(TeaCore.to_map(resp)))
    except Exception as error:
        # 如有需要，请打印 error
        UtilClient.assert_as_string(error)
        return

    if resp is not None and len(resp.body.domain_records.record) > 0:
        for recode in resp.body.domain_records.record:
            if recode.record_id not in domain_ip_dict:
                domain_ip_dict[recode.record_id] = {}
            domain_ip_dict[recode.record_id]['ip'] = recode.value
            domain_ip_dict[recode.record_id]['rr'] = recode.rr
            domain_ip_dict[recode.record_id]['recode_type'] = recode.type

    return


if __name__ == "__main__":
    recode_file_name = sys.argv[3]
    access_key_id = sys.argv[1]
    access_key_secret = sys.argv[2]
    pushplus_token = sys.argv[4]
    domain = 'kieoo.space'
    ConsoleClient.log('-------------------开始检查 %s--------------------' % (datetime.now()))
    ConsoleClient.log('远端旧ip配置:%s' % (get_old_ipv6(recode_file_name)))
    ConsoleClient.log('本机ip配置:%s' % (get_ipv6()))
    # 只有本地ip和旧的缓存ip不一致时, 才进行修改
    if get_ipv6() != get_old_ipv6(recode_file_name):
        ConsoleClient.log('-------------------ip不一致, 需要修改%s解析-------------------' % (domain))
        config_ini(access_key_id, access_key_secret, 'cn-hangzhou', pushplus_token)
        get_analyze_ip_record_id(client=client, domain_name=domain)
        update_domain_ip(client=client, domain_ip_dict=domain_ip_dict, new_ip=local_ip)
        with open(recode_file_name, 'w') as f:
            pass
            f.write(local_ip)
    else:
        ConsoleClient.log("ip一致, 不需要修改")
    ConsoleClient.log('-------------------检查结束 %s--------------------' % (datetime.now()))
