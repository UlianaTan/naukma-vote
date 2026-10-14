"""Тести чистої доменної логіки: межі інтервалу, переходи, підрахунок, email, CSV.

Не потребують БД і виконуються миттєво.
"""
import unittest
from datetime import datetime, timedelta, timezone

from app.domain.emails import check_email, parse_email_batch
from app.domain.lifecycle import (
    VotingWindow,
    activation_problems,
    can_transition,
    is_expired,
    is_voting_open,
    voting_window,
)
from app.domain.tally import (
    OUTCOME_NO_VOTES,
    OUTCOME_TIE,
    OUTCOME_WINNER,
    determine_outcome,
    percent,
    sorted_rows,
)
from app.models.enums import ElectionStatus
from app.services.csv_export import CSV_COLUMNS, UTF8_BOM, build_results_csv, sanitize_cell

START = datetime(2030, 1, 1, 10, 0, tzinfo=timezone.utc)
END = datetime(2030, 1, 1, 18, 0, tzinfo=timezone.utc)
EPS = timedelta(microseconds=1)


class VotingWindowTests(unittest.TestCase):
    def test_before_start(self):
        self.assertEqual(voting_window(START, END, START - EPS), VotingWindow.NOT_STARTED)

    def test_exact_start_is_open(self):
        self.assertEqual(voting_window(START, END, START), VotingWindow.OPEN)

    def test_last_microsecond_is_open(self):
        self.assertEqual(voting_window(START, END, END - EPS), VotingWindow.OPEN)

    def test_exact_end_is_closed(self):
        self.assertEqual(voting_window(START, END, END), VotingWindow.ENDED)

    def test_naive_datetimes_are_treated_as_utc(self):
        naive_end = END.replace(tzinfo=None)
        self.assertEqual(voting_window(START, naive_end, END - EPS), VotingWindow.OPEN)

    def test_other_timezone_is_normalized(self):
        kyiv = timezone(timedelta(hours=3))
        self.assertEqual(
            voting_window(START, END, END.astimezone(kyiv) - EPS), VotingWindow.OPEN
        )

    def test_only_active_status_accepts_votes(self):
        inside = START + timedelta(hours=1)
        self.assertTrue(is_voting_open(ElectionStatus.ACTIVE, START, END, inside))
        for status in (ElectionStatus.DRAFT, ElectionStatus.CLOSED):
            self.assertFalse(is_voting_open(status, START, END, inside))

    def test_expired_only_for_active(self):
        self.assertTrue(is_expired(ElectionStatus.ACTIVE, END, END))
        self.assertFalse(is_expired(ElectionStatus.ACTIVE, END, END - EPS))
        self.assertFalse(is_expired(ElectionStatus.CLOSED, END, END + timedelta(days=1)))
        self.assertFalse(is_expired(ElectionStatus.DRAFT, END, END + timedelta(days=1)))


class TransitionTests(unittest.TestCase):
    def test_allowed_and_forbidden(self):
        S = ElectionStatus
        self.assertTrue(can_transition(S.DRAFT, S.ACTIVE))
        self.assertTrue(can_transition(S.ACTIVE, S.CLOSED))
        for cur, tgt in [(S.DRAFT, S.CLOSED), (S.ACTIVE, S.DRAFT), (S.CLOSED, S.ACTIVE),
                         (S.CLOSED, S.DRAFT), (S.ACTIVE, S.ACTIVE)]:
            self.assertFalse(can_transition(cur, tgt), (cur, tgt))

    def test_activation_problems(self):
        now = START
        self.assertEqual(activation_problems(candidate_count=2, eligible_count=1, ends_at=END, now=now), [])
        problems = activation_problems(candidate_count=1, eligible_count=0, ends_at=START, now=now)
        self.assertEqual(len(problems), 3)


class TallyTests(unittest.TestCase):
    def test_zero_turnout(self):
        self.assertEqual(determine_outcome({}), (OUTCOME_NO_VOTES, []))
        self.assertEqual(determine_outcome({"a": 0, "b": 0}), (OUTCOME_NO_VOTES, []))
        self.assertEqual(percent(0, 0), 0.0)

    def test_winner_and_tie(self):
        self.assertEqual(determine_outcome({"a": 3, "b": 1}), (OUTCOME_WINNER, ["a"]))
        outcome, leaders = determine_outcome({"a": 2, "b": 2, "c": 1})
        self.assertEqual(outcome, OUTCOME_TIE)
        self.assertEqual(sorted(leaders), ["a", "b"])

    def test_percent_rounding(self):
        self.assertEqual(percent(1, 3), 33.33)
        self.assertEqual(percent(2, 3), 66.67)
        self.assertEqual(percent(5, 5), 100.0)

    def test_stable_ordering(self):
        rows = [(2, "Борис", 1), (1, "Анна", 1), (3, "Віра", 5)]
        self.assertEqual([r[0] for r in sorted_rows(rows)], [3, 1, 2])


class EmailTests(unittest.TestCase):
    def test_normalization_and_domain(self):
        self.assertEqual(check_email("  Test.Student@UKMA.edu.ua ", "ukma.edu.ua"),
                         ("test.student@ukma.edu.ua", None))
        self.assertIsNotNone(check_email("a@gmail.com", "ukma.edu.ua")[1])
        self.assertIsNotNone(check_email("a@evilukma.edu.ua", "ukma.edu.ua")[1])
        self.assertEqual(check_email("a@gmail.com", None)[1], None)

    def test_invalid_formats(self):
        for bad in ["", "   ", "no-at", "a@b", "a b@ukma.edu.ua", "a..b@ukma.edu.ua",
                    "@ukma.edu.ua", None, 5, "a@@ukma.edu.ua"]:
            self.assertIsNotNone(check_email(bad, None)[1], bad)

    def test_batch_dedupes_and_reports_invalid(self):
        valid, dups, invalid = parse_email_batch(
            ["A@ukma.edu.ua", "a@ukma.edu.ua", "b@ukma.edu.ua", "bad", "x@gmail.com"],
            "ukma.edu.ua",
        )
        self.assertEqual(valid, ["a@ukma.edu.ua", "b@ukma.edu.ua"])
        self.assertEqual(dups, 1)
        self.assertEqual([i[0] for i in invalid], ["bad", "x@gmail.com"])


class CsvTests(unittest.TestCase):
    def _row(self, name):
        return dict(election_id="e", candidate_id="c", candidate_name=name, votes=2,
                    percent_of_votes=100.0, total_votes=2, eligible_voters=4,
                    participants=2, turnout_percent=50.0)

    def test_formula_injection_is_neutralized(self):
        for evil in ["=1+1", "+cmd", "-2", "@SUM(A1)"]:
            self.assertEqual(sanitize_cell(evil), "'" + evil)
        self.assertEqual(sanitize_cell("Анна"), "Анна")

    def test_csv_shape(self):
        text = build_results_csv([self._row("=HYPERLINK(1)"), self._row("Анна, Марія")])
        self.assertTrue(text.startswith(UTF8_BOM))
        lines = text[1:].split("\r\n")
        self.assertEqual(lines[0], ",".join(CSV_COLUMNS))
        self.assertIn("'=HYPERLINK(1)", lines[1])
        self.assertIn('"Анна, Марія"', lines[2])

    def test_zero_votes_still_exports_rows(self):
        row = self._row("Анна")
        row.update(
            votes=0,
            percent_of_votes=0.0,
            total_votes=0,
            participants=0,
            turnout_percent=0.0,
        )
        self.assertEqual(len(build_results_csv([row])[1:].strip().split("\r\n")), 2)


if __name__ == "__main__":
    unittest.main()