"""Behavior checks for the separate exploratory semantic challenge study."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class SemanticFollowupTests(unittest.TestCase):
    def test_touching_intervals_are_valid_and_joined(self):
        from semantic_validation_followup import challenge_cases
        cases = challenge_cases('aggregation.interval_union')
        touching = next(c for c in cases if c['principle'] == 'touching_intervals')
        self.assertEqual(touching['expected'], {'main': {'segments': [[0, 5]], 'covered': 5}})

    def test_overpayment_does_not_cancel_other_account_debt(self):
        from semantic_validation_followup import challenge_cases
        case = next(c for c in challenge_cases('reports.invoice_balances')
                    if c['principle'] == 'separate_debt_and_credit')
        self.assertEqual(case['expected']['summary']['due'], 5)
        self.assertEqual(case['expected']['summary']['credit'], 5)

    def test_exact_stock_exhaustion_is_accepted(self):
        from semantic_validation_followup import challenge_cases
        case = next(c for c in challenge_cases('service.stock_allocation')
                    if c['principle'] == 'exact_stock')
        self.assertEqual(case['expected'], {'main': {'accepted': ['a'], 'rejected': [], 'remaining': 0}})

    def test_all_sixteen_correct_controls_pass_valid_challenges(self):
        from semantic_validation_followup import challenge_cases, evaluate_program
        from rm15.tasks import TEMPLATES, solver
        for template in TEMPLATES:
            cases = challenge_cases(template)
            self.assertEqual(len(cases), 4)
            for case in cases:
                result = evaluate_program(solver(template), template, case)
                self.assertTrue(result['passed'], (template, case['principle'], result))

    def test_three_recipes_retained_and_inputs_are_candidate_independent(self):
        from semantic_validation_followup import challenge_cases, programs
        from rm15.tasks import TEMPLATES
        from rm15.validation_study import digest
        for template in TEMPLATES:
            before = digest(challenge_cases(template))
            candidates = programs(template)
            self.assertEqual(len(candidates), 4)
            self.assertEqual(sum(p['kind'] == 'mutant' for p in candidates), 3)
            self.assertEqual(before, digest(challenge_cases(template)))

    def test_definition_is_exploratory_and_includes_all_candidates_before_execution(self):
        from semantic_validation_followup import build_definition
        definition = build_definition()
        self.assertTrue(definition['exploratory'])
        self.assertFalse(definition['confirmatory'])
        self.assertEqual(len(definition['templates']), 16)
        self.assertEqual(sum(len(p) for p in definition['programs'].values()), 64)
        for suites in definition['cases'].values():
            self.assertEqual(len(suites['random']), 4)
            self.assertEqual(len(suites['semantic_challenge']), 4)
            self.assertEqual(len(suites['final_random']), 12)
            self.assertEqual(len(suites['final_parameterized']), 4)


if __name__ == '__main__':
    unittest.main()
