# 这是一个示例 Python 脚本。
import os
from datetime import datetime, timezone
import datetime
import email_model
from oci.identity import IdentityClient
from oci.config import from_file
from oci.core.models import Shape
from oci.config import validate_config
from oci.identity.models import CreateUserDetails
from oci.identity.models import AddUserToGroupDetails
from oci.core.models import LaunchInstanceDetails
from oci.core.models import InstanceSourceViaImageDetails
import time
import oci
import pytz
import json
from currency_converter import CurrencyConverter
import pandas as pd
import matplotlib.pyplot as plt

# 管理组？到时候分配给新建用户administrators权限
group_name = "Administrators"
# 配置文件路径
file_location = "oci/config.prod"
# file_location = "/root/demo/oci/config.prod"
# 文件路径
file_path = 'params.txt'

arm = "VM.Standard.A1.Flex"
amd = "VM.Standard.E2.1.Micro"


# file_path = '/root/demo/params.txt'


def get_compute():
    # 创建计算服务客户端（根据您之前设置的配置信息）
    compute = oci.core.ComputeClient(get_config(file_location))
    return compute


def get_launch_instance_details():
    # 设置实例创建的参数
    launch_instance_details = LaunchInstanceDetails()
    return launch_instance_details


def get_launch_instance_details_shape():
    # 设置实例创建的参数
    launch_instance_details = LaunchInstanceDetails()
    shape = launch_instance_details.shape
    return shape


# 使用 ImageCatalogClient 客户端来获取镜像信息
def get_image_catalog_client():
    image_catalog_client = oci.artifacts.ArtifactsClient(get_config(file_location))
    return image_catalog_client


def get_images_list(shape):
    # 获取映像列表
    # 默认Canonical-Ubuntu-20.04-2023.06.30-0
    compute = get_compute()
    images = compute.list_images(
        compartment_id=get_compartment_id(),
        # operating_system="linux",
        # operating_system_version = "20.04",
        shape=shape,  # 很重要，必须加上shape
        # limit = 41,
        # page = "EXAMPLE-page-Value",
        # sort_by = "DISPLAYNAME",
        # sort_order = "ASC",
    )
    # print(images.data)
    for image in images.data:
        # print("映像名称:", image.display_name + "映像 OCID:", image.id)
        if (
                image.display_name == "Canonical-Ubuntu-20.04-2024.08.26-0" or image.display_name == "Canonical-Ubuntu-20.04-aarch64-2024.08.26-0"):
            # print(image.id)
            return image.id
    # 或者抛出异常
    raise ValueError("未知的镜像。。。")


def get_shapes_list(compute, image_id):
    # 获取计算形状列表
    shapes = compute.list_shapes(compartment_id=get_compartment_id(), image_id=image_id)
    return shapes.data


def get_shape(image_id, shape_name):
    # 假设您已经创建了一个ComputeClient实例：compute
    compute = get_compute()
    shapes = get_shapes_list(compute, image_id)
    for shape in shapes:
        if shape.shape == shape_name:
            return shape
    raise ValueError("没有符合条件的Shape")


def get_compute_config():
    compute = get_compute()
    compartment_id = get_compartment_id()
    # 要查询的实例的 OCID 或实例的名称和所属分区的 OCID
    instance_ocid = "ocid1.instance.oc1.ap-singapore-1.anzwsljrw7yy4jic6m56v3xntc4bj3ofhjn5kd65s53ajp3lllkfv6vtgxua"  # 替换为您要查询的实例的 OCID
    # instance_name = "your-instance-name"  # 如果您知道实例的名称，可以使用实例名称进行查询
    # compartment_id = "your-compartment-id"  # 替换为实例所属的分区的 OCID
    # 使用 get_instance() 方法查询实例的详细信息
    try:
        instance = compute.get_instance(instance_id=instance_ocid).data
        # print("实例名称: ", instance.display_name)
        # print("实例 OCID: ", instance.id)
        # print("实例状态: ", instance.lifecycle_state)
        # print("实例所属分区: ", instance.compartment_id)
        # print("实例可用域: ", instance.availability_domain)
        # print("实例形状: ", instance.shape)
        print(instance)
        # 在此可以继续打印或处理其他实例属性
    except oci.exceptions.ServiceError as e:
        print("未找到指定实例:", e)

    # 关闭 ComputeClient 客户端


def get_tenancy():
    identity_client = get_identityClient()
    tenancy = identity_client.get_tenancy(get_compartment_id()) #传入租户ID
    # print(tenancy.data.description)
    return tenancy.data.description

def get_availability_domain():  # 所有可用域作为数组返回
    # 创建 IdentityClient 客户端
    identity_client = get_identityClient()
    compartment_id = get_compartment_id()
    availability_domains = identity_client.list_availability_domains(
        compartment_id=compartment_id
    )
    availability_domains_array = [ad.name for ad in availability_domains.data]
    return availability_domains_array


def create_instance_config():
    compartment_id = get_compartment_id()
    config = get_config(file_location)
    compute_management_client = oci.core.ComputeManagementClient(config)
    # create_instance_config_details = oci.core.models.CreateInstanceConfigurationDetails(
    #     compartment_id=compartment_id,
    #     display_name="MyInstanceConfig",
    #     # source="INSTANCE",   # 创建一个实例配置，使用现有实例作为模板
    #     instance_details=oci.core.models.InstanceConfigurationInstanceDetails(
    #         instance_type="compute",
    #     )
    # )

    create_instance_config_response = compute_management_client.create_instance_configuration(
        create_instance_configuration=oci.core.models.CreateInstanceConfigurationDetails(
            source="NONE",
            instance_details=oci.core.models.InstanceConfigurationInstanceDetails(
                instance_type="compute",
            ),

            compartment_id=compartment_id,
            # instance_id="ocid1.test.oc1..<unique_ID>EXAMPLE-instanceId-Value",
            # defined_tags={
            #     'EXAMPLE_KEY_CaKTw': {
            #         'EXAMPLE_KEY_hs0Jo': 'EXAMPLE--Value'}},
            display_name="my_config",
            # freeform_tags={
            #     'EXAMPLE_KEY_XMj6t': 'EXAMPLE_VALUE_kXDdvieud6iBj1TxlG74'}
        ),
        # opc_retry_token="EXAMPLE-opcRetryToken-Value"
    )

    # Get the data from response
    print(create_instance_config_response.data)

    # create_instance_config_response = compute_management_client.create_instance_configuration(
    #     create_instance_config_details)
    # 获取实例配置的 OCID
    instance_config_id = create_instance_config_response.data.id
    print(instance_config_id)

    return instance_config_id


def get_subnet_id():
    # 创建 VirtualNetwork 客户端
    virtual_network_client = oci.core.VirtualNetworkClient(get_config(file_location))
    compartment_id = get_compartment_id()
    # 查询指定 Compartment ID 下的子网列表
    try:
        response = virtual_network_client.list_subnets(compartment_id=compartment_id)
        subnets = response.data
        # print(subnets)
        if subnets:
            # 提取第一个子网的 OCID
            subnet_id = subnets[0].id
            return subnet_id
        else:
            print("当前租户中没有发现子网.")
            return None
    except oci.exceptions.ServiceError as e:
        print("查询子网时发生错误:", e)
        return None


def ListVnicAttachments():  # 返回一个.data数组，包含ListVnic的个数，几个实例就有几个vnci和分别对应的subnit
    compute = get_compute()
    compartment_id = get_compartment_id()
    list_vnic_attachments_response = compute.list_vnic_attachments(
        compartment_id=compartment_id)
    # 从响应中获取数据
    # print(list_vnic_attachments_response.data)
    return list_vnic_attachments_response.data


def get_vnic():  # 获取所有实例的vnic信息
    Vnics = ListVnicAttachments()
    alive_instances = []
    for Vnic in Vnics:
        if Vnic.lifecycle_state == "ATTACHED":
            alive_instances.append(Vnic)
    return alive_instances


def get_vnicid_by_instance_id(instance_id):
    config = oci.config.from_file(file_location=file_location, profile_name='DEFAULT')
    core_client = oci.core.VirtualNetworkClient(config)
    alive_instances = get_vnic()
    # print(alive_instances)
    for Vnic in alive_instances:
        if Vnic.instance_id == instance_id:
            get_vnic_response = core_client.get_vnic(vnic_id=Vnic.vnic_id)
            return get_vnic_response.data


def get_ipv4_by_vnic(instance_id):
    this_vnic = get_vnicid_by_instance_id(instance_id)
    print(this_vnic)
    return this_vnic.public_ip


def get_hostname_label_by_vnic(instance_id):  # 获取实例名称
    this_vnic = get_vnicid_by_instance_id(instance_id)
    return this_vnic.hostname_label


def get_ipv6_addresses_by_vnic(instance_id):  # 获取ipv6
    this_vnic = get_vnicid_by_instance_id(instance_id)
    return this_vnic.ipv6_addresses


def get_lifecycle_state_by_vnic(instance_id):  # 获取实例状态，类似running
    this_vnic = get_vnicid_by_instance_id(instance_id)
    return this_vnic.lifecycle_state


def get_time_created_by_vnic(instance_id):  # 获取实例创建时间
    this_vnic = get_vnicid_by_instance_id(instance_id)
    return this_vnic.time_created


def list_vcns():
    compartment_id = get_compartment_id()
    virtual_network_client = oci.core.VirtualNetworkClient(get_config(file_location))
    response = virtual_network_client.list_vcns(compartment_id=compartment_id)
    print(response.data)
    return response.data, None


def create_or_get_vcn():
    vcns = list_vcns()
    if len(vcns) >= 1:
        vcn = vcns[0]
    return vcn


# 创建或获取基础网络设施
def CreateOrGetNetworkInfrastructure():
    vcn = create_or_get_vcn()
    print(vcn)


def creat_instance(shape_name, instance_ocpus, instance_memory_in_gbs, boot_volume_size_in_gbs, frequency):
    # shape_name, instance_ocpus, instance_memory_in_gbs, boot_volume_size_in_gbs
    if shape_name == "amd":
        shape_name = amd
    elif shape_name == "arm":
        shape_name = arm
    instance = oci.core.models.Instance
    print("创建计算服务客户端compute:...")
    compute = get_compute()
    print("已完成。")
    print("获取租户Id中:...")
    compartment_id = get_compartment_id()
    print("已完成。")

    print("获取镜像信息中:...")
    image_id = get_images_list(shape_name)
    print("已完成。")
    # print("image_id:" + image_id)

    print("获取shape信息中:...")
    shape = get_shape(image_id, shape_name)  # 该shape值为默认配置amd-1+1或arm-1+6
    if shape is None:
        print("ERROR-----shape信息-----")
    print("加载信息中:...")
    ShapeModel = oci.core.models.Shape()  # 创建shape对象,并传递形参值
    ShapeModel.shape = shape_name
    ShapeModel.ocpus = instance_ocpus
    ShapeModel.memory_in_gbs = instance_memory_in_gbs

    request = oci.core.models.LaunchInstanceDetails()  # 创建实例对象request
    request.compartment_id = compartment_id
    request.shape = ShapeModel.shape

    # print(request.shape)
    if "flex" in ShapeModel.shape.lower():  # 有flex关键字，说明该实例为ARM,则要把4+24类似参数传递
        request.shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=ShapeModel.ocpus,
            memory_in_gbs=ShapeModel.memory_in_gbs
        )
    print("加载成功。")
    print("正在获取子网...")
    subnet_id = get_subnet_id()
    request.create_vnic_details = oci.core.models.CreateVnicDetails(
        subnet_id=subnet_id
    )
    print("已完成。")
    print("加载source_details中:...")
    # 创建一个新的 InstanceSourceViaImageDetails 对象
    sd = InstanceSourceViaImageDetails()
    # 将镜像 ID 赋值给实例来源详情的 ImageId 字段
    sd.image_id = image_id
    sd.source_type = "image"
    # boot_volume_size_in_gbs = 50  # 启动卷大小
    # 检查实例的启动卷大小是否大于 0
    if boot_volume_size_in_gbs > 0:
        # 如果实例的启动卷大小大于 0，则将该大小赋值给实例来源详情的 BootVolumeSizeInGBs 字段
        sd.boot_volume_size_in_gbs = boot_volume_size_in_gbs
    # 将配置好的实例来源详情 sd 赋值给创建实例的请求 request 的 SourceDetails 字段
    request.source_details = sd
    # 设置实例的块存储传输加密功能为 True
    request.is_pv_encryption_in_transit_enabled = True
    print("已完成。")
    # 创建一个空的字典来存储元数据
    print("设置公钥中:...")
    meta_data = {}
    # 将实例的 SSH 公钥赋值给元数据的 "ssh_authorized_keys" 字段
    meta_data[
        "ssh_authorized_keys"] = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCiwp3W8IwI1ineymY5o3F2s02np1OfApkBlnFfJFvQ5MYfFl1F4Dqry429EC3zdXGjX+4bhU9nX2sXjw0pk8ZyEC5zJTZ75raqAKFtQaBhB+SY5CcGwD5NvGnLGd+MNhT5K1tHvF5KJSMELsmnl2/5DwrGeWiV0ZUWvMg8KdsRlNGCtTaNQnUxKW9WqYqFrD/tFiZ1tGSQFNr6V3KqjlfZY3bbtURazmthSncaqkZnqvM0Nlap4KFjAArof1tYGkeCXFiO7/FMpFCUtYZpNG5Gum+1gDVVKJZLCjUSWWeO6fn5uVOx5vjQnxzqExNbHo7ke2++Z6B5r6qvMxnlvtR/ 张迪生@DESKTOP-CO53JAE"

    request.metadata = meta_data
    print("已完成。")
    print("加载可用域中:...")
    availability_domain = get_availability_domain()
    print("已完成。")
    num = len(availability_domain)
    print("可用域数量:" + str(num))
    flag = True  # 设置一个标志变量，用于控制是否继续 while 循环
    print("创建实例中:...")
    print("-------------------开始---------------------")
    subject_fail = email_model.subject_fail
    body_fail = email_model.body_fail
    subject_succeed = email_model.subject_succeed
    body_succeed = email_model.body_succeed
    print("正在创建---配置:" + shape_name + "  ocpu:" + str(instance_ocpus) + "  内存(GB):" + str(
        instance_memory_in_gbs) + "  引导卷(GB):" + str(boot_volume_size_in_gbs))
    if len(availability_domain) > 1:
        numb1 = 1
        while flag:
            for ad in availability_domain:
                print("正在尝试:   " + ad)
                request.availability_domain = ad
                # 获取当前时间
                current_time_utc = datetime.datetime.now(pytz.utc)
                # 转换为UTC+8时区
                china_tz = pytz.timezone('Asia/Shanghai')
                timestamp = current_time_utc.astimezone(china_tz)
                try:
                    instance_response = compute.launch_instance(request)
                    if instance_response.status == 200:
                        print("(^o^)实例创建成功！！！")
                        time.sleep(60)
                        instance = instance_response.data
                        instance_id = str(instance.id)
                        body_succeed = body_succeed + "\n时间:" + str(timestamp) + "\n租户:" + str(get_tenancy()) + "\n区域:" + ad + "\n实例名称:" + str(
                            instance.display_name) + "\n可用性域:" + str(
                            instance.availability_domain) + "\n实例类型:" + str(
                            instance.shape) + "\nOCPU个数:" + str(instance.shape_config.ocpus) + "\n内存(GB):" + str(
                            instance.shape_config.memory_in_gbs) + "\nipv4:" + str(
                            get_ipv4_by_vnic(instance_id)) + "\n尝试次数:" + str(numb1)
                        email_model.email_send(subject_succeed, body_succeed)
                        flag = False  # 设置标志变量为 False，终止 while 1 循环
                        break
                    else:
                        error_message = instance_response.data.message
                        print("未知错误:", error_message)
                        # 这里发一封错误邮件
                        email_model.email_send(subject_fail, "这里为非200错误，未知原因！")
                        flag = False  # 设置标志变量为 False，终止 while 1 循环
                        break
                except Exception as e:
                    # 处理异常，例如打印异常信息
                    status = getattr(e, 'status', None)
                    code = getattr(e, 'code', None)

                    if status == 500:
                        print(str(timestamp) + "--创建失败(╯︵╰)--第" + str(
                            numb1) + "次抢机--可用性域 " + ad + " 主机容量不足，请再次尝试。。。")
                        numb1 = numb1 + 1
                        time.sleep(frequency)
                    elif status == 429:
                        print(str(timestamp) + "--创建失败(╯︵╰)---当前抢机速度过快，请尝试降低速度。。。")
                        numb1 = numb1 + 1
                        time.sleep(frequency)
                    elif status == 404:
                        print(str(timestamp) + "--创建失败(╯︵╰)---当前可用性域:" + ad + "  下无  " + str(shape_name))
                    elif status == 400:
                        print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code))
                        time.sleep(frequency)
                    elif status == 401:
                        print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code) + ",当前API无权限。")
                        body_fail += str(status) + "\n时间:" + str(
                            timestamp) + "\n区域:" + ad + "\n正在创建---配置:" + shape_name + "  ocpu:" + str(
                            instance_ocpus) + "  内存(GB):" + str(
                            instance_memory_in_gbs) + "  引导卷(GB):" + str(boot_volume_size_in_gbs) + "\n" + str(e)
                        email_model.email_send(subject_fail, body_fail)
                        time.sleep(frequency)
                        break
                    elif status == 502:
                        print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code))
                        time.sleep(frequency)
                    elif status == 503:
                        print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code))
                        time.sleep(frequency)
                    elif status is None:
                        print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code) + str(e))
                        time.sleep(frequency)
                    else:
                        print(str(timestamp) + "--出现未知错误。。。错误代码: " + str(status) + "\n" + str(e))
                        # 这里进行更新
                        body_fail += str(status) + "\n时间:" + str(
                            timestamp) + "\n区域:" + ad + "\n正在创建---配置:" + shape_name + "  ocpu:" + str(
                            instance_ocpus) + "  内存(GB):" + str(
                            instance_memory_in_gbs) + "  引导卷(GB):" + str(boot_volume_size_in_gbs) + "\n" + str(e)
                        email_model.email_send(subject_fail, body_fail)
                        flag = False  # 设置标志变量为 False，终止 while 1 循环
                        break

    if len(availability_domain) == 1:
        ad1 = availability_domain[0]
        print("正在尝试:   " + ad1)
        request.availability_domain = ad1
        numb = 1
        while 1:
            # 获取当前时间
            current_time_utc = datetime.datetime.now(pytz.utc)
            # 转换为UTC+8时区
            china_tz = pytz.timezone('Asia/Shanghai')
            timestamp = current_time_utc.astimezone(china_tz)
            try:
                instance_response = compute.launch_instance(request)
                if instance_response.status == 200:
                    print("(^o^)实例创建成功！！！")
                    time.sleep(60)
                    instance = instance_response.data
                    instance_id = str(instance.id)
                    body_succeed = body_succeed + "\n时间:" + str(timestamp) + "\n租户:" + str(get_tenancy()) + "\n区域:" + ad1 + "\n实例名称:" + str(
                        instance.display_name) + "\n可用性域:" + str(
                        instance.availability_domain) + "\n实例类型:" + str(
                        instance.shape) + "\nOCPU个数:" + str(instance.shape_config.ocpus) + "\n内存(GB):" + str(
                        instance.shape_config.memory_in_gbs) + "\nipv4:" + str(
                        get_ipv4_by_vnic(instance_id)) + "\n尝试次数:" + str(numb)
                    email_model.email_send(subject_succeed, body_succeed)
                    break
                else:
                    error_message = instance_response.data.message
                    print("未知错误:", error_message)
                    # 这里进行更新
                    email_model.email_send(subject_fail, "这里为非200错误，未知原因！")
                    break
            except Exception as e:
                # 处理异常，例如打印异常信息
                status = getattr(e, 'status', None)
                code = getattr(e, 'code', None)

                if status == 500:
                    print(str(timestamp) + "--创建失败(╯︵╰)--第" + str(
                        numb) + "次抢机--可用性域 " + ad1 + " 主机容量不足，请再次尝试。。。")
                    # email_model.email_send("测试", "测试")
                    numb = numb + 1
                    time.sleep(frequency)
                elif status == 429:
                    print(str(timestamp) + "--创建失败(╯︵╰)---当前抢机速度过快，请尝试降低速度。。。")
                    numb1 = numb + 1
                    time.sleep(frequency)
                elif status == 404:
                    print(str(timestamp) + "--创建失败(╯︵╰)---当前可用性域:" + ad1 + "  下无  " + str(shape_name))
                    time.sleep(frequency)
                elif status == 400:
                    print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code))
                    time.sleep(frequency)
                elif status == 401:
                    print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code) + ",当前API无权限。")
                    body_fail += str(status) + "\n时间:" + str(
                        timestamp) + "\n区域:" + ad1 + "\n正在创建---配置:" + shape_name + "  ocpu:" + str(
                        instance_ocpus) + "  内存(GB):" + str(
                        instance_memory_in_gbs) + "  引导卷(GB):" + str(boot_volume_size_in_gbs) + "\n" + str(e)
                    email_model.email_send(subject_fail, body_fail)
                    time.sleep(frequency)
                    break
                elif status == 502:
                    print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code))
                    time.sleep(frequency)
                elif status == 503:
                    print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code))
                    time.sleep(frequency)
                elif status is None:
                    print(str(timestamp) + "--创建失败(╯︵╰)---错误类型:" + str(code) + str(e))
                    time.sleep(frequency)
                else:
                    print("出现未知错误。。。错误代码:" + str(status) + "\n" + str(e))
                    # 这里进行更新
                    body_fail += str(status) + "\n时间:" + str(
                        timestamp) + "\n区域:" + ad1 + "\n正在创建---配置:" + shape_name + "  ocpu:" + str(
                        instance_ocpus) + "  内存(GB):" + str(
                        instance_memory_in_gbs) + "  引导卷(GB):" + str(boot_volume_size_in_gbs) + "\n" + str(e)
                    email_model.email_send(subject_fail, body_fail)
                    break

    print("-------------------结束---------------------")
    print(instance)


def get_config(file_location):
    # Using the default profile from a different file
    config = from_file(file_location)
    return config


def get_identityClient():
    # 客户端只需要一个有效的配置对象
    identity = IdentityClient(get_config(file_location))
    return identity

def get_usageClient():
    # 创建 UsageAPI 客户端
    usage_client  = oci.usage_api.UsageapiClient(get_config(file_location))
    return usage_client

# 设置当前月份的时间范围
def get_currentMonthBill():
    usage_client = get_usageClient()

    # 设置当前月份的时间范围
    now = datetime.datetime.utcnow()
    start_time = datetime.datetime(now.year, now.month, 1)  # 月初
    end_time = datetime.datetime(now.year, now.month, now.day)  # 当天
    # 请求账单参数
    usage_request = oci.usage_api.models.RequestSummarizedUsagesDetails(
        tenant_id=get_compartment_id(),  # 租户OCID
        time_usage_started=start_time,
        time_usage_ended=end_time,
        granularity="DAILY"
        #is_aggregate_by_time=True
    )
    response = usage_client.request_summarized_usages(usage_request)
    #print(response.data)
    return response.data

def get_compartment_id():
    # 租户id
    config = get_config(file_location)
    compartment_id = config["tenancy"]
    return compartment_id


def get_group_id():
    identity = get_identityClient()
    config = get_config(file_location)
    groups = identity.list_groups(compartment_id=config["tenancy"]).data
    # 遍历找到admin组
    for group in groups:
        if group.name == group_name:
            group_ocid = group.id
    return group_ocid


def creat_user(you_email):  # 注意！这里的邮箱和
    config = get_config(file_location)
    identity = get_identityClient()
    compartment_id = get_compartment_id()

    request = CreateUserDetails()
    request.compartment_id = compartment_id
    request.name = you_email
    request.description = "Created with the Fuckyou"
    request.email = you_email
    # 发送创建用户的请求
    user = identity.create_user(request)
    # 打印创建的用户的 ID
    # print(user.data.id)
    # 获取指定组的 OCID（例如，通过组名称查询）
    # 使用 list_groups() 方法列出所有组
    groups = identity.list_groups(compartment_id=config["tenancy"]).data
    # 遍历找到admin组
    group_ocid = ""
    for group in groups:
        if group.name == group_name:
            group_ocid = group.id

    # print(group_ocid)
    # 将用户添加到组的请求模型实例
    request = AddUserToGroupDetails()
    # {
    #     "group_id": null,
    #     "user_id": null
    # }

    request.group_id = group_ocid
    request.user_id = user.data.id

    # 发送将用户添加到组的请求
    response = identity.add_user_to_group(request)

    # 打印响应状态码（200 表示成功）
    print(response.status)


def delete_user(my_email):  # 注意！这里的邮箱和
    config = get_config(file_location)
    identity = get_identityClient()
    compartment_id = get_compartment_id()
    groups = identity.list_groups(compartment_id=config["tenancy"]).data
    group_ocid = ""
    for group in groups:
        if group.name == group_name:
            group_ocid = group.id
            break
    # 这里group_ocid为 admin 组
    users = identity.list_users(compartment_id=config["tenancy"]).data
    user_ocid = None
    for user in users:
        # print(user)
        if user.name == my_email:
            user_ocid = user.id
            # break
    # print(user_ocid)
    # memberships = identity.list_user_group_memberships(
    #     compartment_id=compartment_id,
    #     user_id=user_ocid,
    #     group_id=group_ocid)
    # print(memberships)
    # assert len(memberships.data) == 1 #==1则表示用户在该组中
    #
    # membership_id = memberships.data[0].id
    # identity.remove_user_from_group(user_group_membership_id=membership_id).status

    Delete_user = identity.delete_user(user_id=user_ocid)
    print(Delete_user.status)


def read_params_from_file(file_path):
    params = {}
    with open(file_path, 'r') as file:
        for line in file:
            key, value = line.strip().split('=')
            params[key] = value

    params['instance_ocpus'] = int(params['instance_ocpus'])
    params['instance_memory_in_gbs'] = int(params['instance_memory_in_gbs'])
    params['boot_volume_size_in_gbs'] = int(params['boot_volume_size_in_gbs'])
    params['frequency'] = int(params['frequency'])
    return params


def get_all_network_info():
    # 子网的 OCID，你需要提供要查询的子网的 OCID
    subnet_ocid = get_subnet_id()
    # 获取当前日期和时间
    # current_datetime = datetime.datetime.now()

    compartment_id = get_compartment_id()
    # OCI 指标查询的起始时间和结束时间
    start_time = "2023-08-01T00:00:00Z"  # 修改为你的起始时间
    end_time = "2023-09-02T00:00:00Z"  # 修改为你的结束时间

    # 创建 OCI 客户端
    config = get_config(file_location)
    monitoring_client = oci.monitoring.MonitoringClient(config)
    obj_list_metrics = {}
    # 查询子网的网络流量指标
    try:
        response = monitoring_client.list_metrics(
            compartment_id=compartment_id,
            # opc_request_id=subnet_ocid,
            list_metrics_details=oci.monitoring.models.ListMetricsDetails()
        )
        # summarize_metrics_data_response = monitoring_client.summarize_metrics_data(
        #     compartment_id=compartment_id,
        #     summarize_metrics_data_details=oci.monitoring.models.SummarizeMetricsDataDetails(
        #         namespace="EXAMPLE-namespace-Value",
        #         query="EXAMPLE-query-Value",
        #         resource_group="EXAMPLE-resourceGroup-Value",
        #         start_time=datetime.strptime(
        #             "2023-07-15T14:17:34.472Z",
        #             "%Y-%m-%dT%H:%M:%S.%fZ"),
        #         end_time=datetime.strptime(
        #             "2023-08-24T14:46:54.388Z",
        #             "%Y-%m-%dT%H:%M:%S.%fZ"),
        #         resolution="EXAMPLE-resolution-Value"),
        #     opc_request_id="OJH3ENHCKITISWYMJD0U<unique_ID>",
        #     compartment_id_in_subtree=True)
        # print(summarize_metrics_data_response.data)
        # 提取并打印出子网的网络流量信息
        obj_list_metrics = {}
        for item in response.data:
            if item.name == "BytesFromIgw" or item.name == "BytesToIgw":
                obj_list_metrics[item.name] = item
        obj_list_metrics = obj_list_metrics
        # for item in response.data:
        #     print(
        #         f"时间: {item.time_stamp}, 入站字节数: {item.values['Network.InBytes[1m]']}, 出站字节数: {item.values['Network.OutBytes[1m]']}")

    except oci.exceptions.ServiceError as e:
        print(f"查询流量信息失败: {e}")
    # resourceId = obj_list_metrics['BytesFromIgw']['dimensions']['resourceId']
    name = obj_list_metrics['BytesFromIgw'].name
    namespace = obj_list_metrics['BytesFromIgw'].namespace

    summarize_metrics_data_response = monitoring_client.summarize_metrics_data(
        compartment_id=compartment_id,
        summarize_metrics_data_details=oci.monitoring.models.SummarizeMetricsDataDetails(
            namespace=namespace,
            query="NetworkInPackets",
            # resource_group = null,
            start_time="2023-01-01T00:00:00Z",
            end_time="2023-01-02T00:00:00Z"
        ),
    )
    print(summarize_metrics_data_response.data)


def get_security_policies():
    config = oci.config.from_file(file_location=file_location, profile_name='DEFAULT')
    cloud_guard_client = oci.cloud_guard.CloudGuardClient(config)
    response = cloud_guard_client.list_security_policies(
        compartment_id=get_compartment_id()
    )
    print(response.data)
    return response.data


def read_ToJson():
    # 文件路径（当前目录下的 billWarn.log 文件）
    file_path = 'billWarn.log'

    # 检查文件是否存在
    if os.path.exists(file_path):
        # 创建一个空列表来存储所有日志记录
        log_entries = []

        # 临时字典存储每条记录的字段
        current_entry = {}
        # 读取并遍历每一行
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()  # 去除每行的前后空白字符
                if line.startswith("开始时间:"):
                    # 如果当前有数据，则保存它
                    if current_entry:
                        log_entries.append(current_entry)
                    current_entry = {"开始时间": line.split(":", 1)[1].strip()}  # 提取时间
                elif line.startswith("结束时间:"):
                    current_entry["结束时间"] = line.split(":", 1)[1].strip()  # 提取租户
                elif line.startswith("租户:"):
                    current_entry["租户"] = line.split(":", 1)[1].strip()  # 提取租户
                elif line.startswith("消费CNY:"):
                    current_entry["消费CNY"] = float(line.split(":", 1)[1].strip())  # 提取消费金额

            # 处理最后一条记录
            if current_entry:
                log_entries.append(current_entry)

        # 将结果转换为 JSON 格式
        json_output = json.dumps(log_entries, ensure_ascii=False, indent=4)

        # 打印读取到的内容（可以选择性地打印）
        # print(json_output)
        return json_output




def jsonToExcel(json_data):
    data = json.loads(json_data)
    df = pd.DataFrame(data)
    # 将 DataFrame 保存为 Excel 文件
    output_file = 'Bill.xlsx'
    df.to_excel(output_file, index=False, engine='openpyxl')
    return (df.to_string(index=False))


def jsonToImg(json_data):
    data = json.loads(json_data)
    # 提取横坐标（time_usage_ended）和纵坐标（computed_amount）
    x_values = [item["结束时间"] for item in data]
    y_values = [item["消费CNY"] for item in data]
    total_cost = round(sum(y_values), 2)

    x_labels = [date.split(" ")[0] for date in x_values]
    # 绘制折线图
    plt.figure(figsize=(16.18, 10))  # 设置画布大小
    plt.plot(x_values, y_values, marker='o', linestyle='-', color='b', label='COST')

    # 优化横坐标
    # 设置横坐标间隔：隔 5 个显示 1 个
    step = 2  # 每隔 5 个显示一个
    plt.xticks(ticks=range(0, len(x_labels), step), labels=x_labels[::step], rotation=45)

    # 设置标题和坐标轴标签
    plt.title("cost-time(" + get_tenancy() + ")(total:" + str(total_cost) + ")", fontsize=20)
    plt.xlabel("time", fontsize=10)
    plt.ylabel("COST-CNY", fontsize=12)

    # 优化 x 轴显示（旋转日期标签）
    #plt.xticks(rotation=45)

    # 添加网格线和图例
    plt.grid(alpha=0.3)
    plt.legend()

    # 保存图片到文件（可选）
    plt.savefig("cost_over_time.png", dpi=300)

    # 显示图像
    plt.show()

def get_BillWarning():
    while 1:
        # 获取当前时间
        current_time_utc = datetime.datetime.now(pytz.utc)
        # 转换为UTC+8时区
        china_tz = pytz.timezone('Asia/Shanghai')
        timestamp = current_time_utc.astimezone(china_tz)
        aBill = get_currentMonthBill().items
        sorted_aBill = sorted(aBill, key=lambda x: x.time_usage_started)
        #print(sorted_data)
        c = CurrencyConverter()
        file_path = 'billWarn.log'
        # 检查文件是否存在
        if os.path.exists(file_path):
            # 如果文件存在，删除该文件
            os.remove(file_path)

        for bill in sorted_aBill:
            amount = bill.computed_amount
            converted_amount = c.convert(amount, bill.currency, 'CNY')
            print(
                "开始时间:" + str(bill.time_usage_started) + "\n结束时间:" + str(bill.time_usage_ended) + "\n租户:" + str(get_tenancy()) + "\n消费CNY:" + str(round(converted_amount, 2)) + "\n")

        time.sleep(2)
        billJson = read_ToJson()
        billMsg = jsonToExcel(billJson)
        jsonToImg(billJson)

        #body_billMsg = billMsg
        attachment_files = ["Bill.xlsx", "cost_over_time.png"]
        if os.path.exists("Bill.xlsx") and os.path.exists("cost_over_time.png"):
            email_model.email_send_with_attachments(email_model.bill_topic, billMsg, attachment_files)
        else:
            email_model.email_send(email_model.bill_topic, billMsg)
        time.sleep(3600 * 24)


# if __name__ == '__main__':
#     # @ 1:
#     # 验证 config!! 配置文件加载没问题则不报错
#     # validate_config(config)
#
#     # @ 2:
#     # 创建用户 ,顺带加上admin权限
#     # you_email="XXXXX@xx.com"
#     # creat_user(you_email)
#
#     # @ 3:
#     # 删除用户 ,顺带加上admin权限
#     # my_email="yourEmail@yourEmail.com"
#     # delete_user(my_email)
#
#     # @ 3:
#     # 创建实例（抢鸡）
#     # params = read_params_from_file(file_path)  # 读取形参的值（你要抢的配置）
#     # creat_instance(**params)
#
#     # @ 4:
#     # 账单监控
#     # get_BillWarning()
#
#     # @测试
#     # get_tenancy()
#     get_BillWarning()

