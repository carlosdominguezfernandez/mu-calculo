import tarjan
from typing import Dict, Set
from parser import Operator, BaseParser

def alternation_depth(formula, polarity=None) -> int:

    op = formula[0]

    if op in [Operator.FIXPOINT_MU, Operator.FIXPOINT_NU]:
        current = 0
        if polarity is None or (polarity == Operator.FIXPOINT_MU and op == Operator.FIXPOINT_NU) or \
                (polarity == Operator.FIXPOINT_NU and op == Operator.FIXPOINT_MU):
            current = 1
        return current + alternation_depth(formula[2], op)

    if op in [Operator.CONJUNCTION, Operator.DISJUNCTION]:
        return max(alternation_depth(formula[1], polarity),
                   alternation_depth(formula[2], polarity))

    if op in [Operator.NEGATION, Operator.ONE, Operator.ALL]:
        return alternation_depth(formula[1] if len(formula) == 2 else formula[2], polarity)

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
        """Completa la función de prioridad total Ω a partir de Ω′ y las SCCs del grafo de estados."""

        # 1. Construir el grafo de estados: diccionario {q: [q1, q2, ...]}
        graph = {
            idx: [elem for value in state.next.values() for elem in value]
            for idx, state in enumerate(self.states)
        }

        # 2. Calcular las SCCs usando tarjan
        sccs = tarjan.tarjan(graph)  # Lista de listas de índices

        for component in sccs:
            if len(component) == 1:
                q = component[0]
                if q in graph and q not in graph[q]:  
                    self.states[q].omega = 0
                    continue

            max_priority = max(self.states[q].omegap for q in component)
            for q in component:
                self.states[q].omega = max_priority

    states: list['APTA.State']
    state_map: dict[Q, int] 

    def __init__(self):
        self.states = []
        self.state_map = {}

    def get_state(self, formula: Q) -> int:
        '''
        Devuelve el índice de un estado.
        Si no existe el estado lo crea automáticamente.
        '''

        if formula not in self.state_map:
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
            return alternation_depth(formula)
        else:
            return 0

    def is_local(self, formula: Q) -> bool:
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
                prop = f[1][1]  
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
