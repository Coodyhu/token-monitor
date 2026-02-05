#!/bin/bash
# uninstall.sh - 卸载 Token Monitor LaunchAgent

PLIST_NAME="com.alex.token-monitor.plist"
DEST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}"

echo "Uninstalling Token Monitor LaunchAgent..."

# 卸载
if launchctl list | grep -q "com.alex.token-monitor"; then
    echo "Unloading agent..."
    launchctl unload "$DEST_PATH"
fi

# 删除 plist
if [ -f "$DEST_PATH" ]; then
    echo "Removing plist..."
    rm "$DEST_PATH"
fi

echo "Done. Token Monitor has been uninstalled."
