from enum import Enum
from lark import Lark, Token

PARSER = r'''
LIT.2: "true" | "false" | "1" | "0" | "False" | "True"
ID.1: /[\w_]+/ | /"[^"]+"/ | /X\d+/

NEGATION: "!" | "~" | "¬"
DISJUNCTION: "|" | "||" | "\/" | "+" | "∨" | "∪"
CONJUNCTION: "&" | "&&" | "\/\\" | "\*" | "∧" | "∩"
IMPLICATION: "->" | "=>" | "-->" | "→" | "⟶" | "⇒" | "⇙"
EXCLUSION: "xor" | "^" | "⊕"
EQUIVALENCE: "<->" | "<=>" | "<-->" | "↔" | "⇔"
FIXPOINT_MU.2: "mu" | "μ"
FIXPOINT_NU.2: "nu" | "ν"
ONE: "< >"  
ALL: "[ ]"

?start: formula0

?formula0: formula1
    | formula1 IMPLICATION formula0
    | formula1 EQUIVALENCE formula0

?formula1: formula2
    | formula1 EXCLUSION formula2

?formula2: formula3
    | formula2 DISJUNCTION formula3

?formula3: formula4
    | formula3 CONJUNCTION formula4

?formula4: formula5
    | FIXPOINT_MU ID "." formula4
    | FIXPOINT_NU ID "." formula4
    | NEGATION formula4
    | ONE formula4       
    | ALL formula4 

?formula5: LIT
    | ID
    | "(" formula0 ")"

%import common.WS
%ignore WS
'''

# Enumeration of operators
Operator = Enum('Operator', (
    'LIT', 'VAR','PROP', 'ONE', 'ALL', 'NEGATION', 'DISJUNCTION', 'CONJUNCTION',
    'IMPLICATION', 'EXCLUSION', 'EQUIVALENCE',
    'FIXPOINT_MU', 'FIXPOINT_NU',
))


class BaseParser:
    """Base parser for formulae with contexts"""

    def __init__(self):
        self.parser = Lark(PARSER, parser='lalr')

    def raw_parse(self, text: str):
        """Get the raw AST"""
        return self.parser.parse(text)

    def _translate(self, ast):
        """Translate from Lark to our AST format"""
        if isinstance(ast, Token):
            if ast.type == 'ID':
                name = ast.value
                if name[0].isupper():  # Ej: X, Y, Z
                    return Operator.VAR, name
                else:  # Ej: p, q, r
                    return Operator.PROP, name

            elif ast.type == 'LIT':
                return Operator.LIT, ast.value in ['true', '1']
        else:
            args = ast.children

            if len(args) == 3:
                if isinstance(args[0], Token) and args[0].type in ['FIXPOINT_MU', 'FIXPOINT_NU']:
                    return Operator[args[0].type], args[1].value, self._translate(args[2])
                else:
                    return Operator[args[1].type], self._translate(args[0]), self._translate(args[2])
            elif len(args) == 2:
                if args[0].type == 'ONE':
                    return Operator.ONE, "", self._translate(args[1])
                elif args[0].type == 'ALL':
                    return Operator.ALL, "", self._translate(args[1])
                else:
                    return Operator[args[0].type], self._translate(args[1])
            else:
                raise ValueError('unexpected number of arguments')

    def parse(self, text: str):
        """Parse a formula with contexts to our internal format"""
        return self._translate(self.parser.parse(text))

    def get_subformulas(self, formula):
        #Dada una fórmula devolver el conjunto de sus subformulas

        def extract_subformulas(ast, subformulas):
            if isinstance(ast, tuple):
                subformulas.add(ast)
                for arg in ast[1:]:
                    extract_subformulas(arg, subformulas)
        parsed_formula = self.parse(formula)
        subformulas = set()
        extract_subformulas(parsed_formula, subformulas)
        return subformulas

    def _substitute_variable(self, ast, var, expr):
        if isinstance(ast, tuple):
            if ast[0] == Operator.VAR and ast[1] == var:
                return expr
            return tuple(self._substitute_variable(arg, var, expr) for arg in ast)
        return ast


    def extract_unique_subformulas(self, formula):
        """Extracts all unique subformulas, applying unfolding for fixpoints."""
        ast = self.parse(formula)
        subformulas = set()

        def process_formula(f):
            if f in subformulas:
                return
            subformulas.add(f)

            if f[0] in [Operator.FIXPOINT_MU, Operator.FIXPOINT_NU]:
                unfolded = self._substitute_variable(f[2], f[1], f)
                process_formula(unfolded)
            elif f[0] in [Operator.CONJUNCTION, Operator.DISJUNCTION]:
                process_formula(f[1])
                process_formula(f[2])
            elif f[0] in [Operator.ONE, Operator.ALL]:
                process_formula(f[2])
            elif f[0] == Operator.NEGATION:
                process_formula(f[1])
            elif f[0] == Operator.LIT or f[0] == Operator.VAR:
                pass  # no deeper structure

        process_formula(ast)
        return subformulas


    def transition_function(self, q, P):

        transition_rules = {
            Operator.CONJUNCTION: lambda q: {q[1], q[2]},
            Operator.DISJUNCTION: lambda q: {q[1], q[2]},
            Operator.ONE: lambda q: {q[2]},
            Operator.ALL: lambda q: {q[2]},
            Operator.FIXPOINT_MU: lambda q: {self._substitute_variable(q[2], q[1], q)},
            Operator.FIXPOINT_NU: lambda q: {self._substitute_variable(q[2], q[1], q)},
            Operator.VAR: lambda q: {Operator.LIT, True} if q[1] in P else {Operator.LIT, False},
            Operator.NEGATION: lambda q: {Operator.LIT, False} if q[1] in P else {Operator.LIT, True}
        }

        return transition_rules.get(q[0], lambda q: {q})(q) if isinstance(q, tuple) else {q}


def main():
    formula = "mu X.(p || < >X)"
    parser = BaseParser()
    ast = parser.parse(formula)
    print("Fórmula de entrada:", formula)
    print("AST resultante:")
    print(ast)

if __name__ == "__main__":
    main()

