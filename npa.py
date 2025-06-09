from enum import Enum
from typing import  Dict, List, Set
from apta import APTA

class Label:
    class Type(Enum):
        ANY = 0
        CHOICE = 1
        STATE = 2

    def __init__(self, type: 'Label.Type', extra=None, aprops=()):
        self.type = type
        self.aprops = aprops  # sequence of (p, bool)
        self.extra = extra  # q', o [(q, q')]

    def __hash__(self):
        return hash((self.type, self.extra, self.aprops))

    def __eq__(self, other):
        return isinstance(other, Label) and self.type == other.type and self.extra == other.extra and self.aprops == self.aprops

    def __repr__(self):
        return f"Label({self.type.name}, {self.extra}, {self.aprops})"


class NPA:

    """Non-deterministic parity automaton on words (tracking automaton)"""

    class State:
        def __init__(self, idx: int, priority: int):
            self.idx = idx
            self.priority = priority  # Omega'(q) = Omega(q) + 1
            self.next: Dict[Label, Set[int]] = {}  # etiqueta -> conjunto de sucesores

    def __init__(self):
        self.states: List[NPA.State] = []

    def from_apta(self, apta: APTA) -> 'NPA':
        """Construye el tracking automaton a partir de un APTA y su arena."""
        self.apta = apta

        # Inicializamos los estados del NPA
        for q_idx, apta_state in enumerate(apta.states):
            priority = apta_state.omega + 1
            npa_state = self.State(q_idx, priority)
            self.states.append(npa_state)

        # Expandimos transiciones para cada estado
        for q_idx in range(len(self.states)):
            self._expand_state(q_idx)

        return self

    def _expand_state(self, state_id: int):
        apta_state = self.apta.states[state_id]
        npa_state = self.states[state_id]

        # Q∨
        if apta_state.local and apta_state.existential:
            # Los sucesores en el APTA etiquetados por su elección
            for next_states in apta_state.next.values():
                for next_state in next_states:
                    lbl = Label(Label.Type.CHOICE, extra=((state_id, next_state),))
                    npa_state.next[lbl] = {next_state}

        # Q∧
        elif apta_state.local and not apta_state.existential:

            for label, tgt in apta_state.next.items():
                if isinstance(label, tuple):  # ('p', True/False)
                    lbl = Label(Label.Type.ANY, aprops=(label,))
                else:
                    lbl = Label(Label.Type.ANY)  # puede ser una conjunción, sin etiqueta específica
                npa_state.next.setdefault(lbl, set()).update(tgt)

        # Q□
        elif not apta_state.local and not apta_state.existential:

            # Transición hacia el único sucesor (φ), con etiqueta STATE
            for next_state in apta_state.next.values():
                lbl = Label(Label.Type.STATE)
                npa_state.next.setdefault(lbl, set()).update(next_state)

            # Autotransición
            lbl = Label(Label.Type.CHOICE)
            npa_state.next[lbl] = {state_id}

        # Q♦
        elif not apta_state.local and apta_state.existential:

            # Transición hacia el único sucesor (φ), con etiqueta STATE
            for next_state in apta_state.next.values():
                lbl = Label(Label.Type.STATE, extra=state_id)
                npa_state.next.setdefault(lbl, set()).update(next_state)

            # Autotransición
            lbl = Label(Label.Type.CHOICE)
            npa_state.next[lbl] = {state_id}

    def transition(self, q: int, a: object) -> Set[int]:
        state = self.states[q]
        return state.next.get(a, set())

    def print_states(self):
        for st in self.states:
            print(f"Estado {st.idx} (Ω′={st.priority}):")
            for lbl, tgts in st.next.items():
                print(f"  {lbl} → {tgts}")
