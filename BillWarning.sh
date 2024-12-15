#!/bin/bash

# 获取当前工作目录
CURRENT_DIR=$(pwd)

# 检查路径是否包含 "demo"
if [[ "$CURRENT_DIR" != *demo* ]]; then
  echo "错误: 请确保路径包含 'demo'！当前路径: $CURRENT_DIR"
  exit 1
fi

# 检查必须的 Python 文件是否存在
REQUIRED_FILES=("email_model.py" "main.py" "BillWaring.py")
for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "${CURRENT_DIR}/${file}" ]; then
    echo "错误: 缺少文件 ${file}，请确保路径正确！"
    exit 1
  fi
done

EMAIL_MODEL_FILE="${CURRENT_DIR}/email_model.py"

# 提取并检查第 14 行
LINE_14=$(sed -n '14p' "$EMAIL_MODEL_FILE")
if [[ "$LINE_14" == 'sender_password = ""' ]]; then
  echo "警告: email_model.py 第14行未配置邮箱！"
fi

# 定义 PID 文件和日志文件路径
PID_FILE="${CURRENT_DIR}/billWarnPID.txt"
LOG_FILE="${CURRENT_DIR}/billWarn.log"

# 检查并清理 PID 文件和日志文件
echo "######## 检查 PID 文件 ########"
if [ -s "$PID_FILE" ]; then
  pid=$(head -n 1 "$PID_FILE")

  # 检查对应的进程是否存在
  if ! ps -p "$pid" > /dev/null 2>&1; then
    echo "进程 $pid 不存在，清理 PID 文件: $PID_FILE"
    rm -f "$PID_FILE"

    # 删除对应的日志文件
    if [ -f "$LOG_FILE" ]; then
      echo "删除对应的日志文件: $LOG_FILE"
      rm -f "$LOG_FILE"
    fi
  fi
else
  echo "开始"
fi
echo "##########################"

# 检查并激活虚拟环境
VENV_PATH="${CURRENT_DIR}/venv/bin/activate"
if [ -f "$VENV_PATH" ]; then
  source "$VENV_PATH"
else
  echo "错误: 虚拟环境未找到: ${VENV_PATH}"
  exit 1
fi

# 检查是否已有监控进程
if [ -f "$LOG_FILE" ]; then
  echo "已存在一个监控进程，日志文件: $LOG_FILE"
  exit 0
fi

# 启动新的监控进程
echo "启动新的监控进程..."
nohup python3 -u BillWarning.py > "$LOG_FILE" 2>&1 & echo "$!" > "$PID_FILE"

echo "监控进程已启动，PID: $(head -n 1 "$PID_FILE")"
exit 0
