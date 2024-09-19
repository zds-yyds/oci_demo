#!/bin/bash
# 获取并输出当前工作目录 例如：/root/demo
CURRENT_DIR=$(pwd)

#如果不包含"demo/demo1/……"就退出
if [[ "$CURRENT_DIR" != *demo* ]]; then
  echo "错误: 请确保路径正确！"
  exit 1
fi

# 检查目录中是否存在 email_model.py 和 main.py 文件
if [ ! -f "${CURRENT_DIR}/email_model.py" ] || [ ! -f "${CURRENT_DIR}/main.py" ]; then
  echo "错误: 请确保路径正确！"
  exit 1
fi

EMAIL_MODEL_FILE="${CURRENT_DIR}/email_model.py"

# 提取第14行
LINE_14=$(sed -n '14p' "$EMAIL_MODEL_FILE")

# 检查第14行
if [[ "$LINE_14" == 'sender_password = ""' ]]; then
    echo "警告: 未配置邮箱！！"
fi

# 读取 params.txt 文件的内容，检查是否包含预期的 shape_name
if [ -f "${CURRENT_DIR}/params.txt" ]; then
  echo "打开文件 ${CURRENT_DIR}/params.txt 进行读取..."

  # 读取文件中的值
  while IFS='=' read -r key value; do
    if [ "$key" = "shape_name" ]; then
      shape_name="$value"
      echo "镜像(arm/amd): $shape_name"
	  continue
    fi
	if [ "$key" = "instance_ocpus" ]; then
      instance_ocpus="$value"
      echo "OCPUS(核): $instance_ocpus"
	  continue
    fi
	if [ "$key" = "instance_memory_in_gbs" ]; then
      instance_memory_in_gbs="$value"
      echo "RAM(GB): $instance_memory_in_gbs"
	  continue
    fi
	if [ "$key" = "boot_volume_size_in_gbs" ]; then
      boot_volume_size_in_gbs="$value"
      echo "硬盘(GB): $boot_volume_size_in_gbs"
	  continue
    fi
	if [ "$key" = "frequency" ]; then
      frequency="$value"
      echo "频率(s): $frequency"
      break
    fi
  done < "${CURRENT_DIR}/params.txt"

  # 提示用户确认
  read -p "是否确保配置无误？输入 'y' 无误并继续: " user_input

  if [ "$user_input" != "y" ]; then
    echo "用户中断，脚本结束。"
    exit 1
  fi
else
  echo "错误: 找不到 params.txt 文件。"
  exit 1
fi

cd "${CURRENT_DIR}" || exit
source "${CURRENT_DIR}/venv/bin/activate"

if [ -f "${CURRENT_DIR}/output.log" ]; then
  if [ -f "${CURRENT_DIR}/output1.log" ]; then
    nohup python3 -u main.py > output2.log 2>&1 & echo "PID: $!" >> pid2.txt && echo "$shape_name" >> pid2.txt
    exit 0
  fi
  nohup python3 -u main.py > output1.log 2>&1 & echo "PID: $!" >> pid1.txt && echo "$shape_name" >> pid1.txt
  exit 0
fi
nohup python3 -u main.py > output.log 2>&1 & echo "PID: $!" >> pid.txt && echo "$shape_name" >> pid.txt
exit 0


