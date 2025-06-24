#
# Determiniza el autómata
#

import buddy
import spot


from mu_calculo import Label, NPA, APTA, get_propositions


class BDDMapping:
	"""Determinize the tracking automaton"""

	def __init__(self, apta: APTA, aut):
		# Extract atomic propositions from the initial formula
		A = get_propositions(apta.states[0].value)

		# This dictionary will map AP and auxiliary variable names to their BDD pointers
		self.ap_map = {a: buddy.bdd_ithvar(aut.register_ap(a)) for a in A}

		# Local disjunctive states with at least one succesor
		self.local_ex_states = [state_id for state_id, state in enumerate(apta.states)
		                        if state.local and state.existential 
					and sum(len(sucs) for sucs in state.next.values()) > 1]
		# Model disjunctive states
		self.modal_ex_states = [state_id for state_id, state in enumerate(apta.states)
		                        if not state.local and state.existential]

		# Inverse map for the previous arrays
		self.local_ex_map = {state_id: k for k, state_id in enumerate(self.local_ex_states)}
		self.modal_ex_map = {state_id: k for k, state_id in enumerate(self.modal_ex_states)}

		# Children (at most two by construction) of the local disjunctive states
		self.local_children = [[state for sset in apta.states[state_id].next.values() for state in sset]
		                       for state_id in self.local_ex_states]

		# Number of variables needed to encode state number and the state/choice part
		self.state_length = len(self.modal_ex_states).bit_length()
		self.y_length = max(len(self.local_ex_states), self.state_length)

		# Complete AP map with variables that represent choices and modal states
		for k in range(self.y_length):
			var_name = f'_u{k}'  # assumed to be fresh
			self.ap_map[var_name] = buddy.bdd_ithvar(aut.register_ap(var_name))

		# Complete AP with the control variable
		self.ap_map['_is_choice'] = buddy.bdd_ithvar(aut.register_ap('_is_choice'))
	
	def _literal(self, name: str, value: bool = True):
		"""Literal variable"""

		return self.ap_map[name] if value else buddy.bdd_not(self.ap_map[name])

	def translate_label(self, label: Label):
		"""Translate a label to a Boolean formula"""

		# Labels are translated to a conjunction of (perhaps negated) literals
		clauses = [self._literal(a, value) for a, value in label.aprops]

		match label.type:
			case Label.Type.STATE:
				clauses.append(buddy.bdd_not(self.ap_map['_is_choice']))

				if label.extra is not None:
					# The index of the choice is encoded with some variables
					# (the most significant bit comes first in the sequence)
					num = self.modal_ex_map[label.extra]

					for k in range(self.state_length):
						clauses.append(self._literal(f'_u{k}', num % 2 != 0))
						num //= 2
		
			case Label.Type.CHOICE:
				clauses.append(self.ap_map['_is_choice'])
				
				if label.extra:
					# In principle, there is only one
					for p, q in label.extra:
						# States with a single successor are not considered. All other
						# disjunctive states are assigned an auxiliary variable and
						# that holds whenever the choice is for the second state
						if p_index := self.local_ex_map.get(p):
							second = q != self.local_children[p_index][0]
							clauses.append(self._literal(f'_u{p_index}', second))

		# Builds the conjunction
		if not clauses:
			return buddy.bddtrue

		elif len(clauses) == 1:
			return clauses[0]

		else:
			formula = clauses[0]

			for a in clauses[1:]:
				formula = formula & a

			return formula


	def translate_back_label(self, bdd: buddy.bdd, bdict):
		"""Translate a Boolean formula back to a label"""

		f = spot.bdd_to_cnf_formula(bdd, bdict)

		# Clauses of the conjunctive normal form
		clauses = list(f) if f.kind() == spot.op_Or else (f,)

		# Each disjunction is a separate edge
		for clause in clauses:
			# Each clause is a conjunction of (maybe negated) literals
			literals = list(clause) if clause.kind() == spot.op_And else (clause,)
			values = {}

			for literal in literals:
				match literal.kind():
					case spot.op_ap:
						values[literal.ap_name()] = True

					case spot.op_Not:
						values[literal[0].ap_name()] = False

					case spot.op_tt:
						pass

					case _:
						raise ValueError('unexpected subformula in a CNF')


			# Restrictions on atomic propositions
			aprops = tuple((p, v) for p, v in values.items() if not p.startswith('_'))

			# The second coordinate can be anything
			if '_is_choice' not in values:
				yield Label(Label.Type.ANY, aprops=aprops)

			# The second coordinate is a choice
			elif values['_is_choice']:
				choice = []

				for k, state_nr in enumerate(self.local_ex_states):
					value = values.get(f'_u{k}')

					if value is not None:
						choice.append((state_nr, self.local_children[1 if value else 0]))

				yield Label(Label.Type.CHOICE, extra=tuple(choice), aprops=aprops) 

			# The second coordinate is a modal state
			else:
				state_nr, factor = 0, 1

				# Unspecified state
				if '_u0' not in values:
					state_nr = None

				else:
					for k in reversed(range(self.state_length)):
						if values[f'_u{k}']:
							state_nr += factor
						factor *= 2

				yield Label(Label.Type.STATE, extra=state_nr, aprops=aprops)



def determinize(automaton: NPA):
	"""Determinize the automaton using Spot"""

	# BDD dictionary
	bdict = spot.make_bdd_dict()
	# Automaton (empty for the moment)
	aut = spot.make_twa_graph(bdict)

	# Register atomic propositions
	bddm = BDDMapping(automaton.apta, aut)
	
	# State-based parity acceptance
	omega_max = max(state.priority for state in automaton.states)

	# Acceptance condition
	code = spot.acc_code(f'parity max even {omega_max + 1}')
	aut.set_acceptance(omega_max + 1, code)

	# Acceptance over states, not transitions
	aut.prop_state_acc(True)

	# As many states as the original one
	aut.new_states(len(automaton.states))
	aut.set_init_state(0)

	for sn, state in enumerate(automaton.states):
		for label, children in state.next.items():
			label_bf = bddm.translate_label(label)
			for child in children:
				aut.new_edge(sn, child, label_bf, [state.priority])

	# Muestra el autómata original en formato HOA
	# print(aut.to_str('hoa'))
	from pathlib import Path
	Path('orig.dot').write_text(aut.to_str('dot'))

	# Determinize the automaton
	daut = aut.postprocess('deterministic', 'parity max even', 'colored')

	# Muestra el autómata resultado en formato HOA y DOT
	# print('-' * 50)
	# print(daut.to_str('hoa'))
	Path('graph.dot').write_text(daut.to_str('dot'))

	# Translate the automata back to our format
	new_aut = NPA()
	new_aut.states = [NPA.State(k, -1) for k in range(daut.num_states())]

	for edge in daut.edges():
		src_state = new_aut.states[edge.src]
		# Set the acceptance set of the state
		src_state.priority = int(edge.acc.as_string().strip('{}'))
		# Set the transition
		for label in bddm.translate_back_label(edge.cond, bdict):
			src_state.next.setdefault(label, []).append(edge.dst)
	
	return new_aut


# Ejemplo

if __name__ == '__main__':
	from mu_calculo import BaseParser

	parser = BaseParser()
	formula = parser.parse(r"(< > a) & ([ ] b)")

	aut = APTA().from_formula(formula)
	aut.compute_total_priority()

	tracking_aut = NPA()
	tracking_aut.from_apta(aut)

	new_aut = determinize(tracking_aut)
