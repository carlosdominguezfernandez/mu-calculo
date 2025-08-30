#
# Punto de entrada del algoritmo de satisfactibilidad
#

import sys

import spot

from parser import BaseParser
from parityGame import ParityGame


def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument('formula', help='Fórmula')

	args = parser.parse_args()

	# Parsea la fórmula
	formula = BaseParser().parse(args.formula)

	# Crea el APTA
	pg = ParityGame.from_formula(formula)
	pg_txt = pg._to_pgsolver_format()
	# print(pg_txt)

	pga, = spot.automata(pg_txt)

	print(not spot.solve_game(pga))

	return 0


if __name__ == '__main__':
	sys.exit(main())
