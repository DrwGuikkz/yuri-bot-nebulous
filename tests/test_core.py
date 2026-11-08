import threading
import unittest

from nebulous_bank.chat_reader import parse_command
from nebulous_bank.command_handler import CommandHandler
from nebulous_bank.database import Database
from nebulous_bank.economy import Economy, InsufficientBalance, InvalidAmount
from nebulous_bank.email_reader import EmailReader, parse_gift
from nebulous_bank.gambling import Gambling
from nebulous_bank.game_interface import GiftResult
from nebulous_bank.simulated_game import SimulatedGame
from nebulous_bank.withdrawal import COMPLETED, FAILED, NEEDS_REVIEW, WithdrawalService


class Rolls:
    def __init__(self, *v): self.v = list(v)
    def randint(self, a, b): return self.v.pop(0)


def setup(rng=None):
    db = Database(":memory:")
    g = SimulatedGame()
    eco = Economy(db)
    wd = WithdrawalService(db, g)
    h = CommandHandler(db, eco, Gambling(db, rng), wd, g.send_chat)
    return db, g, eco, wd, h


class Tests(unittest.TestCase):
    def test_parse_gift(self):
        g = parse_gift("Darwin(4231582) sent you a gift of 10000 plasma!")
        self.assertEqual((g.name, g.player_id, g.amount), ("Darwin", 4231582, 10000))
        self.assertIsNone(parse_gift("Darwin sent you a gift of 10000 plasma!"))
        self.assertIsNone(parse_gift("Darwin(1) sent you a gift of 0 plasma!"))

    def test_parse_command(self):
        self.assertEqual(parse_command("!apostar 5000").amount, 5000)
        self.assertFalse(parse_command("!apostar -5").valid)
        self.assertFalse(parse_command("!sacar").valid)
        self.assertIsNone(parse_command("oi"))

    def test_deposit_once(self):
        db, g, eco, *_ = setup()
        self.assertEqual(eco.process_deposit("mail:1", 7, "A", 5000), 5000)
        self.assertIsNone(eco.process_deposit("mail:1", 7, "A", 5000))
        self.assertEqual(eco.get_balance(7), 5000)

    def test_email_reader_ignores_garbage(self):
        db, g, eco, *_ = setup()
        g.push_mail("lixo"); g.push_mail("Ana(9) sent you a gift of 3000 plasma!")
        self.assertEqual(EmailReader(g, eco).poll(), 1)
        self.assertEqual(eco.get_balance(9), 3000)

    def test_bet_win_loss_tie(self):
        db = Database(":memory:"); eco = Economy(db)
        eco.process_deposit("m", 1, "A", 10000)
        gm = Gambling(db, Rolls(8, 4, 3, 7, 5, 5))
        self.assertEqual(gm.place_bet(1, 5000).balance, 15000)
        self.assertEqual(gm.place_bet(1, 5000).balance, 10000)
        r = gm.place_bet(1, 5000)  # empate
        self.assertFalse(r.won); self.assertEqual(r.balance, 5000)

    def test_bet_validation(self):
        db = Database(":memory:"); eco = Economy(db); eco.process_deposit("m", 1, "A", 2000)
        gm = Gambling(db)
        for bad in (999, 50001):
            with self.assertRaises(InvalidAmount): gm.place_bet(1, bad)
        with self.assertRaises(InsufficientBalance): gm.place_bet(1, 5000)
        self.assertEqual(eco.get_balance(1), 2000)

    def test_withdraw_ok_fail_unknown(self):
        db, g, eco, wd, h = setup()
        eco.process_deposit("m", 1, "A", 30000)
        w = wd.request(1, 10000); self.assertEqual(w.net, 9400)
        self.assertEqual(wd.execute(w.id), COMPLETED); self.assertEqual(g.gifts_sent, [(1, 9400)])
        g.gift_result = GiftResult.FAILED
        w = wd.request(1, 10000); self.assertEqual(wd.execute(w.id), FAILED)
        self.assertEqual(eco.get_balance(1), 20000)  # estornado
        g.gift_result = GiftResult.UNKNOWN
        w = wd.request(1, 10000); self.assertEqual(wd.execute(w.id), NEEDS_REVIEW)
        self.assertEqual(eco.get_balance(1), 10000)  # NÃO estorna

    def test_recover_interrupted(self):
        db, g, eco, wd, h = setup()
        eco.process_deposit("m", 1, "A", 5000)
        w = wd.request(1, 2000)
        db._conn.execute("UPDATE withdrawals SET status='sending'")
        self.assertEqual(wd.recover_interrupted(), 1)
        self.assertEqual(wd.execute(w.id), NEEDS_REVIEW)

    def test_command_flow_and_dedupe(self):
        db, g, eco, wd, h = setup(Rolls(8, 4))
        eco.process_deposit("m", 4231582, "Darwin", 10000)
        g.push_chat("Darwin", "!apostar 5000", uid="x")
        g.push_chat("Darwin", "!apostar 5000", uid="x")  # duplicado
        from nebulous_bank.chat_reader import ChatReader
        ChatReader(g, h, "Bot").poll()
        self.assertEqual(eco.get_balance(4231582), 15000)
        self.assertIn("@Darwin Você venceu! 🎲", g.chat_out)

    def test_unknown_player(self):
        db, g, eco, wd, h = setup()
        g.push_chat("Novo", "!saldo")
        from nebulous_bank.chat_reader import ChatReader
        ChatReader(g, h, "Bot").poll()
        self.assertIn("ainda não possui saldo", g.chat_out[0])

    def test_concurrent_bets_never_negative(self):
        db = Database(":memory:"); eco = Economy(db); eco.process_deposit("m", 1, "A", 50000)
        gm = Gambling(db)
        def work():
            for _ in range(20):
                try: gm.place_bet(1, 10000)
                except InsufficientBalance: pass
        ts = [threading.Thread(target=work) for _ in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertGreaterEqual(eco.get_balance(1), 0)
        # livro-razão bate com o saldo
        s = db.query_one("SELECT SUM(amount) s FROM transactions WHERE player_id=1")["s"]
        self.assertEqual(s, eco.get_balance(1))


if __name__ == "__main__":
    unittest.main()
