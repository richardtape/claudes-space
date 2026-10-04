import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from verify import check_clue  # noqa: E402


def clue(text, answer, parse, defs=(), enum=None):
    return {'clue': text, 'answer': answer, 'parse': parse, 'defs': list(defs),
            'enum': enum or str(len(answer)), 'slot': 'x'}


class VerifyTest(unittest.TestCase):
    def ok(self, c):
        chk = check_clue(c)
        self.assertEqual(chk.failures, [], c['clue'])

    def bad(self, c):
        self.assertTrue(check_clue(c).failures, c['clue'])

    def test_anagram(self):
        self.ok(clue('Silent broadcast? Listen', 'LISTEN', ['ana', 'silent'], ['listen']))
        self.bad(clue('Silent broadcast? Listen', 'LISTED', ['ana', 'silent'], ['listen']))

    def test_fodder_must_be_in_clue(self):
        self.bad(clue('Quiet broadcast? Listen', 'LISTEN', ['ana', 'silent'], ['listen']))

    def test_hidden(self):
        self.ok(clue('Some catacombs hide a pet', 'CAT', ['hid', 'some catacombs'], ['pet']))
        self.ok(clue('Scarab out back', 'BARACS', ['hidrev', 'scarab'], []))  # reversal of SCARAB letters
        self.bad(clue('In the garden, a pet', 'DOG', ['hid', 'the garden'], ['pet']))

    def test_charade_and_container(self):
        # PART + RIDGE ; S(ALE)S
        self.ok(clue('x', 'PARTRIDGE', ['cat', ['syn', 'PART', 'x'], ['syn', 'RIDGE', 'x']]))
        self.ok(clue('x', 'SALES', ['ins', ['syn', 'ALE', 'x'], ['syn', 'SS', 'x']]))
        self.bad(clue('x', 'SALES', ['ins', ['syn', 'ALE', 'x'], ['syn', 'ST', 'x']]))

    def test_reversal_deletion_initials(self):
        self.ok(clue('x', 'STAR', ['rev', ['syn', 'RATS', 'x']]))
        self.ok(clue('x', 'HEAT', ['del', ['syn', 'WHEAT', 'x'], 'W']))
        self.ok(clue('Every apple ripens late', 'EARL', ['first', 'every apple ripens late']))
        self.ok(clue('Oddly, cabbage', 'CBAE', ['odd', 'cabbage']))

    def test_definition_at_an_end(self):
        self.ok(clue('Silent broadcast? Listen', 'LISTEN', ['ana', 'silent'], ['listen']))
        self.bad(clue('Silent listen broadcast', 'LISTEN', ['ana', 'silent'], ['listen x']))

    def test_possessive_definition(self):
        # first run's only failure: "Hen's" was one token, so "Hen" was not found
        self.ok(clue("Hen's bed", 'LAYER', ['dd'], ['Hen', 'bed']))
        self.ok(clue("Store takes in Spain's yes", 'DEPOSIT',
                     ['ins', ['syn', 'SI', "Spain's yes"], ['syn', 'DEPOT', 'store']]))

    def test_enumeration(self):
        self.bad(clue('x', 'FREETIME', ['dd'], enum='4,5'))
        self.ok(clue('x', 'FREETIME', ['dd'], enum='4,4'))


if __name__ == '__main__':
    unittest.main()
