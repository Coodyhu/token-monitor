#!/bin/bash
# install.sh - 安装 Token Monitor LaunchAgent

PLIST_NAME="com.alex.token-monitor.plist"
SRC_PATH="/Users/aaa/projects/token-monitor/${PLIST_NAME}"
DEST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}"

echo "Installing Token Monitor LaunchAgent..."

# 如果已存在，先卸载
if launchctl list | grep -q "com.alex.token-monitor"; then
    echo "Unloading existing agent..."
    launchctl unload "$DEST_PATH" 2>/dev/null
fi

# 复制 plist
echo "Copying plist to $DEST_PATH..."
cp "$SRC_PATH" "$DEST_PATH"

# 加载
echo "Loading agent..."
launchctl load "$DEST_PATH"

# 验证
if launchctl list | grep -q "com.alex.token-monitor"; then
    echo "Success! Token Monitor is now scheduled to run daily at 21:00"
    echo ""
    echo "Commands:"
    echo "  launchctl list | grep token-monitor  # Check status"
    echo "  launchctl start com.alex.token-monitor  # Run now"
    echo "  cat /tmp/token-monitor.log  # View logs"
else
    echo "Error: Failed to load agent"
    exit 1
fi
