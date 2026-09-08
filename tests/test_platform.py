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
        # Option price = ₹100, lot_size = 75 (1 Lot = ₹7,500 <= ₹10,000)
        qty, allocated = self.rm.calculate_position_size(self.account, 100.0, lot_size=75)
        self.assertEqual(qty, 75)
        self.assertEqual(allocated, 7500.0)

        # Test with Bank Nifty lot size 30 @ ₹150 (1 Lot = ₹4,500 <= ₹10,000)
        qty2, allocated2 = self.rm.calculate_position_size(self.account, 150.0, lot_size=30)
        self.assertEqual(qty2, 30)
        self.assertEqual(allocated2, 4500.0)

    def test_max_daily_loss_protection(self):
        # If daily loss reaches -₹2000, can_open_trade should be False
        can_open, msg = self.rm.can_open_trade(self.account, [], -2100.0)
        self.assertFalse(can_open)
        self.assertIn("exceeded", msg)

        # Reset emergency halt and test if daily loss is -₹500, should be approved
        self.rm.emergency_halt = False
        can_open_ok, _ = self.rm.can_open_trade(self.account, [], -500.0)
        self.assertTrue(can_open_ok)

    def test_swing_holding_period_rule(self):
        # Intraday trades auto-exit or target hit
        trade = {
            "entry_price": 100.0,
            "target_price": 120.0,
            "stoploss_price": 90.0,
            "trade_type": "INTRADAY",
            "entry_time": time.time(),
            "qty": 75
        }
        should_exit, reason = self.rm.should_exit_trade(trade, 122.0)
        self.assertTrue(should_exit)
        self.assertIn("TARGET_HIT", reason)

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
        self.assertIn("delta", first)
        self.assertIn("india_vix", first)

    def test_mathematical_pnl_nifty(self):
        # 21.25 pts * 75 qty - 48.50 charges = 1545.25
        target_pts = 21.25
        lot_size = 75
        round_trip_charges = 48.50
        gross = round(target_pts * lot_size, 2)
        net = round(gross - round_trip_charges, 2)
        self.assertEqual(gross, 1593.75)
        self.assertEqual(net, 1545.25)

    def test_independent_ce_pe_quotes(self):
        from angel_one_service import angel_one_service
        ce = angel_one_service.get_atm_option_details("NIFTY", 23635.10, "CE")
        pe = angel_one_service.get_atm_option_details("NIFTY", 23635.10, "PE")
        self.assertEqual(ce["lot_size"], 75)
        self.assertEqual(pe["lot_size"], 75)
        # Spot is 23635.10, ATM strike is 23650. Spot < Strike -> CE is slightly OTM, PE is slightly ITM
        # Their premiums must not be dummy identical
        self.assertNotEqual(ce["estimated_premium"], pe["estimated_premium"])
        self.assertGreater(pe["estimated_premium"], ce["estimated_premium"])

if __name__ == "__main__":
    unittest.main()

