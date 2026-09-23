#!/bin/bash

set -e

LOG_DIR="/home/matthieu_merlyn/merlynbot/config/logs/ChannelLogger"

find "$LOG_DIR" \
  -type f \
  -name "*.20??-??-??.log" \
  -mtime +30 \
  -delete
