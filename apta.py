import tarjan
from typing import Dict, Set
from parser import Operator, BaseParser

def variable_occurs(var, formula):
    found = False
    op = formula[0]

    if op == Operator.VAR:
        found = (formula[1] == var)

    elif op in [Operator.FIXPOINT_MU, Operator.FIXPOINT_NU]:
        bound = formula[1]
        if bound != var:
            found = variable_occurs(var, formula[2])

    elif op in [Operator.CONJUNCTION, Operator.DISJUNCTION]:
        found = variable_occurs(var, formula[1]) or variable_occurs(var, formula[2])

    elif op == Operator.NEGATION:
        found = variable_occurs(var, formula[1])

    elif op in [Operator.ONE, Operator.ALL]:
        found = variable_occurs(var, formula[2])

    return found

def alternation_depth(formula) -> int:

    def buscar_siguiente_fixpoint(f):
        op = f[0]
        if op in [Operator.FIXPOINT_MU, Operator.FIXPOINT_NU]:
            return f
        if op in [Operator.CONJUNCTION, Operator.DISJUNCTION]:
            return buscar_siguiente_fixpoint(f[1]) or buscar_siguiente_fixpoint(f[2])
        if op == Operator.NEGATION:
            return buscar_siguiente_fixpoint(f[1])
        if op in [Operator.ONE, Operator.ALL]:
            return buscar_siguiente_fixpoint(f[2])
        return None

    primer_fp = buscar_siguiente_fixpoint(formula)
    if primer_fp is None:
        return 0

    outer_op = primer_fp[0]
    outer_var = primer_fp[1]
    outer_body = primer_fp[2]

    inner_fp = buscar_siguiente_fixpoint(outer_body)
    if inner_fp:
        inner_op, inner_var, inner_body = inner_fp
        appears = variable_occurs(outer_var, inner_body)
        step = 1 if appears and outer_op != inner_op else 0
        return step + alternation_depth(inner_fp)
    else:
        if variable_occurs(outer_var, outer_body):
            return 1
        else:
            return 0



def alternation_level(chi):
    op = chi[0]
    d = alternation_depth(chi)
    if op == Operator.FIXPOINT_MU:
        return 2 * ((d + 1) // 2) - 1
    elif op == Operator.FIXPOINT_NU:
        return 2 * (d // 2)
    else:
        return 0


class APTA[Q, E]:
    """Alternating parity tree automaton"""

    class State:
        def __init__(self, formula: Q, get_priority, is_local, is_existential):
            self.value: Q = formula
            self.local: bool = is_local(formula)
            self.existential: bool = is_existential(formula)
            self.omegap: int = get_priority(formula)
            self.next: Dict[E, Set[int]] = {}
            self.omega: int = 0  # Total priority (Ω) to be computed

    def compute_total_priority(self):

        graph = {
            idx: [elem for value in state.next.values() for elem in value]
            for idx, state in enumerate(self.states)
        }

        # 2. Calcular las SCCs usando tarjan
        sccs = tarjan.tarjan(graph)  # Lista de listas de índices

        for component in sccs:
            if len(component) == 1:
                q = component[0]
                if q in graph and q not in graph[q]:  # sin bucle
                    self.states[q].omega = 0
                    continue

            max_priority = max(self.states[q].omegap for q in component)
            for q in component:
                self.states[q].omega = max_priority

    states: list['APTA.State']  # lista de estados
    state_map: dict[Q, int]     # diccionario de Q a su índice en el array

    def __init__(self):
        self.states = []
        self.state_map = {}

    def get_state(self, formula: Q) -> int:
        '''
        Devuelve el índice de un estado.
        Si no existe el estado lo crea automáticamente.
        '''

        if formula not in self.state_map:
            # Creamos el estado automáticamente a partir de la fórmula
            new_state = self.State(
                formula,
                self.get_priority,
                self.is_local,
                self.is_existential
            )
            index = len(self.states)
            self.states.append(new_state)
            self.state_map[formula] = index

        return self.state_map[formula]

    def get_priority(self, formula: Q) -> int:
        if formula == (Operator.LIT, True):
            return 0
        elif formula == (Operator.LIT, False):
            return 1
        elif isinstance(formula, tuple) and formula[0] in [Operator.FIXPOINT_MU, Operator.FIXPOINT_NU]:
            return alternation_level(formula)
        else:
            return 0

    def is_local(self, formula: Q) -> bool:
        # Determina si una fórmula es un estado local
        return formula[0] in [
            Operator.PROP, Operator.NEGATION, Operator.CONJUNCTION,
            Operator.DISJUNCTION, Operator.FIXPOINT_MU, Operator.FIXPOINT_NU
        ] or formula[0] == Operator.LIT

    def is_existential(self, formula: Q) -> bool:
        return formula[0] in [
            Operator.DISJUNCTION,
            Operator.FIXPOINT_MU,
            Operator.FIXPOINT_NU,
            Operator.ONE] or formula == (Operator.LIT, False)

    def expand_state(self, state_id: int):
        # Expande el estado dado añadiendo sus sucesores etiquetados
        state = self.states[state_id]
        f = state.value

        match f[0]:
            case Operator.CONJUNCTION | Operator.DISJUNCTION:
                self._add_transition(state, None, f[1])
                self._add_transition(state, None, f[2])

            case Operator.ONE | Operator.ALL:
                self._add_transition(state, None, f[2])

            case Operator.FIXPOINT_MU | Operator.FIXPOINT_NU:
                unfolded = BaseParser()._substitute_variable(f[2], f[1], f)
                self._add_transition(state, None, unfolded)

            case Operator.PROP:
                self._add_transition(state, (f[1], True), (Operator.LIT, True))
                self._add_transition(state, (f[1], False), (Operator.LIT, False))

            case Operator.NEGATION:
                prop = f[1][1]  # f = (¬, (PROP, p))
                self._add_transition(state, (prop, True), (Operator.LIT, False))
                self._add_transition(state, (prop, False), (Operator.LIT, True))

            case Operator.LIT:
                self._add_transition(state, None, f)

            case _:
                raise ValueError(f"Fórmula no reconocida al expandir: {f}")

    def _add_transition(self, from_state: 'APTA.State', label: E, target_formula: Q):
        target_id = self.get_state(target_formula)
        from_state.next.setdefault(label, set()).add(target_id)

    def from_formula(self, ast: Q):
        """Construye el APTA expandiendo desde el estado inicial (ya parseado)."""
        initial = self.get_state(ast)
        num_expanded = 0

        while num_expanded < len(self.states):
            self.expand_state(num_expanded)
            num_expanded += 1

        return self

    def print_states(self, title: str = None):
        if title:
            print(f"\n=== {title} ===")

        for idx, state in enumerate(self.states):
            print(f"\nEstado {idx}:")
            print(f"  value: {state.value}")
            print(f"  local: {state.local}")
            print(f"  existential: {state.existential}")
            print(f"  omegap (Ω′): {state.omegap}")
            print(f"  transiciones (next):")
            for label, target_id in state.next.items():
                print(f"    con etiqueta {label} → Estado {target_id}")

if __name__ == "__main__":
    from parser import BaseParser
    from apta import APTA
    from npa import NPA

    # 1. Fórmula de prueba
    formula_str = "nu X.(mu Y. Y && a)"
    # 2. Parsear
    parser = BaseParser()
    formula = parser.parse(formula_str)

    print(alternation_depth(formula))
    # 3. Construir APTA y calcular prioridades
    apta = APTA().from_formula(formula)
    apta.compute_total_priority()
    apta.print_states()
