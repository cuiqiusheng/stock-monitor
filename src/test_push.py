#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
推送测试脚本 - 模拟信号/波动/大盘场景发送飞书消息
本地使用: source venv/bin/activate && cd src && FEISHU_WEBHOOK="你的webhook" python test_push.py
容器使用: docker exec -it stock-monitor python src/test_push.py
参数: all | signal | volatility | market
"""

import sys
import time
import logging
from datetime import datetime
from monitor import send_feishu, FEISHU_WEBHOOK, MONITORED_SYMBOLS, STOCK_LABELS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TEST_SYMBOL = MONITORED_SYMBOLS[0] if MONITORED_SYMBOLS else "600166"
TEST_STOCK_NAME = STOCK_LABELS.get(TEST_SYMBOL, TEST_SYMBOL)

SCENARIOS = [
    {
        'action': '强力买入',
        'signal_type': '🔴🔴 强力买入信号',
        'price': 9.35,
        'score': 4,
        'reasons': ['价格≤9.50', 'RSI超卖(25.3)', 'MACD底背离', '成交量萎缩'],
        'position_advice': '加仓至40%',
    },
    {
        'action': '温和买入',
        'signal_type': '🔴 买入信号',
        'price': 9.48,
        'score': 2,
        'reasons': ['价格≤9.50', 'RSI超卖(28.7)'],
        'position_advice': '加仓至30%',
    },
    {
        'action': '温和卖出',
        'signal_type': '🟢 卖出信号',
        'price': 10.55,
        'score': -2,
        'reasons': ['价格≥10.50', 'RSI超买(76.2)'],
        'position_advice': '减仓至20%',
    },
    {
        'action': '强力卖出',
        'signal_type': '🟢🟢 强力卖出信号',
        'price': 10.82,
        'score': -4,
        'reasons': ['价格≥10.50', 'RSI超买(81.5)', 'MACD顶背离', '主力净流出'],
        'position_advice': '减仓至10%',
    },
]

VOLATILITY_SCENARIOS = [
    {'pct': 3.12,  'price': 9.80,  'thresholds': ['±3%']},
    {'pct': 5.45,  'price': 10.03, 'thresholds': ['±5%']},
    {'pct': -7.21, 'price': 8.82,  'thresholds': ['±7%']},
    {'pct': 9.56,  'price': 10.42, 'thresholds': ['±3%', '±5%', '±7%', '±9%']},
]


def build_message(s):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""[测试] {s['signal_type']}

股票：{TEST_STOCK_NAME} ({TEST_SYMBOL})
当前价格：{s['price']:.2f} 元
策略得分：{s['score']}
触发因子：{', '.join(s['reasons'])}
时间：{current_time}

建议操作：
- 机动仓：{s['position_advice']}
- 底仓（70%）：继续持有"""


def build_volatility_message(v):
    pct = v['pct']
    price = v['price']
    direction = 'up' if pct >= 0 else 'down'
    abs_pct = abs(pct)
    max_t = max(int(t.strip('±%')) for t in v['thresholds'])

    if direction == 'up':
        emoji = "📈" if max_t < 7 else "🚀"
        label = "涨幅"
        risk_note = "注意追高风险，可考虑分批止盈" if max_t >= 7 else "关注持续性，量价配合"
    else:
        emoji = "📉" if max_t < 7 else "⚠️"
        label = "跌幅"
        risk_note = "关注止损位，控制仓位风险" if max_t >= 7 else "观察支撑位，等待企稳信号"

    crossed = ", ".join(v['thresholds'])
    current_time = datetime.now().strftime("%H:%M:%S")

    return f"""[测试] {emoji} 波动提醒 | {label}达 {abs_pct:.2f}%

股票：{TEST_STOCK_NAME} ({TEST_SYMBOL})
当前价格：{price:.2f} 元
涨跌幅：{pct:+.2f}%
突破阈值：{crossed}
时间：{current_time}

提示：{risk_note}"""


def main():
    if not FEISHU_WEBHOOK:
        logger.error("❌ 飞书 Webhook 未配置，请设置 FEISHU_WEBHOOK 环境变量")
        sys.exit(1)

    test_type = "all"
    if len(sys.argv) > 1:
        test_type = sys.argv[1]

    total = 0
    success = 0

    if test_type in ("all", "signal"):
        logger.info(f"=== 三因子信号测试 ({len(SCENARIOS)} 条) ===")
        for i, s in enumerate(SCENARIOS, 1):
            total += 1
            msg = build_message(s)
            logger.info(f"[{i}/{len(SCENARIOS)}] 发送: {s['action']} (得分 {s['score']})")
            if send_feishu(msg):
                logger.info(f"  ✅ {s['action']} 推送成功")
                success += 1
            else:
                logger.error(f"  ❌ {s['action']} 推送失败")
            time.sleep(1)

    if test_type in ("all", "volatility"):
        logger.info(f"\n=== 波动提醒测试 ({len(VOLATILITY_SCENARIOS)} 条) ===")
        for i, v in enumerate(VOLATILITY_SCENARIOS, 1):
            total += 1
            msg = build_volatility_message(v)
            label = f"涨跌幅 {v['pct']:+.2f}% 突破 {v['thresholds']}"
            logger.info(f"[{i}/{len(VOLATILITY_SCENARIOS)}] 发送: {label}")
            if send_feishu(msg):
                logger.info(f"  ✅ 推送成功")
                success += 1
            else:
                logger.error(f"  ❌ 推送失败")
            time.sleep(1)

    if test_type in ("all", "market"):
        logger.info("\n=== 大盘行情测试 (实时数据) ===")
        total += 1
        from query import query_market
        result = query_market()
        msg = f"[测试] 📊 大盘行情推送\n\n{result}"
        logger.info("发送大盘行情...")
        if send_feishu(msg):
            logger.info("  ✅ 大盘推送成功")
            success += 1
        else:
            logger.error("  ❌ 大盘推送失败")

    logger.info(f"\n测试完成: {success}/{total} 条发送成功，请检查飞书是否收到消息")
    if success < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
