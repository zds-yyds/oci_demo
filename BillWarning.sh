#!/bin/bash
# 获取并输出当前工作目录 例如：/root/demo
CURRENT_DIR=$(pwd)

#如果不包含"demo/demo1/……"就退出
if [[ "$CURRENT_DIR" != *demo* ]]; then
  echo "错误: 请确保路径正确！"
  exit 1
fi

# 检查目录中是否存在 email_model.py 和 main.py 和 BillWaring.py 文件
if [ ! -f "${CURRENT_DIR}/email_model.py" ] || [ ! -f "${CURRENT_DIR}/main.py" ] || [ ! -f "${CURRENT_DIR}/BillWaring.py" ]; then
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
pid_file=("billWarnPID.txt")



# 遍历每一个 pid 文件
echo "########遍历 pid 文件########"
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
    #output_file="${pid_file//pid/output}"
    output_file="${billWarn/.txt/.log}"
    if [ -f "$output_file" ]; then
      echo "删除对应的 $output_file 文件"
      rm -f "$output_file"
    fi
  fi

fi
echo "##########################"


source "${CURRENT_DIR}/venv/bin/activate"

if [ -f "${CURRENT_DIR}/billWarn.log" ]; then
  echo "已存在一个监控进程!"
  exit 0
fi
nohup python3 -u BillWaring.py > billWarn.log 2>&1 & echo "$!" >> billWarnPID.txt
exit 0


