#!/bin/sh
# 호스트의 ./data 를 /app/data 에 바인드 마운트. 모든 코드의 DB_PATH 는
# /app/data/onbid.db 절대경로로 통일되어 있어 별도 symlink 호환층 불필요.
set -e

mkdir -p /app/data
if [ ! -e /app/data/onbid.db ]; then
    # 최초 부팅 시 빈 파일만 생성 — 스키마는 collector가 알아서 초기화
    touch /app/data/onbid.db
fi

exec "$@"
