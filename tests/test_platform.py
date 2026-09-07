import unittest
import time
from risk_manager import RiskManager
from account_manager import calculate_quantity_for_account
from indstocks_client import INDstocksClient
from scanner import MarketScanner

class TestAlgoPlatform(unittest.TestCase):
    def setUp(self):
        self.rm = RiskManager()
        self.account = {
            "id": "test-acc-1",
            "name": "Test Demat",
            "total_capital": 100000.0,
            "capital_allocation_pct": 10.0,  # 10% = ₹10,000 per trade
            "max_loss_limit": 2000.0
        }

    def test_capital_allocation_percentage(self):
        # With 10% of ₹100,000 = ₹10,000 allocation
        # Stock price = ₹2,500 -> Expected qty = 4 (₹10,000 / 2500)
        qty, allocated = self.rm.calculate_position_size(self.account, 2500.0)
        self.assertEqual(qty, 4)
        self.assertEqual(allocated, 10000.0)

        # Test with 5% allocation on ₹50,000 = ₹2,500
        # Stock price = ₹1,000 -> Expected qty = 2
        acc_small = {
            "id": "test-2",
            "total_capital": 50000.0,
            "capital_allocation_pct": 5.0
        }
        qty2, allocated2 = self.rm.calculate_position_size(acc_small, 1000.0)
        self.assertEqual(qty2, 2)
        self.assertEqual(allocated2, 2000.0)

    def test_max_daily_loss_protection(self):
        # If daily loss reaches -₹2000, can_open_trade should be False
        can_open, msg = self.rm.can_open_trade(self.account, [], -2100.0)
        self.assertFalse(can_open)
        self.assertIn("Daily loss limit reached", msg)

        # If daily loss is -₹500, should be approved
        can_open_ok, _ = self.rm.can_open_trade(self.account, [], -500.0)
        self.assertTrue(can_open_ok)

    def test_swing_holding_period_rule(self):
        # Trade opened 8 days ago (exceeding 7 days limit)
        old_trade = {
            "entry_price": 1000.0,
            "target_price": 1060.0,
            "stoploss_price": 975.0,
            "trade_type": "SWING_DELIVERY",
            "entry_time": time.time() - (8 * 86400),
            "qty": 10
        }
        should_exit, reason = self.rm.should_exit_trade(old_trade, 1010.0)
        self.assertTrue(should_exit)
        self.assertEqual(reason, "SWING_7DAY_TIMESTOP")

    def test_paper_trading_execution(self):
        client = INDstocksClient(access_token="", is_paper=True)
        res = client.place_order(
            txn_type="BUY",
            symbol="RELIANCE",
            security_id="2885",
            qty=5,
            order_type="MARKET",
            product="INTRADAY",
            limit_price=2980.0
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["mode"], "PAPER")
        self.assertTrue(res["order_id"].startswith("PAPER-"))

    def test_scanner_output(self):
        scanner = MarketScanner()
        opps = scanner.scan_opportunities()
        self.assertGreater(len(opps), 5)
        first = opps[0]
        self.assertIn("score", first)
        self.assertIn("trade_type", first)
        self.assertIn("target_price", first)
        self.assertIn("stoploss_price", first)

if __name__ == "__main__":
    unittest.main()
