#!/usr/bin/env python3
"""
监控循环 - 容器入口
包含三因子信号监控 + 定时行情推送 + 波动提醒
"""

import time
from datetime import datetime
from monitor import (
    check_and_notify,
    check_volatility,
    is_trading_time,
    send_feishu,
    logger,
    MONITORED_SYMBOLS,
)
from query import query_realtime, query_market

TRADING_INTERVAL = 60
NON_TRADING_INTERVAL = 300

_PUSH_SCHEDULE = {
    'open':      (935,  940,  '开盘速报'),
    'morning':   (1030, 1035, '早盘中段'),
    'mid_close': (1135, 1140, '午盘收盘'),
    'afternoon': (1305, 1310, '午后开盘'),
    'afternoon_mid': (1400, 1405, '下午盘中'),
    'afternoon_late': (1440, 1445, '尾盘前'),
    'close':     (1505, 1510, '收盘总结'),
}

_daily_push_done = {}


def _check_scheduled_push():
    """在交易日 7 个关键时段自动推送大盘 + 个股行情"""
    now = datetime.now()
    if now.weekday() >= 5:
        return

    today = now.strftime('%Y-%m-%d')
    t = now.hour * 100 + now.minute

    for key, (start, end, label) in _PUSH_SCHEDULE.items():
        if start <= t <= end and _daily_push_done.get(f"{key}_market") != today:
            market = query_market()
            if send_feishu(f"📊 {label} | 大盘行情\n\n{market}"):
                _daily_push_done[f"{key}_market"] = today
                logger.info(f"{label}大盘推送成功")

            stock_sections = [query_realtime(symbol=s) for s in MONITORED_SYMBOLS]
            stock = "\n\n".join(stock_sections)
            if send_feishu(f"📊 {label} | 个股行情\n\n{stock}"):
                _daily_push_done[f"{key}_stock"] = today
                logger.info(f"{label}个股推送成功")


if __name__ == "__main__":
    logger.info(f"股票监控容器启动，监控标的: {', '.join(MONITORED_SYMBOLS)}")
    while True:
        try:
            _check_scheduled_push()
            if is_trading_time():
                check_and_notify()
                check_volatility()
                time.sleep(TRADING_INTERVAL)
            else:
                logger.debug("非交易时段，跳过检查")
                time.sleep(NON_TRADING_INTERVAL)
        except KeyboardInterrupt:
            logger.info("监控容器停止")
            break
        except Exception as e:
            logger.error(f"监控循环异常: {e}")
            time.sleep(TRADING_INTERVAL)
