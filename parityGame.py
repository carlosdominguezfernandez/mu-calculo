from gameArena import GameArena
from apta import APTA
from npa import NPA, Label
from determiniza import determinize

class ParityGameNode:
    def __init__(self, arena_position, tracking_state, symbol, player: bool, priority: int, idx: int):
        self.idx = idx
        self.arena_position = arena_position
        self.tracking_state = tracking_state
        self.symbol = symbol  # puede ser None
        self.player = player
        self.priority = priority + 1
        self.successors: set['ParityGameNode'] = set()

class ParityGame:
    def __init__(self, arena: GameArena, tracking_aut: NPA):
        self.arena = arena
        self.tracking_aut = tracking_aut
        self.nodes: list[ParityGameNode] = []
        self.node_map: dict[tuple, ParityGameNode] = {}

    def get_node(self, arena_pos, tracking_state, symbol) -> ParityGameNode:
        key = (arena_pos, tracking_state, symbol)
        if key in self.node_map:
            return self.node_map[key]

        idx = len(self.nodes)
        if symbol is None:
            player = self.arena.positions[arena_pos].is_diamond
        else:
            player = False
        priority = self.tracking_aut.states[tracking_state].priority
        node = ParityGameNode(arena_pos, tracking_state, symbol, player, priority, idx)
        self.node_map[key] = node
        self.nodes.append(node)
        return node



    @staticmethod
    def from_formula(formula) -> 'ParityGame':
        apta = APTA().from_formula(formula)
        apta.compute_total_priority()

        arena = GameArena()
        arena.emptyness_arena(apta, formula)

        npa = NPA().from_apta(apta)
        dnpa = determinize(npa)

        game = ParityGame(arena, npa)
        game.build()
        return game

    def get_initial_node(self) -> ParityGameNode:
        """
        Devuelve el nodo inicial del juego, basado en la posición 0 de la arena y el estado 0 del NPA.
        """
        arena_init = self.arena.positions[0]
        tracking_init = self.tracking_aut.states[0]
        return self.get_node(
            arena_pos=0,
            tracking_state=tracking_init.idx,
            symbol=None
        )

    def expand_state(self, node: ParityGameNode):
        arena_pos = self.arena.positions[node.arena_position]
        tracking_state = self.tracking_aut.states[node.tracking_state]

        if node.symbol is None:
            if arena_pos.symbol is None:  # regla 2
                for sigma, tgt_idx in arena_pos.next:
                    tgt_node = self.arena.positions[tgt_idx]
                    new_node = self.get_node(
                        arena_pos=tgt_idx,
                        tracking_state=node.tracking_state,
                        symbol=sigma,
                    )
                    node.successors.add(new_node)
            else:  # regla 1
                sigma = arena_pos.symbol
                for d, tgt_idx in arena_pos.next:
                    new_node = self.get_node(
                        arena_pos=tgt_idx,
                        tracking_state=node.tracking_state,
                        symbol=(sigma, d),
                    )
                    node.successors.add(new_node)

        # Regla 3: ((σ,d), v', t) → (v', t')
        elif isinstance(node.symbol, tuple) and len(node.symbol) == 2:
            sigma, d = node.symbol
            sigma_dict = dict(sigma)

            for label, t_primes in tracking_state.next.items():
                is_compatible = False

                if label.type == Label.Type.CHOICE:
                    if not isinstance(d, frozenset):
                        continue
                    if label.extra is None:
                        is_compatible = True
                    elif isinstance(label.extra, (tuple,list)):
                        d_dict = dict(d)
                        is_compatible = all(d_dict.get(q) == q_prime for q, q_prime in label.extra)

                elif label.type == Label.Type.ANY:
                    is_compatible = True

                elif label.type == Label.Type.STATE:
                    if isinstance(d, int) and isinstance(label.extra, int) and d == label.extra:
                        is_compatible = True
                    else:
                        is_compatible = False

                if is_compatible and label.aprops:
                    is_compatible = all(
                        (p not in sigma_dict or sigma_dict[p] == val)
                        for p, val in label.aprops
                    )

                if is_compatible:
                    for t_prime in t_primes:
                        new_node = self.get_node(
                            arena_pos=node.arena_position,
                            tracking_state=t_prime,
                            symbol=None
                        )
                        node.successors.add(new_node)


        # Regla 4: (σ, v', t) → (v', t') (autotransición)
        else:
            sigma = node.symbol
            new_node = self.get_node(
                arena_pos=node.arena_position,
                tracking_state=node.tracking_state,
                symbol=None,
            )
            node.successors.add(new_node)

    def build(self):
        arena_init = self.arena.positions[0]
        tracking_init = self.tracking_aut.states[0]

        initial_node = self.get_node(
            arena_pos=0,
            tracking_state=tracking_init.idx,
            symbol=None
        )

        pending = [initial_node]
        visited = set()

        while pending:
            node = pending.pop()
            key = (node.arena_position, node.tracking_state, node.symbol)
            if key in visited:
                continue
            visited.add(key)

            self.expand_state(node)
            pending.extend(node.successors)

    def print_game(self):
        print(f"\n=== JUEGO DE PARIDAD: {len(self.nodes)} nodos ===")
        for node in self.nodes:
            player = "◇" if node.player else "☐"
            print(f" Nodo {node.idx}: (Arena: {node.arena_position}, Track: {node.tracking_state}, Symbol: {node.symbol}), jugador={player}, prioridad={node.priority}")
            for succ in node.successors:
                print(f"   → Nodo {succ.idx}")

    def _to_pgsolver_format(self):
        lines = []
        lines.append(f"parity {len(self.nodes)};\n")
        for node in self.nodes:
            priority = node.priority
            player = 0 if node.player else 1  # 0 = existencial (◇), 1 = universal (☐)
            # States without successors are not allowed in PGSolver format
            if node.successors:
                successors = ",".join(str(succ.idx) for succ in node.successors)
            else:
                # player cannot move is replaced by player moves in the same
                # state forever, but 1 - player must win, so the priority is
                # adjusted to this effect
                successors = node.idx
                priority = 1 - player
            lines.append(f"{node.idx} {priority} {player} {successors};\n")
        return ''.join(lines)

    def to_pgsolver_format(self, file_path: str):
        with open(file_path, "w") as f:
            f.write(self._to_pgsolver_format())

from parser import BaseParser
from parityGame import ParityGame  # Asegúrate de que el archivo se llame parityGame.py

def main():
    # Fórmula de prueba (usa μ y ν para asegurarte de que haya alternancia)
    formula_str = "nu X. (X && a)"

    parser = BaseParser()
    formula = parser.parse(formula_str)

    # Construir el juego de paridad
    game = ParityGame.from_formula(formula)

    # Imprimir el juego en consola
    game.print_game()

    # Exportar a PGSolver
    game.to_pgsolver_format("output.pg")

    print("\nArchivo 'output.pg' generado para PGSolver.")

if __name__ == "__main__":
    main()
