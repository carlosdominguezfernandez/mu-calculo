from gameArena import GameArena
from npa import NPA, Label


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

    def get_node(self, arena_pos, tracking_state, symbol, player, priority) -> ParityGameNode:
        key = (arena_pos, tracking_state, symbol, player)
        if key in self.node_map:
            return self.node_map[key]

        idx = len(self.nodes)
        node = ParityGameNode(arena_pos, tracking_state, symbol, player, priority, idx)
        self.node_map[key] = node
        self.nodes.append(node)
        return node

    def from_formula(self) -> ParityGameNode:
        arena_init = self.arena.positions[0]
        tracking_init = self.tracking_aut.states[0]
        initial_node = self.get_node(
            arena_pos=0,
            tracking_state=tracking_init.idx,
            symbol=None,
            player=arena_init.is_diamond,
            priority=tracking_init.priority
        )
        return initial_node

    def expand_state(self, node: ParityGameNode):
        arena_pos = self.arena.positions[node.arena_position]
        tracking_state = self.tracking_aut.states[node.tracking_state]

        # Regla 1 y 2: symbol is None
        if node.symbol is None:
            if arena_pos.symbol is None:  # regla 1
                for sigma, tgt_idx in arena_pos.next:
                    tgt_node = self.arena.positions[tgt_idx]
                    new_node = self.get_node(
                        arena_pos=tgt_idx,
                        tracking_state=node.tracking_state,
                        symbol=sigma,
                        player=False,
                        priority=tracking_state.priority
                    )
                    node.successors.add(new_node)
            else:  # regla 2
                sigma = arena_pos.symbol
                for d, tgt_idx in arena_pos.next:
                    new_node = self.get_node(
                        arena_pos=tgt_idx,
                        tracking_state=node.tracking_state,
                        symbol=(sigma, d),
                        player=False,
                        priority=tracking_state.priority
                    )
                    node.successors.add(new_node)

        # Regla 3: ((σ,d), v', t) → (v', t')
        elif isinstance(node.symbol, tuple) and len(node.symbol) == 2:
            sigma, d = node.symbol
            sigma_dict = dict(sigma)

            for label, t_primes in tracking_state.next.items():
                is_compatible = False

                if label.type == Label.Type.CHOICE:
                    if label.extra is None or label.extra == d:
                        is_compatible = True
                    elif isinstance(label.extra, tuple) and all(item in d for item in label.extra):
                        is_compatible = True

                elif label.type == Label.Type.ANY:
                    if not label.aprops:
                        is_compatible = True
                    else:
                        is_compatible = all(sigma_dict.get(p) == val for p, val in label.aprops)

                if is_compatible:
                    for t_prime in t_primes:
                        new_node = self.get_node(
                            arena_pos=node.arena_position,
                            tracking_state=t_prime,
                            symbol=None,
                            player=self.arena.positions[node.arena_position].is_diamond,
                            priority=self.tracking_aut.states[t_prime].priority
                        )
                        node.successors.add(new_node)


        # Regla 4: (σ, v', t) → (v', t') (autotransición)
        else:
            sigma = node.symbol
            new_node = self.get_node(
                arena_pos=node.arena_position,
                tracking_state=node.tracking_state,
                symbol=None,
                player=self.arena.positions[node.arena_position].is_diamond,
                priority=tracking_state.priority
            )
            node.successors.add(new_node)

    def build(self):
        pending = [self.from_formula()]
        visited = set()

        while pending:
            node = pending.pop()
            key = (node.arena_position, node.tracking_state, node.symbol, node.player)
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