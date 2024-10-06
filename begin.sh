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

cd "${CURRENT_DIR}" || exit


# 定义 PID 文件列表
pid_files=("pid1.txt" "pid2.txt" "pid3.txt" "pid4.txt")

# 遍历每一个 pid 文件
for pid_file in "${pid_files[@]}"; do
  # 检查 pid 文件是否存在且不为空
  if [ -s "$pid_file" ]; then
    # 读取 pid 文件的第一行（进程号）
    pid=$(head -n 1 "$pid_file")
    
    # 检查进程号是否存在
    if ! ps -p "$pid" > /dev/null 2>&1; then
      # 如果进程不存在，删除 pid 文件
      echo "进程 $pid 不存在，删除 $pid_file"
      rm -f "$pid_file"
      # 删除对应的 output 文件
      output_file="${pid_file//pid/output}"
      output_file="${output_file/.txt/.log}"
      if [ -f "$output_file" ]; then
        echo "删除对应的 $output_file 文件"
        rm -f "$output_file"
      fi
    fi
  fi
done

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

source "${CURRENT_DIR}/venv/bin/activate"

if [ -f "${CURRENT_DIR}/output1.log" ]; then
  if [ -f "${CURRENT_DIR}/output2.log" ]; then
    if [ -f "${CURRENT_DIR}/output3.log" ]; then
      if [ -f "${CURRENT_DIR}/output4.log" ]; then
        echo "删除已存在的 output4.log 文件"
        rm -f "${CURRENT_DIR}/output4.log"
      fi
      nohup python3 -u main.py > output4.log 2>&1 & echo "PID: $!" >> pid4.txt && echo "$shape_name" >> pid4.txt
      exit 0
    fi
    nohup python3 -u main.py > output3.log 2>&1 & echo "PID: $!" >> pid3.txt && echo "$shape_name" >> pid3.txt
    exit 0
  fi
  nohup python3 -u main.py > output2.log 2>&1 & echo "PID: $!" >> pid2.txt && echo "$shape_name" >> pid2.txt
  exit 0
fi
nohup python3 -u main.py > output1.log 2>&1 & echo "PID: $!" >> pid1.txt && echo "$shape_name" >> pid1.txt
exit 0


