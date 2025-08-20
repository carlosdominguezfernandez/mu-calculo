from typing import  Dict, List, Set, Generic, FrozenSet, Optional, Tuple, TypeVar
from itertools import product
from apta import APTA
from parser import Operator

def get_propositions(formula) -> set[str]:
    """Proposiciones atómicas de una fórmula"""

    def _get_propositions(formula, props):
        match formula[0]:
            case Operator.PROP:
                props.add(formula[1])
            case Operator.ONE | Operator.ALL:
                _get_propositions(formula[2], props)
            case Operator.LIT:
                pass
            case _:
                for arg in formula[1:]:
                    _get_propositions(arg, props)

    props = set()
    _get_propositions(formula, props)

    return props

Q = TypeVar("Q")
E = TypeVar("E")

class GameArena(Generic[Q, E]):
    class Position:
        def __init__(self, states: FrozenSet[int], symbol: Optional[E], is_diamond: bool):
            self.states = states
            self.symbol = symbol
            self.is_diamond = is_diamond
            self.is_box = not is_diamond
            self.next: List[Tuple[object, int]] = []

    def __init__(self):
        self.positions: List[GameArena.Position] = []
        self.position_map: Dict[Tuple[FrozenSet[int], Optional[E]], int] = {}
        self.d_choices: Set[FrozenSet[Tuple[int, int]]] = set()

    def get_position(self, states: FrozenSet[int], symbol: Optional[E]) -> int:
        key = (states, symbol)
        if key not in self.position_map:
            is_diamond = symbol is None or any(self.automaton.states[q].local for q in states)
            pos = self.Position(states, symbol, is_diamond)
            index = len(self.positions)
            self.positions.append(pos)
            self.position_map[key] = index
        return self.position_map[key]

    def extract_alphabet(self, states: FrozenSet[int], aut: 'APTA[Q, E]') -> Set[FrozenSet[Tuple[str, bool]]]:
        labels = set()
        for q in states:
            labels |= get_propositions(aut.states[q].value)

        props = sorted(labels)

        sigma_set = set()
        for combo in product([False, True], repeat=len(props)):
            sigma = frozenset((p, b) for p, b in zip(props, combo))
            sigma_set.add(sigma)

        return sigma_set

    def add_transition(self, from_node: 'GameArena.Position', label: object, to_states: FrozenSet[int], symbol: Optional[E], pending: List[int], visited: Set[int]) -> int:
        target_idx = self.get_position(to_states, symbol)
        from_node.next.append((label, target_idx))
        if target_idx not in visited:
            pending.append(target_idx)
        return target_idx

    def emptyness_arena(self, aut: 'APTA[Q, E]', formula: Q):
        self.automaton = aut

        q0 = aut.get_state(formula)
        initial_idx = self.get_position(frozenset({q0}), None)

        pending = [initial_idx]
        visited = set()

        while pending:
            node_idx = pending.pop()
            if node_idx in visited:
                continue
            visited.add(node_idx)

            node = self.positions[node_idx]
            states = node.states
            p = node.symbol

            if p is None:
                for sigma in self.extract_alphabet(states, aut):
                    self.add_transition(node, sigma, states, sigma, pending, visited)


            elif any(self.automaton.states[q].local for q in states):
                existentials = [q for q in states if
                                self.automaton.states[q].local and self.automaton.states[q].existential]

                choices = [list(self.automaton.states[q].next.values()) for q in existentials]
                for successors in product(*choices):
                    for successor_combination in product(*successors):
                        d = frozenset((q, succ) for q, succ in zip(existentials, successor_combination))
                        if d:  # solo guarda los d no vacíos
                            self.d_choices.add(d)
                        d_dict = dict(d)
                        s_prime = self.updatel(states, p, d_dict)
                        self.add_transition(node, d, frozenset(s_prime), p, pending, visited)

            else:
                existentials = [q for q in states if self.automaton.states[q].existential]

                if existentials:
                    for q in existentials:
                        s_prime = self.updatem(states, p, q)
                        self.add_transition(node, q, frozenset(s_prime), None, pending, visited)

                else:
                    universals = [q for q in states if not self.automaton.states[q].existential]
                    if universals:
                        q_rep = min(universals) #por coger algún
                        s_prime = self.updatem(states, p, q_rep)
                        self.add_transition(node, None, frozenset(s_prime), None, pending, visited)

    def updatel(self, s: Set[int], sigma: FrozenSet[Tuple[str, bool]], d: Dict[int, int]) -> Set[int]:
        new_s = set()
        sigma_dict = dict(sigma)  # función característica: p ↦ bool

        for q in s:
            state = self.automaton.states[q]
            if state.local:
                if state.existential:
                    if q in d:
                        new_s.add(d[q])
                else:
                    for label, targets in state.next.items():
                        if label is None:
                            new_s.update(targets)
                        elif isinstance(label, tuple):
                            var, val = label
                            if var in sigma_dict and sigma_dict[var] == val:
                                new_s.update(targets)
            else:
                new_s.add(q)

        return new_s

    def updatem(self, s: Set[int], sigma: E, q: int) -> Set[int]:
        new_s = set()
        for target in self.automaton.states[q].next.values():
            new_s.update(target)
        for q2 in s:
            if q2 != q and not self.automaton.states[q2].existential:
                for target in self.automaton.states[q2].next.values():
                    new_s.update(target)
        return new_s

    def print_arena(self, aut: 'APTA[Q, E]') -> None:
        print("\n=== NODOS DE GAME ARENA ===")
        for idx, pos in enumerate(self.positions):
            states = [aut.states[q].value for q in pos.states]
            symbol = 'None' if pos.symbol is None else set(pos.symbol)
            jugador = "◇" if pos.is_diamond else "☐"

            print(f"[{idx}] jugador={jugador} | estados={states} | símbolo={symbol}")

        print("\n=== ARISTAS ===")
        for idx, pos in enumerate(self.positions):
            source_str = (
                [aut.states[i].value for i in pos.states],
                'None' if pos.symbol is None else set(pos.symbol)
            )
            for label, target_idx in pos.next:
                target = self.positions[target_idx]
                target_str = (
                    [aut.states[i].value for i in target.states],
                    'None' if target.symbol is None else set(target.symbol)
                )
                if isinstance(label, dict):
                    label_str = "d = { " + ", ".join(
                        f"{aut.states[q].value} → {aut.states[t].value}"
                        for q, t in label.items()
                    ) + " }"
                else:
                    label_str = str(label if label is not None else 'None')

                print(f"[{idx}] {source_str} --{label_str}--> [{target_idx}] {target_str}")


if __name__ == "__main__":
    from parser import BaseParser
    from apta import APTA

    # 1. Fórmula de prueba
    formula_str = "nu X.(X && a)"


    # 2. Parsear
    parser = BaseParser()
    formula = parser.parse(formula_str)

    apta = APTA().from_formula(formula)

    arena = GameArena()
    arena.emptyness_arena(apta, formula)
    arena.print_arena(apta)

